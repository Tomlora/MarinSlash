"""Atomic add/drop and one-for-one trades, using the existing Fantasy schema."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from .database import transaction
from .freshness import stale_competitions
from .lineup import LineupView, _context, _load_entries, _lock_pool_and_calendar, _locks
from .models import Competition, PlayerAsset, PlayerRole, RosterEntry, RosterSlot, TeamAsset
from .roster import RosterValidationError, validate_final_roster
from .service import FantasyServiceError, _league_row


@dataclass(frozen=True)
class MarketPage:
    assets: tuple[PlayerAsset | TeamAsset, ...]
    page: int
    has_more: bool


@dataclass(frozen=True)
class TradeView:
    trade_id: int
    status: str
    proposer_discord_id: int
    recipient_discord_id: int
    asset_type: str
    offered_id: int
    offered_name: str
    requested_id: int
    requested_name: str


def _column(asset_type):
    if asset_type not in ('player', 'team'):
        raise FantasyServiceError("Choisis un joueur ou une équipe.")
    return asset_type + '_id'


def _identity(entry):
    return ('player', entry.player.player_id) if entry.player else ('team', entry.team.team_id)


def _asset(entry):
    return entry.player or entry.team


def _owned(entries, asset_type, asset_id):
    result = next((e for e in entries if _identity(e) == (asset_type, asset_id)), None)
    if result is None:
        raise FantasyServiceError("Le joueur ou l'équipe n'appartient plus au manager indiqué.")
    return result


def replace_asset(entries, outgoing, incoming):
    """Keep the released slot; never silently rearrange a manager's other starters."""
    if isinstance(incoming, PlayerAsset) != (outgoing.player is not None):
        raise FantasyServiceError("L'échange doit concerner deux joueurs ou deux équipes.")
    replacement = RosterEntry(outgoing.slot, player=incoming) if outgoing.player else RosterEntry(outgoing.slot, team=incoming)
    updated = [replacement if entry == outgoing else entry for entry in entries]
    try:
        validate_final_roster(updated)
    except RosterValidationError as exc:
        raise FantasyServiceError(
            "L'opération doit conserver 5 titulaires à leur rôle, 3 remplaçants, "
            "1 équipe et au moins 2 championnats parmi les titulaires."
        ) from exc
    return updated, replacement


def _active_assets(connection, asset_type, now, *, asset_id=None, season_id=None,
                   role=None, competition=None, offset=0, limit=21):
    column = _column(asset_type)
    params = {'now': now, 'offset': offset, 'limit': limit}
    where = ['a.active = TRUE']
    if asset_type == 'player':
        source = '''fantasy.pro_player a JOIN LATERAL (
            SELECT team.competition_code, team.active, h.valid_until
            FROM fantasy.pro_player_team_history h
            JOIN fantasy.pro_team team ON team.id = h.team_id
            WHERE h.player_id = a.id AND h.valid_from <= :now
            ORDER BY h.valid_from DESC, h.id DESC LIMIT 1
        ) current_team ON TRUE'''
        fields = 'a.id, a.handle AS name, a.role, current_team.competition_code'
        where += ['current_team.active = TRUE', '(current_team.valid_until IS NULL OR current_team.valid_until > :now)']
        comp_column = 'current_team.competition_code'
    else:
        source, fields, comp_column = 'fantasy.pro_team a', 'a.id, a.name, a.competition_code', 'a.competition_code'
    if asset_id is not None:
        where.append('a.id = :asset_id')
        params['asset_id'] = asset_id
    if season_id is not None:
        where.append(f'NOT EXISTS (SELECT 1 FROM fantasy.roster_asset r WHERE r.season_id = :season_id AND r.{column} = a.id)')
        params['season_id'] = season_id
    if role:
        if asset_type != 'player' or role not in {r.value for r in PlayerRole}:
            raise FantasyServiceError("Ce filtre de rôle n'est pas valide.")
        where.append('a.role = :role')
        params['role'] = role
    if competition:
        if competition not in {c.value for c in Competition}:
            raise FantasyServiceError("Championnat inconnu.")
        where.append(comp_column + ' = :competition')
        params['competition'] = competition
    # SQL identifiers are internal constants; every user value is bound.
    rows = connection.execute(text(f'''SELECT {fields} FROM {source}
        WHERE {' AND '.join(where)} ORDER BY LOWER({'a.handle' if asset_type == 'player' else 'a.name'}), a.id
        LIMIT :limit OFFSET :offset'''), params).all()
    return [PlayerAsset(int(r.id), r.name, PlayerRole(r.role), Competition(r.competition_code))
            if asset_type == 'player' else TeamAsset(int(r.id), r.name, Competition(r.competition_code)) for r in rows]


def _eligible(connection, asset_type, asset_id, now):
    assets = _active_assets(connection, asset_type, now, asset_id=asset_id)
    if not assets:
        raise FantasyServiceError("Ce joueur ou cette équipe n'est plus actif dans le pool synchronisé.")
    return assets[0]


def _guard(connection, entries, now):
    competitions = {_asset(entry).competition for entry in entries}
    locked = _locks(connection, now)
    stale = stale_competitions(connection, now)
    if competitions & locked:
        raise FantasyServiceError("Un championnat concerné est verrouillé pour la journée (Europe/Paris).")
    if competitions & stale:
        raise FantasyServiceError("Calendrier trop ancien ou non vérifié : lance /fantasy_update_schedule avant cette opération.")
    return locked, stale


def _write_context(connection, league_id, guild_id, discord_user_id):
    connection.execute(text("SET LOCAL lock_timeout = '5s'"))
    league, season, manager_id = _context(connection, league_id, guild_id, discord_user_id, editing=True)
    _lock_pool_and_calendar(connection)
    now = connection.execute(text('SELECT clock_timestamp()')).scalar_one()
    return league, season, manager_id, now


def list_free_agents(*, league_id, guild_id, discord_user_id, asset_type='player',
                     role=None, competition=None, page=1):
    _column(asset_type)
    if not 1 <= page <= 10000:
        raise FantasyServiceError("Numéro de page invalide.")
    with transaction() as connection:
        league, season, _ = _context(connection, league_id, guild_id, discord_user_id)
        if league.status != 'active':
            raise FantasyServiceError("Le marché ouvre après la draft, dans une Fantasy active.")
        now = connection.execute(text('SELECT clock_timestamp()')).scalar_one()
        assets = _active_assets(connection, asset_type, now, season_id=int(season.id),
                                role=role, competition=competition, offset=(page-1)*20)
        return MarketPage(tuple(assets[:20]), page, len(assets) > 20)


def _move_assets(connection, season_id, moves, now, reason):
    # Delete all outgoing ownerships before inserting incoming ones: the unique
    # season/asset and starter-slot indexes must hold even during a trade.
    for manager_id, old, new in moves:
        kind, asset_id = _identity(old)
        params = {'season': season_id, 'manager': manager_id, 'asset': asset_id, 'slot': old.slot.value, 'now': now}
        result = connection.execute(text(f'''UPDATE fantasy.roster_history SET valid_until = :now
            WHERE season_id = :season AND manager_id = :manager AND {kind}_id = :asset
              AND slot = :slot AND valid_until IS NULL'''), params)
        if result.rowcount != 1:
            raise FantasyServiceError("Historique incohérent : opération annulée.")
        result = connection.execute(text(f'''DELETE FROM fantasy.roster_asset
            WHERE season_id = :season AND manager_id = :manager AND {kind}_id = :asset'''), params)
        if result.rowcount != 1:
            raise FantasyServiceError("Propriété modifiée : opération annulée.")
    for manager_id, old, new in moves:
        params = {'season': season_id, 'manager': manager_id, 'player': new.player.player_id if new.player else None,
                  'team': new.team.team_id if new.team else None, 'slot': new.slot.value, 'now': now, 'reason': reason}
        connection.execute(text('''INSERT INTO fantasy.roster_asset
            (season_id, manager_id, player_id, team_id, slot, acquired_at)
            VALUES (:season, :manager, :player, :team, :slot, :now)'''), params)
        connection.execute(text('''INSERT INTO fantasy.roster_history
            (season_id, manager_id, player_id, team_id, slot, valid_from, reason)
            VALUES (:season, :manager, :player, :team, :slot, :now, :reason)'''), params)
    for _, old, _ in moves:
        kind, asset_id = _identity(old)
        connection.execute(text(f'''UPDATE fantasy.trade SET status = 'invalidated', resolved_at = :now
            WHERE season_id = :season AND status = 'pending' AND id IN
                (SELECT trade_id FROM fantasy.trade_asset WHERE {kind}_id = :asset)'''),
            {'season': season_id, 'now': now, 'asset': asset_id})


def claim_free_agent(*, league_id, guild_id, discord_user_id, asset_type, released_id, incoming_id):
    column = _column(asset_type)
    with transaction() as connection:
        league, season, manager_id, now = _write_context(connection, league_id, guild_id, discord_user_id)
        entries, unavailable = _load_entries(connection, int(season.id), manager_id, now)
        old = _owned(entries, asset_type, released_id)
        owned = connection.execute(text(f'SELECT 1 FROM fantasy.roster_asset WHERE season_id = :season AND {column} = :asset'),
                                   {'season': int(season.id), 'asset': incoming_id}).first()
        if owned:
            raise FantasyServiceError("Ce joueur ou cette équipe est déjà détenu dans cette saison.")
        incoming = _eligible(connection, asset_type, incoming_id, now)
        updated, new = replace_asset(entries, old, incoming)
        locked, stale = _guard(connection, [old, new], now)
        _move_assets(connection, int(season.id), [(manager_id, old, new)], now, 'free_agency')
        return LineupView(league.name, season.name, tuple(updated), locked,
                          unavailable - {released_id} if asset_type == 'player' else unavailable, stale)


def _trade_view(connection, trade_id):
    row = connection.execute(text('''SELECT t.*, p.discord_user_id AS proposer, r.discord_user_id AS recipient
        FROM fantasy.trade t JOIN fantasy.manager p ON p.id = t.proposer_manager_id
        JOIN fantasy.manager r ON r.id = t.recipient_manager_id WHERE t.id = :id'''), {'id': trade_id}).one()
    assets = connection.execute(text('''SELECT a.*, COALESCE(p.handle, t.name) AS name FROM fantasy.trade_asset a
        LEFT JOIN fantasy.pro_player p ON p.id = a.player_id LEFT JOIN fantasy.pro_team t ON t.id = a.team_id
        WHERE a.trade_id = :id ORDER BY a.id'''), {'id': trade_id}).all()
    offered = [a for a in assets if a.from_manager_id == row.proposer_manager_id]
    requested = [a for a in assets if a.from_manager_id == row.recipient_manager_id]
    if len(assets) != 2 or len(offered) != 1 or len(requested) != 1:
        raise FantasyServiceError("Cet échange n'utilise pas le format un contre un.")
    offered, requested = offered[0], requested[0]
    if (offered.player_id is None) != (requested.player_id is None):
        raise FantasyServiceError("Cet échange mélange joueurs et équipes.")
    kind = 'player' if offered.player_id is not None else 'team'
    return TradeView(int(row.id), row.status, int(row.proposer), int(row.recipient), kind,
                     int(offered.player_id or offered.team_id), offered.name,
                     int(requested.player_id or requested.team_id), requested.name)


def _validate_trade(connection, season_id, proposer, recipient, kind, offered_id, requested_id, now):
    left, _ = _load_entries(connection, season_id, proposer, now)
    right, _ = _load_entries(connection, season_id, recipient, now)
    offered = _owned(left, kind, offered_id)
    requested = _owned(right, kind, requested_id)
    active_offered = _eligible(connection, kind, offered_id, now)
    active_requested = _eligible(connection, kind, requested_id, now)
    _, left_new = replace_asset(left, offered, active_requested)
    _, right_new = replace_asset(right, requested, active_offered)
    _guard(connection, [offered, requested], now)
    return [(proposer, offered, left_new), (recipient, requested, right_new)]


def offer_trade(*, league_id, guild_id, discord_user_id, recipient_discord_id, asset_type, offered_id, requested_id):
    column = _column(asset_type)
    with transaction() as connection:
        _, season, proposer, now = _write_context(connection, league_id, guild_id, discord_user_id)
        recipient = connection.execute(text('SELECT id FROM fantasy.manager WHERE league_id = :league AND discord_user_id = :user'),
                                       {'league': league_id, 'user': recipient_discord_id}).first()
        if recipient is None or int(recipient.id) == proposer:
            raise FantasyServiceError("Choisis un autre manager inscrit dans cette Fantasy.")
        recipient = int(recipient.id)
        _validate_trade(connection, int(season.id), proposer, recipient, asset_type, offered_id, requested_id, now)
        params = {'season': int(season.id), 'proposer': proposer, 'recipient': recipient, 'offered': offered_id, 'requested': requested_id}
        existing = connection.execute(text(f'''SELECT t.id FROM fantasy.trade t
            JOIN fantasy.trade_asset a ON a.trade_id = t.id AND a.from_manager_id = t.proposer_manager_id
            JOIN fantasy.trade_asset b ON b.trade_id = t.id AND b.from_manager_id = t.recipient_manager_id
            WHERE t.season_id = :season AND t.proposer_manager_id = :proposer AND t.recipient_manager_id = :recipient
              AND t.status = 'pending' AND a.{column} = :offered AND b.{column} = :requested'''), params).first()
        if existing:
            return _trade_view(connection, int(existing.id))
        trade_id = connection.execute(text('''INSERT INTO fantasy.trade (season_id, proposer_manager_id, recipient_manager_id)
            VALUES (:season, :proposer, :recipient) RETURNING id'''), params).scalar_one()
        for manager, asset_id in ((proposer, offered_id), (recipient, requested_id)):
            connection.execute(text(f'INSERT INTO fantasy.trade_asset (trade_id, from_manager_id, {column}) VALUES (:trade, :manager, :asset)'),
                               {'trade': trade_id, 'manager': manager, 'asset': asset_id})
        return _trade_view(connection, int(trade_id))


def respond_trade(*, league_id, guild_id, discord_user_id, trade_id, action):
    if action not in ('accept', 'decline', 'cancel'):
        raise FantasyServiceError("Action d'échange inconnue.")
    with transaction() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        # Reject/cancel remain possible when a league finishes or calendars expire.
        league = _league_row(connection, league_id, guild_id, for_update=True)
        _, season, manager = _context(connection, league_id, guild_id, discord_user_id)
        trade = connection.execute(text('SELECT * FROM fantasy.trade WHERE id = :id AND season_id = :season FOR UPDATE'),
                                   {'id': trade_id, 'season': int(season.id)}).first()
        if trade is None or manager not in (trade.proposer_manager_id, trade.recipient_manager_id):
            raise FantasyServiceError("Échange introuvable pour ce manager dans cette saison.")
        expected = trade.proposer_manager_id if action == 'cancel' else trade.recipient_manager_id
        if manager != expected:
            raise FantasyServiceError("Seul le destinataire peut accepter/refuser ; seul l'auteur peut annuler.")
        if trade.status != 'pending':
            raise FantasyServiceError("Cet échange est déjà terminé ou invalidé.")
        status = {'accept': 'accepted', 'decline': 'declined', 'cancel': 'cancelled'}[action]
        if action == 'accept':
            if league.status != 'active':
                raise FantasyServiceError("L'échange nécessite une Fantasy active.")
            _lock_pool_and_calendar(connection)
            now = connection.execute(text('SELECT clock_timestamp()')).scalar_one()
            view = _trade_view(connection, trade_id)
            moves = _validate_trade(connection, int(season.id), int(trade.proposer_manager_id),
                                    int(trade.recipient_manager_id), view.asset_type, view.offered_id, view.requested_id, now)
            connection.execute(text("UPDATE fantasy.trade SET status = 'accepted', resolved_at = :now WHERE id = :id"), {'now': now, 'id': trade_id})
            _move_assets(connection, int(season.id), moves, now, f'trade:{trade_id}')
        else:
            connection.execute(text('UPDATE fantasy.trade SET status = :status, resolved_at = clock_timestamp() WHERE id = :id'),
                               {'status': status, 'id': trade_id})
        return _trade_view(connection, trade_id)


def list_trades(*, league_id, guild_id, discord_user_id, page=1):
    if not 1 <= page <= 10000:
        raise FantasyServiceError("Numéro de page invalide.")
    with transaction() as connection:
        _, season, manager = _context(connection, league_id, guild_id, discord_user_id)
        rows = connection.execute(text('''SELECT id FROM fantasy.trade WHERE season_id = :season
            AND (proposer_manager_id = :manager OR recipient_manager_id = :manager)
            ORDER BY (status = 'pending') DESC, id DESC LIMIT 11 OFFSET :offset'''),
            {'season': int(season.id), 'manager': manager, 'offset': (page-1)*10}).all()
        return tuple(_trade_view(connection, int(row.id)) for row in rows[:10]), len(rows) > 10
