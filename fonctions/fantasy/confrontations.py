"""Round-robin periods and explicitly finalized head-to-head standings.

The existing manager_period_score rows are the finalization snapshot: all
participants in a round are written/deleted together under the league lock.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import text

from .database import transaction
from .matchups import round_robin
from .results import _season_context
from .service import FantasyServiceError, _league_row


def period_schedule(manager_ids, start_date, days=7):
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 28:
        raise FantasyServiceError('Une période doit durer entre 1 et 28 jours.')
    try:
        date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if date.isoformat() != start_date:
            raise ValueError()
        rounds = round_robin(manager_ids)
        start = datetime.combine(date, time.min, tzinfo=ZoneInfo('Europe/Paris'))
        return [(m.round_number, m.manager1_id, m.manager2_id,
                 (start + timedelta(days=i*days)).astimezone(timezone.utc),
                 (start + timedelta(days=(i+1)*days)).astimezone(timezone.utc))
                for i, matches in enumerate(rounds) for m in matches]
    except (ValueError, TypeError, OverflowError):
        raise FantasyServiceError('Date AAAA-MM-JJ ou liste de managers invalide (2 à 8 managers distincts).') from None


def _write_context(c, league_id, guild_id, discord_user_id):
    c.execute(text("SET LOCAL lock_timeout = '5s'"))
    c.execute(text("SET LOCAL statement_timeout = '30s'"))
    _league_row(c, league_id, guild_id, for_update=True)
    league, season, _ = _season_context(c, league_id, guild_id, discord_user_id)
    if int(league.owner_discord_id) != discord_user_id:
        raise FantasyServiceError('Seul le propriétaire peut gérer les confrontations.')
    return league, season


def create_schedule(*, league_id, guild_id, discord_user_id, start_date, days=7):
    with transaction() as c:
        league, season = _write_context(c, league_id, guild_id, discord_user_id)
        managers = c.execute(text('SELECT id FROM fantasy.manager WHERE league_id = :league ORDER BY draft_position NULLS LAST, id'),
                             {'league': league_id}).scalars().all()
        planned = period_schedule(managers, start_date, days)
        existing = c.execute(text('''SELECT round_number, manager1_id, manager2_id, starts_at, ends_at
            FROM fantasy.matchup WHERE season_id = :season ORDER BY round_number, id'''), {'season': season.id}).all()
        if existing:
            if [tuple(row) for row in existing] != planned:
                raise FantasyServiceError('Un calendrier existe déjà pour cette saison ; il ne peut pas être remplacé.')
            return {'rounds': planned[-1][0], 'created': False}
        now = c.execute(text('SELECT clock_timestamp()')).scalar_one()
        if league.status != 'active' or planned[0][3] <= now or planned[0][3] < season.starts_at:
            raise FantasyServiceError('Le premier tour doit commencer dans le futur, après le début de la saison active.')
        if season.ends_at is not None and planned[-1][4] > season.ends_at:
            raise FantasyServiceError('Le calendrier dépasse la fin de la saison.')
        for number, left, right, start, end in planned:
            c.execute(text('''INSERT INTO fantasy.matchup
                (season_id, round_number, manager1_id, manager2_id, starts_at, ends_at)
                VALUES (:season, :round, :left, :right, :start, :end)'''),
                {'season': season.id, 'round': number, 'left': left, 'right': right, 'start': start, 'end': end})
        return {'rounds': planned[-1][0], 'created': True}


def _round(c, season_id, number):
    rows = c.execute(text('''SELECT m.*, a.discord_user_id AS user1, b.discord_user_id AS user2
        FROM fantasy.matchup m
        LEFT JOIN fantasy.manager a ON a.id = m.manager1_id
        LEFT JOIN fantasy.manager b ON b.id = m.manager2_id
        WHERE m.season_id = :season AND m.round_number = :round ORDER BY m.id'''),
        {'season': season_id, 'round': number}).mappings().all()
    if not rows:
        raise FantasyServiceError('Tour introuvable. Le propriétaire doit créer le calendrier avec /fantasy fixtures.')
    periods = {(r['starts_at'], r['ends_at']) for r in rows}
    ids = [mid for r in rows for mid in (r['manager1_id'], r['manager2_id']) if mid is not None]
    start, end = rows[0]['starts_at'], rows[0]['ends_at']
    if len(periods) != 1 or start is None or end is None or end <= start or len(ids) != len(set(ids)):
        raise FantasyServiceError('Calendrier incohérent : dates ou participants du tour invalides.')
    snapshots = c.execute(text('''SELECT s.* FROM fantasy.manager_period_score s
        JOIN fantasy.matchup m ON m.id = s.matchup_id WHERE m.season_id = :season AND m.round_number = :round'''),
        {'season': season_id, 'round': number}).mappings().all()
    frozen = {(r['matchup_id'], r['manager_id']): r['score'] for r in snapshots}
    expected = {(r['id'], mid) for r in rows for mid in (r['manager1_id'], r['manager2_id']) if mid is not None}
    if frozen and set(frozen) != expected:
        raise FantasyServiceError('Clôture partielle incohérente : aucune modification effectuée.')
    return rows, frozen, start, end


def _progress(c, season_id, start, end):
    return dict(c.execute(text('''SELECT COUNT(*) AS imported, COUNT(s.game_id) AS calculated
        FROM fantasy.game g JOIN fantasy.result_snapshot r ON r.game_id = g.id
        LEFT JOIN fantasy.season_game_scored s ON s.game_id = g.id AND s.season_id = :season
        WHERE g.started_at >= :start AND g.started_at < :end'''),
        {'season': season_id, 'start': start, 'end': end}).mappings().one())


def _totals(c, season_id, start, end):
    rows = c.execute(text('''SELECT s.manager_id, SUM(s.score) AS score FROM fantasy.manager_game_score s
        JOIN fantasy.game g ON g.id = s.game_id WHERE s.season_id = :season
        AND g.started_at >= :start AND g.started_at < :end GROUP BY s.manager_id'''),
        {'season': season_id, 'start': start, 'end': end}).all()
    return {int(r.manager_id): r.score for r in rows}


def ensure_periods_open(c, season_id, game_ids):
    """A late import must not silently disagree with a finalized round."""
    if not game_ids:
        return
    closed = c.execute(text('''SELECT DISTINCT m.round_number FROM fantasy.matchup m
        JOIN fantasy.game g ON g.started_at >= m.starts_at AND g.started_at < m.ends_at
        WHERE m.season_id = :season AND g.id = ANY(:games)
        AND EXISTS (SELECT 1 FROM fantasy.manager_period_score s WHERE s.matchup_id = m.id)
        ORDER BY m.round_number'''), {'season': season_id, 'games': list(game_ids)}).scalars().all()
    if closed:
        raise FantasyServiceError('Nouveaux résultats dans un tour clôturé (' + ', '.join(map(str, closed))
                                  + ') : réouvre le tour avec /fantasy round avant de recalculer.')


def resolve_round(*, league_id, guild_id, discord_user_id, round_number, action, confirm_complete=False):
    if action not in ('close', 'reopen'):
        raise FantasyServiceError('Action de tour inconnue.')
    with transaction() as c:
        _, season = _write_context(c, league_id, guild_id, discord_user_id)
        # Import takes only this lock; scoring takes only the league lock.
        # Taking both prevents finalization between an import and its visibility.
        c.execute(text('SELECT pg_advisory_xact_lock(70612027)'))
        rows, frozen, start, end = _round(c, season.id, round_number)
        if action == 'reopen':
            c.execute(text('''DELETE FROM fantasy.manager_period_score s USING fantasy.matchup m
                WHERE s.matchup_id = m.id AND m.season_id = :season AND m.round_number = :round'''),
                {'season': season.id, 'round': round_number})
            return {'changed': bool(frozen), 'closed': False}
        if frozen:
            return {'changed': False, 'closed': True}
        if confirm_complete is not True:
            raise FantasyServiceError('Vérifie tous les résultats de la période, puis indique confirmer_complet:True. Les imports seuls ne prouvent pas leur complétude.')
        if c.execute(text('SELECT clock_timestamp()')).scalar_one() < end:
            raise FantasyServiceError('Le tour ne peut être clôturé avant la fin de sa période.')
        progress = _progress(c, season.id, start, end)
        if progress['imported'] != progress['calculated']:
            raise FantasyServiceError('Des parties importées ne sont pas calculées. Lance /fantasy calculate avant la clôture.')
        totals = _totals(c, season.id, start, end)
        for row in rows:
            for manager in (row['manager1_id'], row['manager2_id']):
                if manager is not None:
                    c.execute(text('INSERT INTO fantasy.manager_period_score (matchup_id, manager_id, score) VALUES (:match, :manager, :score)'),
                              {'match': row['id'], 'manager': manager, 'score': totals.get(manager, Decimal(0))})
        return {'changed': True, 'closed': True}


def view_round(*, league_id, guild_id, discord_user_id, round_number=None):
    with transaction() as c:
        c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        _, season, _ = _season_context(c, league_id, guild_id, discord_user_id)
        now = c.execute(text('SELECT clock_timestamp()')).scalar_one()
        if round_number is None:
            round_number = c.execute(text('''SELECT COALESCE(MIN(round_number) FILTER (WHERE ends_at > :now), MAX(round_number))
                FROM fantasy.matchup WHERE season_id = :season'''), {'now': now, 'season': season.id}).scalar_one()
        rows, frozen, start, end = _round(c, season.id, round_number)
        totals = {} if frozen else _totals(c, season.id, start, end)
        matches = []
        for row in rows:
            points = [None if mid is None else frozen.get((row['id'], mid), totals.get(mid, Decimal(0)))
                      for mid in (row['manager1_id'], row['manager2_id'])]
            matches.append({'user1': row['user1'], 'user2': row['user2'], 'score1': points[0], 'score2': points[1]})
        state = 'closed' if frozen else ('scheduled' if now < start else 'live' if now < end else 'awaiting_close')
        return {'round': round_number, 'start': start, 'end': end, 'state': state, 'matches': matches,
                **_progress(c, season.id, start, end)}


def ranking_rows(managers, finalized):
    """3 points per win, 1 per draw, no win/points-for advantage for a bye."""
    table = {mid: {'manager_id': mid, 'user': user, 'wins': 0, 'draws': 0, 'losses': 0,
                   'byes': 0, 'points': 0, 'for': Decimal(0), 'against': Decimal(0)} for mid, user in managers}
    for left, right, score1, score2 in finalized:
        if left is None or right is None:
            table[left if left is not None else right]['byes'] += 1
            continue
        for own, other, scored, conceded in ((left, right, score1, score2), (right, left, score2, score1)):
            row = table[own]
            row['for'] += scored
            row['against'] += conceded
            if scored == conceded:
                row['draws'] += 1
                row['points'] += 1
            elif scored > conceded:
                row['wins'] += 1
                row['points'] += 3
            else:
                row['losses'] += 1
    def key(row):
        return row['points'], row['for'] - row['against'], row['for']
    ordered = sorted(table.values(), key=lambda row: (*(-v for v in key(row)), row['manager_id']))
    previous, rank = None, 0
    for index, row in enumerate(ordered, 1):
        if key(row) != previous:
            rank = index
        previous = key(row)
        row['rank'] = rank
    return ordered


def league_ranking(*, league_id, guild_id, discord_user_id):
    with transaction() as c:
        c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        _, season, _ = _season_context(c, league_id, guild_id, discord_user_id)
        managers = c.execute(text('SELECT id, discord_user_id FROM fantasy.manager WHERE league_id = :league ORDER BY id'), {'league': league_id}).all()
        rounds = c.execute(text('SELECT DISTINCT round_number FROM fantasy.matchup WHERE season_id = :season ORDER BY round_number'), {'season': season.id}).scalars().all()
        finalized, closed, pending = [], 0, 0
        for number in rounds:
            rows, frozen, start, end = _round(c, season.id, number)
            if not frozen:
                continue
            closed += 1
            progress = _progress(c, season.id, start, end)
            pending += progress['imported'] - progress['calculated']
            for row in rows:
                left, right = row['manager1_id'], row['manager2_id']
                finalized.append((left, right, frozen.get((row['id'], left)), frozen.get((row['id'], right))))
        return {'rows': ranking_rows(managers, finalized), 'closed': closed, 'rounds': len(rounds), 'pending': pending}
