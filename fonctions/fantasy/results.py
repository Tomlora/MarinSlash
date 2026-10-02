"""Immutable result imports, season rule snapshots and historical allocations."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from sqlalchemy import text

from .database import transaction
from .lineup import _context
from .providers.results import ResultImportError
from .scoring import PlayerGameStats, PlayerScoringRules, TeamGameStats, TeamScoringRules, score_player, score_team
from .service import FantasyServiceError


@dataclass(frozen=True)
class ImportSummary:
    imported: int
    unchanged: int


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def import_results(games):
    """Persist a validated provider batch atomically; never alter active pool state."""
    if not games:
        raise ResultImportError('Aucune partie à importer.')
    imported = unchanged = 0
    with transaction() as c:
        c.execute(text("SET LOCAL lock_timeout = '5s'"))
        c.execute(text("SET LOCAL statement_timeout = '30s'"))
        c.execute(text('SELECT pg_advisory_xact_lock(70612027)'))
        for game in games:
            payload = _json(game)
            digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
            old = c.execute(text('''SELECT g.id, r.content_hash FROM fantasy.game g
                LEFT JOIN fantasy.result_snapshot r ON r.game_id = g.id WHERE g.external_game_id = :external'''),
                {'external': game['external_id']}).first()
            if old:
                if old.content_hash != digest:
                    raise ResultImportError('Résultat déjà importé avec un contenu différent : correction explicite nécessaire. Import annulé.')
                unchanged += 1
                continue
            teams, players = {}, {}
            for team in game['teams']:
                params = {'competition': game['competition'], 'external': team['external_id'], 'name': team['name']}
                c.execute(text('''INSERT INTO fantasy.pro_team (competition_code, external_id, name, active)
                    VALUES (:competition, :external, :name, FALSE) ON CONFLICT (competition_code, external_id) DO NOTHING'''), params)
                teams[team['external_id']] = c.execute(text('SELECT id FROM fantasy.pro_team WHERE competition_code = :competition AND external_id = :external'), params).scalar_one()
            for player in game['players']:
                params = {'external': player['external_id'], 'name': player['name'], 'role': player['role']}
                c.execute(text('''INSERT INTO fantasy.pro_player (external_id, handle, role, active)
                    VALUES (:external, :name, :role, FALSE) ON CONFLICT (external_id) DO NOTHING'''), params)
                players[player['external_id']] = c.execute(text('SELECT id FROM fantasy.pro_player WHERE external_id = :external'), params).scalar_one()
            start = datetime.fromisoformat(game['started_at'])
            winner = next(t for t in game['teams'] if t['won'])
            gid = c.execute(text('''INSERT INTO fantasy.game
                (external_game_id, competition_code, started_at, ended_at, duration_seconds, winner_team_id, source)
                VALUES (:external, :competition, :start, :end, :duration, :winner, 'oracle_elixir') RETURNING id'''),
                {'external': game['external_id'], 'competition': game['competition'], 'start': start,
                 'end': start + timedelta(seconds=game['duration_seconds']), 'duration': game['duration_seconds'],
                 'winner': teams[winner['external_id']]}).scalar_one()
            for player in game['players']:
                c.execute(text('''INSERT INTO fantasy.player_game_stats
                    (game_id, player_id, team_id, kills, deaths, assists, cs, triple_kills, quadra_kills, penta_kills, raw)
                    VALUES (:game, :player, :team, :kills, :deaths, :assists, :cs, :triple_kills, :quadra_kills, :penta_kills, CAST(:raw AS jsonb))'''),
                    {**player, 'game': gid, 'player': players[player['external_id']], 'team': teams[player['team_external_id']], 'raw': _json(player)})
            for team in game['teams']:
                c.execute(text('''INSERT INTO fantasy.team_game_stats
                    (game_id, team_id, won, barons, dragons, towers, first_blood, raw)
                    VALUES (:game, :team, :won, :barons, :dragons, :towers, :first_blood, CAST(:raw AS jsonb))'''),
                    {**team, 'game': gid, 'team': teams[team['external_id']], 'raw': _json(team)})
            c.execute(text('INSERT INTO fantasy.result_snapshot (game_id, content_hash, payload) VALUES (:game, :hash, CAST(:payload AS jsonb))'),
                      {'game': gid, 'hash': digest, 'payload': payload})
            imported += 1
    return ImportSummary(imported, unchanged)


def _rules(value):
    try:
        if set(value) != {'player', 'team'}:
            raise ValueError()
        result = []
        for key, cls in (('player', PlayerScoringRules), ('team', TeamScoringRules)):
            if set(value[key]) != set(asdict(cls())):
                raise ValueError()
            if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or abs(v) > 1000 for v in value[key].values()):
                raise ValueError()
            result.append(cls(**value[key]))
        return result
    except (TypeError, ValueError, KeyError):
        raise FantasyServiceError('Barème incomplet ou incompatible : calcul annulé.') from None


def _season_context(c, league_id, guild_id, discord_user_id):
    league, season, manager = _context(c, league_id, guild_id, discord_user_id)
    if league.status not in ('active', 'finished') or season.starts_at is None:
        raise FantasyServiceError('La saison doit avoir commencé après la draft.')
    if league.scoring_mode != 'classic_sum':
        raise FantasyServiceError('Le mode normalisé ne dispose pas encore de règles de calcul ; aucun classement classique ne lui est substitué.')
    return league, season, manager


def calculate_scores(*, league_id, guild_id, discord_user_id):
    with transaction() as c:
        c.execute(text("SET LOCAL lock_timeout = '5s'"))
        c.execute(text("SET LOCAL statement_timeout = '30s'"))
        # Same league lock as lineup/market; histories cannot change mid-calculation.
        from .service import _league_row
        _league_row(c, league_id, guild_id, for_update=True)
        league, season, _ = _season_context(c, league_id, guild_id, discord_user_id)
        if int(league.owner_discord_id) != discord_user_id:
            raise FantasyServiceError('Seul le propriétaire de la Fantasy peut lancer le calcul.')
        row = c.execute(text('SELECT rules FROM fantasy.scoring_rule WHERE version = :version FOR SHARE'), {'version': season.scoring_rule_version}).first()
        if row is None:
            raise FantasyServiceError('Version de barème introuvable.')
        player_rules, team_rules = _rules(row.rules)
        frozen = c.execute(text('SELECT * FROM fantasy.season_scoring_snapshot WHERE season_id = :season'), {'season': season.id}).first()
        if frozen and (frozen.rule_version != season.scoring_rule_version or frozen.rules != row.rules):
            raise FantasyServiceError('Le barème de cette saison a changé depuis le premier calcul : opération annulée.')
        c.execute(text('''INSERT INTO fantasy.season_scoring_snapshot (season_id, rule_version, rules)
            VALUES (:season, :version, CAST(:rules AS jsonb)) ON CONFLICT (season_id) DO NOTHING'''),
            {'season': season.id, 'version': season.scoring_rule_version, 'rules': _json(row.rules)})
        games = c.execute(text('''SELECT g.id, g.started_at, r.payload FROM fantasy.game g
            JOIN fantasy.result_snapshot r ON r.game_id = g.id
            WHERE g.started_at >= :start AND (CAST(:end AS timestamptz) IS NULL OR g.started_at < :end)
            AND NOT EXISTS (SELECT 1 FROM fantasy.season_game_scored s WHERE s.season_id = :season AND s.game_id = g.id)
            ORDER BY g.started_at, g.id LIMIT 201'''),
            {'season': season.id, 'start': season.starts_at, 'end': season.ends_at}).all()
        for game in games[:200]:
            _score_game(c, season.id, game, season.scoring_rule_version, player_rules, team_rules)
        return {'calculated': min(len(games), 200), 'has_more': len(games) > 200, 'version': season.scoring_rule_version}


def _score_game(c, season_id, game, version, player_rules, team_rules):
    values = {}
    # Identity links come from the imported stats, while all scoring inputs and
    # names come from the immutable result snapshot, never the current pool.
    for kind, stats_cls, rules, score_fn in (('player', PlayerGameStats, player_rules, score_player),
                                           ('team', TeamGameStats, team_rules, score_team)):
        source_rows = c.execute(text(f'''SELECT a.{kind}_id AS id, p.external_id FROM fantasy.{kind}_game_stats a
            JOIN fantasy.pro_{kind} p ON p.id = a.{kind}_id WHERE a.game_id = :game'''), {'game': game.id}).all()
        ids = {r.external_id: int(r.id) for r in source_rows}
        if set(ids) != {a['external_id'] for a in game.payload[kind + 's']}:
            raise FantasyServiceError('Identités du résultat incohérentes : calcul annulé.')
        for asset in game.payload[kind + 's']:
            stats = {key: asset[key] for key in asdict(stats_cls()) if key != 'duration_seconds'}
            if kind == 'team':
                stats['duration_seconds'] = game.payload['duration_seconds']
            points = score_fn(stats_cls(**stats), rules)
            aid = ids[asset['external_id']]
            values[(kind, aid)] = (points, asset['name'])
            c.execute(text(f'''INSERT INTO fantasy.{kind}_game_score (season_id, game_id, {kind}_id, score, rule_version)
                VALUES (:season, :game, :asset, :score, :version)'''),
                {'season': season_id, 'game': game.id, 'asset': aid, 'score': points, 'version': version})
    histories = c.execute(text('''SELECT h.* FROM fantasy.roster_history h
        WHERE season_id = :season AND valid_from <= :start AND (valid_until IS NULL OR valid_until > :start)
        ORDER BY id'''), {'season': season_id, 'start': game.started_at}).all()
    assets_seen, slots_seen = set(), set()
    for h in histories:
        key = ('player', h.player_id) if h.player_id is not None else ('team', h.team_id)
        slot_key = (h.manager_id, h.slot)
        if key in assets_seen or (h.slot != 'BENCH' and slot_key in slots_seen):
            raise FantasyServiceError('Historique du roster ambigu au début de la partie : calcul annulé.')
        assets_seen.add(key)
        slots_seen.add(slot_key)
    c.execute(text('INSERT INTO fantasy.season_game_scored (season_id, game_id) VALUES (:season, :game)'), {'season': season_id, 'game': game.id})
    for h in histories:
        key = ('player', h.player_id) if h.player_id is not None else ('team', h.team_id)
        if h.slot == 'BENCH' or key not in values:
            continue
        points, name = values[key]
        c.execute(text('''INSERT INTO fantasy.manager_game_score
            (season_id, game_id, manager_id, roster_history_id, slot, player_id, team_id, asset_name, score, rule_version)
            VALUES (:season, :game, :manager, :history, :slot, :player, :team, :name, :score, :version)'''),
            {'season': season_id, 'game': game.id, 'manager': h.manager_id, 'history': h.id, 'slot': h.slot,
             'player': h.player_id, 'team': h.team_id, 'name': name, 'score': points, 'version': version})


def standings(*, league_id, guild_id, discord_user_id):
    with transaction() as c:
        _, season, _ = _season_context(c, league_id, guild_id, discord_user_id)
        rows = c.execute(text('''SELECT m.discord_user_id, COALESCE(SUM(s.score), 0) AS score,
            COUNT(s.game_id) AS contributions FROM fantasy.manager m
            LEFT JOIN fantasy.manager_game_score s ON s.manager_id = m.id AND s.season_id = :season
            WHERE m.league_id = :league GROUP BY m.id ORDER BY score DESC, m.id'''),
            {'season': season.id, 'league': league_id}).mappings().all()
        progress = c.execute(text('''SELECT COUNT(*) AS imported, COUNT(s.game_id) AS calculated
            FROM fantasy.game g JOIN fantasy.result_snapshot r ON r.game_id = g.id
            LEFT JOIN fantasy.season_game_scored s ON s.game_id = g.id AND s.season_id = :season
            WHERE g.started_at >= :start AND (CAST(:end AS timestamptz) IS NULL OR g.started_at < :end)'''),
            {'season': season.id, 'start': season.starts_at, 'end': season.ends_at}).mappings().one()
        return {'rows': [dict(r) for r in rows], **dict(progress)}


def score_details(*, league_id, guild_id, discord_user_id, page=1):
    if not 1 <= page <= 10000:
        raise FantasyServiceError('Numéro de page invalide.')
    with transaction() as c:
        _, season, manager = _season_context(c, league_id, guild_id, discord_user_id)
        rows = c.execute(text('''SELECT s.*, g.started_at, g.external_game_id FROM fantasy.manager_game_score s
            JOIN fantasy.game g ON g.id = s.game_id WHERE s.season_id = :season AND s.manager_id = :manager
            ORDER BY g.started_at DESC, s.game_id DESC, s.slot LIMIT 11 OFFSET :offset'''),
            {'season': season.id, 'manager': manager, 'offset': (page-1)*10}).mappings().all()
        return [dict(r) for r in rows[:10]], len(rows) > 10
