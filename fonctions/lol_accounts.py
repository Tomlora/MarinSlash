"""Accès aux comptes du tracker depuis les commandes d'un serveur Discord."""
from sqlalchemy import column, select, table, text

from fonctions.gestion_bdd import engine


tracker = table("tracker", column("id_compte"), column("server_id"), column("discord"),
                column("riot_id"), column("riot_tagline"), column("puuid"), column("save_records"))


def _account(conn, guild_id, riot_id, riot_tag, owner_id=None):
    if guild_id is None:
        raise ValueError("Utilise cette commande sur un serveur Discord.")
    query = select(tracker).where(
        tracker.c.server_id == int(guild_id),
        tracker.c.riot_id == riot_id.lower().replace(" ", ""),
    )
    if riot_tag is not None:
        query = query.where(tracker.c.riot_tagline == riot_tag.strip().lstrip("#").upper())
    if owner_id is not None:
        # Garder le compte verrouillé jusqu'à la fin de la modification personnelle.
        query = query.with_for_update()
    accounts = conn.execute(query.limit(2)).mappings().all()
    if not accounts:
        raise ValueError("Compte introuvable sur ce serveur.")
    if len(accounts) > 1:
        raise ValueError("Plusieurs comptes portent ce Riot ID sur ce serveur, précise le tag.")
    account = accounts[0]
    if owner_id is not None and str(account["discord"]) != str(owner_id):
        raise ValueError("Seul le propriétaire de ce compte peut le modifier.")
    return account


def guild_account(guild_id, riot_id, riot_tag):
    with engine.connect() as conn:
        return _account(conn, guild_id, riot_id, riot_tag)


def set_recap_color(guild_id, owner_id, riot_id, riot_tag, red, green, blue):
    with engine.begin() as conn:
        account = _account(conn, guild_id, riot_id, riot_tag, int(owner_id))
        conn.execute(text('UPDATE tracker SET "R"=:red, "G"=:green, "B"=:blue WHERE id_compte=:account'),
                     {"account": account["id_compte"], "red": red, "green": green, "blue": blue})
    return account


def set_active_objective(guild_id, owner_id, riot_id, riot_tag, objective_id, value):
    """Remplace l'objectif actif, ou le retire si value vaut None."""
    with engine.begin() as conn:
        account = _account(conn, guild_id, riot_id, riot_tag, int(owner_id))
        params = {"account": account["id_compte"], "objective": objective_id}
        conn.execute(text("""DELETE FROM objectifs_lol_suivi
            WHERE id_compte=:account AND objectif_id=:objective AND match_id IS NULL"""), params)
        if value is not None:
            conn.execute(text("""INSERT INTO objectifs_lol_suivi
                (id_compte, objectif_id, valeur_attendue, match_id)
                VALUES (:account, :objective, :value, NULL)"""), {**params, "value": value})
