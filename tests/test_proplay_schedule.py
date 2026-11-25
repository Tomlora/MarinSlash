import asyncio
from datetime import date, datetime
from functools import partial
from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest
from sqlalchemy import create_engine

from cogs import lol_proplay as cog
from fonctions import proplay_schedule as schedule


@pytest.fixture
def job(monkeypatch):
    # Le marqueur persiste entre deux instances du cog, comme après un redémarrage.
    db = create_engine("sqlite://")
    with db.begin() as conn:
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS public")
    monkeypatch.setattr(schedule, "engine", db)

    clock = Mock()
    clock.now.side_effect = lambda zone: datetime(2026, 11, 25, 9, tzinfo=zone)
    monkeypatch.setattr(cog, "datetime", clock)
    monkeypatch.setattr(cog, "create_proplay_backup", Mock())
    existing = pd.DataFrame([{"plug": "Caps", "role": "Mid"}]).set_index("plug")
    monkeypatch.setattr(cog, "lire_bdd_perso", Mock(return_value=existing.T))
    monkeypatch.setattr(cog, "sauvegarde_bdd", Mock())
    monkeypatch.setattr(cog.LoLProplay, "_read_optional_table", Mock(return_value=pd.DataFrame()))
    league = pd.DataFrame([{"plug": "Caps", "Rôle": "Mid", "team_plug": "G2"}])
    monkeypatch.setattr(cog, "fetch_leaguepedia_players", AsyncMock(return_value=league))
    monkeypatch.setattr(cog, "fetch_trackingthepros_players", AsyncMock(return_value=pd.DataFrame()))
    monkeypatch.setattr(cog, "fetch_lolpros_accounts_for_players",
                        AsyncMock(return_value=(pd.DataFrame(), pd.DataFrame())))

    def new_instance():
        instance = object.__new__(cog.LoLProplay)
        instance._pro_update_lock = asyncio.Lock()
        return instance

    yield new_instance
    db.dispose()


def test_wednesday_catchup_survives_restart_and_manual_refresh(job):
    async def run():
        for _ in range(2):
            instance = job()
            tick = AsyncMock(side_effect=partial(cog.LoLProplay.update_pro_database.callback, instance))
            tick.start = Mock()
            instance.update_pro_database = tick
            await cog.LoLProplay.on_startup.callback(instance)
            tick.start.assert_called_once_with()
            tick.assert_awaited_once_with()
        assert cog.create_proplay_backup.call_count == 1
        assert schedule.is_proplay_week_complete(date(2026, 11, 23))
        await job()._run_pro_database_update(trigger="manuel")
        assert cog.create_proplay_backup.call_count == 2

        cog.datetime.now.side_effect = lambda zone: datetime(2026, 11, 30, tzinfo=zone)
        await job()._run_pro_database_update(trigger="hebdo")
        assert cog.create_proplay_backup.call_count == 3
        assert schedule.is_proplay_week_complete(date(2026, 11, 30))

    asyncio.run(run())


def test_failed_or_empty_run_remains_due(job):
    async def run():
        instance = job()
        cog.create_proplay_backup.side_effect = RuntimeError("backup")
        await instance._run_pro_database_update(trigger="hebdo")
        cog.fetch_leaguepedia_players.assert_not_awaited()
        cog.create_proplay_backup.side_effect = None

        cog.sauvegarde_bdd.side_effect = RuntimeError("write")
        with pytest.raises(RuntimeError, match="write"):
            await instance._run_pro_database_update(trigger="hebdo")
        cog.sauvegarde_bdd.side_effect = None
        cog.fetch_leaguepedia_players.return_value = pd.DataFrame()
        await instance._run_pro_database_update(trigger="hebdo")
        assert not schedule.is_proplay_week_complete(date(2026, 11, 23))

        profiles = pd.DataFrame([{"joueur": "Caps", "role": "Mid"}])
        cog.fetch_lolpros_accounts_for_players.return_value = (pd.DataFrame(), profiles)
        await instance._run_pro_database_update(trigger="hebdo")
        assert schedule.is_proplay_week_complete(date(2026, 11, 23))

    asyncio.run(run())
