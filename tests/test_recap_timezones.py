"""Compatibilité Windows/Python 3.10, sans dépendances pandas ni Discord."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfoNotFoundError

import pytest

from fonctions import recap_filters


@pytest.mark.parametrize('options', [
    {'observation_parties': 20, 'champion': 'Aphelios'},
    {'observation': '24h'}, {'observation': '48h'},
    {'observation': '72h'}, {'observation': '96h'},
    {'observation': 'Semaine'}, {'observation': 'Mois'}, {},
])
def test_count_and_rolling_duration_do_not_load_paris_timezone(monkeypatch, options):
    def unavailable_zone(key):
        raise ZoneInfoNotFoundError(key)
    monkeypatch.setattr(recap_filters, 'ZoneInfo', unavailable_zone)
    now = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
    _, params, _ = recap_filters.recap_query('Tomlora', 'EUW', mode='RANKED', now=now, **options)
    if 'observation_parties' in options:
        assert params['limit'] == 20
        assert 'date_start' not in params and 'date_end' not in params
    else:
        days = recap_filters.DURATION_DAYS[options.get('observation', '24h')]
        assert params['date_start'] == now - timedelta(days=days)
        assert params['date_end'] == now


def test_today_uses_packaged_tzdata_without_system_timezone_database():
    # Un processus neuf et un TZPATH vide forcent la lecture du paquet tzdata,
    # même si le système du développeur fournit déjà Europe/Paris.
    script = '''
from datetime import datetime, timezone
from zoneinfo import TZPATH, ZoneInfo
from fonctions.recap_filters import recap_query
assert not TZPATH
assert ZoneInfo('Europe/Paris').key == 'Europe/Paris'
for now, expected in [
    ('2026-10-11T12:00:00+00:00', '2026-10-10T22:00:00+00:00'),
    ('2026-03-29T12:00:00+00:00', '2026-03-28T23:00:00+00:00'),
    ('2026-10-25T12:00:00+00:00', '2026-10-24T22:00:00+00:00'),
]:
    _, params, _ = recap_query('Tomlora', 'EUW', observation='today',
                              now=datetime.fromisoformat(now))
    assert params['date_start'] == datetime.fromisoformat(expected), params
    assert params['date_end'] == datetime.fromisoformat(now), params
'''
    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, 'PYTHONTZPATH': ''},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
