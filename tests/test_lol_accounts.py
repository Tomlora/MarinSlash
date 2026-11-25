import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool


@pytest.fixture(params=["sqlite", "postgres"])
def store(request, monkeypatch):
    url = "sqlite://"
    if request.param == "postgres":
        url = os.environ.get("CHALLENGES_TEST_DATABASE_URL")
        if not url:
            pytest.skip("Base PostgreSQL de test non configurée")

    monkeypatch.setenv("API_SQL", "sqlite://")
    from fonctions import lol_accounts

    # Tables temporaires propres à cette connexion, même sur le service CI.
    database = create_engine(url, poolclass=StaticPool)
    monkeypatch.setattr(lol_accounts, "engine", database)
    with database.begin() as conn:
        conn.execute(text("""CREATE TEMP TABLE tracker (
            id_compte INT PRIMARY KEY, server_id BIGINT, discord TEXT, riot_id TEXT,
            riot_tagline TEXT, puuid TEXT UNIQUE, save_records BOOLEAN,
            "R" INT DEFAULT 0, "G" INT DEFAULT 0, "B" INT DEFAULT 0)"""))
        conn.execute(text("""CREATE TEMP TABLE objectifs_lol_suivi (
            id_compte INT, objectif_id INT, valeur_attendue INT CHECK (valeur_attendue >= 0),
            match_id TEXT)"""))
        conn.execute(text("""INSERT INTO tracker
            (id_compte, server_id, discord, riot_id, riot_tagline, puuid, save_records) VALUES
            (1, 10, '17', 'playerone', 'EUW', 'puuid-a', TRUE),
            (2, 20, '29', 'playerone', 'ALT', 'puuid-b', FALSE),
            (3, 20, '17', 'another', 'EUW', 'puuid-c', TRUE)"""))
        conn.execute(text("""INSERT INTO objectifs_lol_suivi VALUES
            (1, 1, 7, NULL), (1, 1, 6, 'match-a'), (2, 1, 5, NULL)"""))
    yield lol_accounts
    database.dispose()


def test_lookup_uses_only_local_tags_and_preserves_account_settings(store):
    assert store.guild_account(10, "Player One", None)["puuid"] == "puuid-a"
    assert not store.guild_account(20, "Player One", "#alt")["save_records"]
    with pytest.raises(ValueError, match="introuvable"):
        store.guild_account(10, "Player One", "ALT")
    with pytest.raises(ValueError, match="serveur Discord"):
        store.guild_account(None, "Player One", "EUW")
    with store.engine.begin() as conn:
        conn.execute(text("UPDATE tracker SET riot_id='playerone' WHERE id_compte=3"))
    with pytest.raises(ValueError, match="précise le tag"):
        store.guild_account(20, "Player One", None)


@pytest.mark.parametrize("guild, owner, tag", [(10, 29, "EUW"), (20, 17, "EUW")])
def test_personal_writes_refuse_other_members_and_other_guilds(store, guild, owner, tag):
    with pytest.raises(ValueError):
        store.set_recap_color(guild, owner, "playerone", tag, 1, 2, 3)
    for value in (9, None):
        with pytest.raises(ValueError):
            store.set_active_objective(guild, owner, "playerone", tag, 1, value)
    with store.engine.connect() as conn:
        assert conn.execute(text('SELECT SUM("R"+"G"+"B") FROM tracker')).scalar_one() == 0
        assert conn.execute(text("SELECT SUM(valeur_attendue) FROM objectifs_lol_suivi")).scalar_one() == 18


def test_owner_updates_only_active_goal_and_own_color(store):
    store.set_recap_color(10, 17, "Player One", None, 2, 3, 4)
    store.set_active_objective(10, 17, "Player One", None, 1, 9)
    with pytest.raises(IntegrityError):
        store.set_active_objective(10, 17, "Player One", "EUW", 1, -1)
    with store.engine.connect() as conn:
        assert conn.execute(text('SELECT "R","G","B" FROM tracker ORDER BY id_compte')).all() == [
            (2, 3, 4), (0, 0, 0), (0, 0, 0)]
        assert conn.execute(text("""SELECT valeur_attendue FROM objectifs_lol_suivi
            WHERE id_compte=1 AND match_id IS NULL""")).scalar_one() == 9
    store.set_active_objective(10, 17, "Player One", None, 1, None)
    with store.engine.connect() as conn:
        assert conn.execute(text("""SELECT id_compte, valeur_attendue, match_id
            FROM objectifs_lol_suivi ORDER BY id_compte""")).all() == [(1, 6, "match-a"), (2, 5, None)]
