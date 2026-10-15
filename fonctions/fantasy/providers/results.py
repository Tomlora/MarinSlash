"""Strict modern Oracle's Elixir CSV adapter (duration in integer seconds)."""
from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from .oracles_elixir import (
    LEAGUE_MAP, ROLE_MAP, OE_DATA_URL_TEMPLATE, OracleElixirPlayerProvider,
    _parse_datetime, _player_external_id, _team_external_id,
)
from ..service import FantasyServiceError


class ResultImportError(FantasyServiceError):
    pass


def result_window(start, end):
    """UTC half-open interval, at most 31 days and one annual source file."""
    if not isinstance(start, datetime) or not isinstance(end, datetime) or start.tzinfo is None or end.tzinfo is None:
        raise ResultImportError('Utilise deux dates UTC avec fuseau horaire.')
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    if not timedelta(0) < end - start <= timedelta(days=31) or start.year != (end - timedelta(microseconds=1)).year:
        raise ResultImportError('La fenêtre doit couvrir au plus 31 jours dans une même année (fin exclue).')
    return start, end


def integer(row, key, maximum=100000):
    try:
        value = Decimal(str(row.get(key, '')).strip())
        if not value.is_finite() or value != value.to_integral_value() or not 0 <= value <= maximum:
            raise ValueError()
        return int(value)
    except (InvalidOperation, ValueError):
        raise ResultImportError(f'Statistique absente ou invalide : {key}.') from None


def _game(rows, competition, game_id, now):
    if len(rows) != 12:
        raise ResultImportError('Une partie doit contenir dix joueurs et deux équipes.')
    starts = {_parse_datetime(r.get('date', '')) for r in rows}
    durations = {integer(r, 'gamelength', 14400) for r in rows}
    if len(starts) != 1 or None in starts or len(durations) != 1 or 0 in durations:
        raise ResultImportError('Dates ou durées incohérentes dans une partie.')
    started, duration = starts.pop(), durations.pop()
    if started + timedelta(seconds=duration) > now:
        raise ResultImportError('Une partie future ou encore en cours ne peut pas être importée.')
    teams, players = [], []
    sides = defaultdict(list)
    for row in rows:
        if (row.get('datacompleteness') or '').strip().lower() != 'complete':
            raise ResultImportError('Une partie contient des données incomplètes.')
        side = (row.get('side') or '').strip().lower()
        if side not in ('blue', 'red') or not (row.get('teamname') or '').strip():
            raise ResultImportError('Côté ou équipe manquant.')
        team_id = _team_external_id(competition, row)
        won = integer(row, 'result', 1)
        sides[side].append((team_id, won))
        position = (row.get('position') or '').strip().lower()
        if position == 'team':
            teams.append(dict(external_id=team_id, name=row['teamname'].strip(), side=side,
                              won=bool(won), barons=integer(row, 'barons'), dragons=integer(row, 'dragons'),
                              towers=integer(row, 'towers'), first_blood=bool(integer(row, 'firstblood', 1))))
        else:
            role = ROLE_MAP.get(position)
            if role is None or not (row.get('playername') or '').strip():
                raise ResultImportError('Rôle ou joueur manquant.')
            players.append(dict(external_id=_player_external_id(competition, row), name=row['playername'].strip(),
                                team_external_id=team_id, side=side, role=role.value,
                                kills=integer(row, 'kills'), deaths=integer(row, 'deaths'),
                                assists=integer(row, 'assists'), cs=integer(row, 'total cs'),
                                triple_kills=integer(row, 'triplekills'), quadra_kills=integer(row, 'quadrakills'),
                                penta_kills=integer(row, 'pentakills')))
    if (len(teams) != 2 or len({t['external_id'] for t in teams}) != 2 or sum(t['won'] for t in teams) != 1
            or len({p['external_id'] for p in players}) != 10 or sum(t['first_blood'] for t in teams) > 1):
        raise ResultImportError('Participants ou vainqueur incohérents.')
    for side in ('blue', 'red'):
        if (len(sides[side]) != 6 or len(set(sides[side])) != 1
                or {p['role'] for p in players if p['side'] == side} != {'TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT'}
                or len([t for t in teams if t['side'] == side]) != 1):
            raise ResultImportError('Chaque côté doit contenir une équipe et cinq rôles distincts.')
    return dict(external_id=f'oe:{competition.value}:{started.year}:{game_id}', competition=competition.value,
                started_at=started.isoformat(), duration_seconds=duration,
                players=sorted(players, key=lambda p: p['external_id']), teams=sorted(teams, key=lambda t: t['external_id']))


def parse_results(path, *, start, end, now=None):
    start, end = result_window(start, end)
    grouped = defaultdict(list)
    with open(path, encoding='utf-8-sig', newline='') as source:
        reader = csv.DictReader(source)
        required = {'gameid', 'league', 'date', 'position', 'datacompleteness', 'side', 'playername', 'teamname',
                    'gamelength', 'result', 'kills', 'deaths', 'assists', 'total cs', 'triplekills',
                    'quadrakills', 'pentakills', 'barons', 'dragons', 'towers', 'firstblood'}
        if not required <= set(reader.fieldnames or []):
            raise ResultImportError('CSV Oracle\'s Elixir incompatible : colonnes de résultats manquantes.')
        for row in reader:
            competition = LEAGUE_MAP.get((row.get('league') or '').strip().upper())
            if competition is None:
                continue
            date_value = (row.get('date') or '').strip()
            if not re.match(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', date_value):
                raise ResultImportError('Heure de début absente : impossible de choisir le roster historique.')
            played = _parse_datetime(date_value)
            if played is None:
                raise ResultImportError('Date illisible dans le CSV.')
            if not start <= played < end:
                continue
            game_id = (row.get('gameid') or '').strip()
            if not game_id:
                raise ResultImportError('Identifiant de partie manquant.')
            grouped[(competition, game_id)].append(row)
            if len(grouped) > 1000 or len(grouped[(competition, game_id)]) > 12:
                raise ResultImportError('Import trop volumineux ou lignes dupliquées.')
    if not grouped:
        raise ResultImportError('Aucune partie complète dans cette fenêtre ; aucune donnée modifiée.')
    now = now or datetime.now(timezone.utc)
    return tuple(_game(rows, competition, game_id, now) for (competition, game_id), rows in sorted(grouped.items()))


async def fetch_results(start, end):
    start, end = result_window(start, end)
    provider = OracleElixirPlayerProvider(data_url=os.environ.get('FANTASY_OE_DATA_URL') or OE_DATA_URL_TEMPLATE.format(year=start.year))
    path = await provider._download()
    try:
        # Called on the dedicated sync worker, including parsing and persistence.
        return parse_results(path, start=start, end=end)
    finally:
        os.remove(path)
