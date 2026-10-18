"""Stockage transactionnel PostgreSQL (SQLite pour les tests hors ligne).

Chaque écriture verrouille une ligne commune : synchronisation, fermeture et pari
ne peuvent pas se croiser, même entre deux processus. Les totaux sont dérivés,
jamais incrémentés lors d'une synchronisation.
"""
from contextlib import contextmanager
import json

from sqlalchemy import (BigInteger, Boolean, Column, Float, ForeignKey, Integer,
                        MetaData, String, Table, Text, select, update)

from .domain import Fixture, WorldsError, points, utcnow, validate_score

metadata = MetaData()
mutex = Table("worlds26_mutex", metadata, Column("id", Integer, primary_key=True),
              Column("version", Integer, nullable=False))
config = Table("worlds26_config", metadata,
               Column("guild", BigInteger, primary_key=True),
               Column("enabled", Boolean, nullable=False))
members = Table("worlds26_members", metadata,
                Column("guild", BigInteger, primary_key=True),
                Column("user_id", BigInteger, primary_key=True),
                Column("active", Boolean, nullable=False))
matches = Table("worlds26_matches", metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column("guild", BigInteger, nullable=False, index=True),
                Column("team1", String(100), nullable=False),
                Column("team2", String(100), nullable=False),
                Column("starts_at", Float, nullable=False),
                Column("lock_at", Float, nullable=False),
                Column("best_of", Integer, nullable=False),
                Column("state", String(20), nullable=False),
                Column("score1", Integer), Column("score2", Integer),
                Column("stage", String(150), nullable=False),
                Column("source", String(30), nullable=False),
                Column("manual", Boolean, nullable=False, default=False),
                Column("updated_at", Float, nullable=False))
aliases = Table("worlds26_sources", metadata,
                Column("guild", BigInteger, primary_key=True),
                Column("source", String(30), primary_key=True),
                Column("source_id", String(255), primary_key=True),
                Column("match_id", ForeignKey(matches.c.id), nullable=False))
bets = Table("worlds26_bets", metadata,
             Column("guild", BigInteger, primary_key=True),
             Column("user_id", BigInteger, primary_key=True),
             Column("match_id", ForeignKey(matches.c.id), primary_key=True),
             Column("score1", Integer, nullable=False),
             Column("score2", Integer, nullable=False),
             Column("submitted_at", Float, nullable=False))
health = Table("worlds26_health", metadata,
               Column("source", String(30), primary_key=True),
               Column("attempt_at", Float, nullable=False),
               Column("success_at", Float), Column("message", Text, nullable=False))
audit = Table("worlds26_audit", metadata,
              Column("id", Integer, primary_key=True, autoincrement=True),
              Column("guild", BigInteger, nullable=False),
              Column("actor", BigInteger), Column("at", Float, nullable=False),
              Column("action", String(40), nullable=False),
              Column("detail", Text, nullable=False))


class Store:
    def __init__(self, engine):
        self.engine = engine

    def initialize(self):
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            self._upsert(conn, mutex, {"id": 1, "version": 0}, ["id"], nothing=True)

    def _upsert(self, conn, table, values, keys, nothing=False):
        if self.engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif self.engine.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise RuntimeError("Worlds 2026 requiert PostgreSQL (ou SQLite pour les tests).")
        stmt = insert(table).values(**values)
        stmt = (stmt.on_conflict_do_nothing(index_elements=keys) if nothing else
                stmt.on_conflict_do_update(index_elements=keys, set_={
                    k: v for k, v in values.items() if k not in keys}))
        conn.execute(stmt)

    @contextmanager
    def transaction(self):
        with self.engine.begin() as conn:
            conn.execute(update(mutex).where(mutex.c.id == 1).values(version=mutex.c.version + 1))
            yield conn

    def _audit(self, conn, guild, action, detail, actor=None):
        conn.execute(audit.insert().values(guild=guild, actor=actor, at=utcnow(),
                     action=action, detail=json.dumps(detail, ensure_ascii=False, default=str)))

    def _enabled(self, conn, guild):
        if not conn.execute(select(config.c.enabled).where(config.c.guild == guild)).scalar():
            raise WorldsError("Les pronostics sont désactivés. Un administrateur doit utiliser /worlds_admin activer.")

    def enabled_guilds(self):
        with self.engine.connect() as conn:
            return list(conn.execute(select(config.c.guild).where(config.c.enabled.is_(True))).scalars())

    def configure(self, guild, enabled, actor):
        with self.transaction() as conn:
            self._upsert(conn, config, dict(guild=guild, enabled=enabled), ["guild"])
            self._audit(conn, guild, "configure", {"enabled": enabled}, actor)

    def register(self, guild, user_id, active=True):
        with self.transaction() as conn:
            self._enabled(conn, guild)
            self._upsert(conn, members, dict(guild=guild, user_id=user_id, active=active), ["guild", "user_id"])
            self._audit(conn, guild, "inscription" if active else "retrait", {}, user_id)

    def _match(self, conn, guild, match_id):
        row = conn.execute(select(matches).where(matches.c.id == match_id, matches.c.guild == guild)).mappings().first()
        if row is None:
            raise WorldsError("Match introuvable sur ce serveur.")
        return dict(row)

    def predict(self, guild, user_id, match_id, score1, score2):
        with self.transaction() as conn:
            self._enabled(conn, guild)
            if not conn.execute(select(members.c.active).where(members.c.guild == guild, members.c.user_id == user_id)).scalar():
                raise WorldsError("Inscris-toi d'abord avec /worlds inscription.")
            match = self._match(conn, guild, match_id)
            now = utcnow()  # Après acquisition du verrou, pas avant l'attente SQL.
            if match["state"] != "scheduled" or now >= match["lock_at"]:
                raise WorldsError("Pronostics fermés pour ce match.")
            validate_score(match["best_of"], score1, score2)
            self._upsert(conn, bets, dict(guild=guild, user_id=user_id, match_id=match_id,
                         score1=score1, score2=score2, submitted_at=now), ["guild", "user_id", "match_id"])
            self._audit(conn, guild, "pronostic", {"match": match_id, "score": [score1, score2]}, user_id)
            return match

    def list_matches(self, guild):
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(matches).where(matches.c.guild == guild)
                    .order_by(matches.c.starts_at, matches.c.id)).mappings()]

    def standings(self, guild):
        with self.engine.connect() as conn:
            roster = conn.execute(select(members).where(members.c.guild == guild)).mappings().all()
            predictions = self._predictions(conn, guild)
        totals = {r["user_id"]: dict(user_id=r["user_id"], active=r["active"], points=0,
                  correct=0, exact=0, settled=0) for r in roster}
        for row in predictions:
            total = totals[row["user_id"]]
            if row["points"] is not None:
                total["points"] += row["points"]
                total["correct"] += row["points"] > 0
                total["exact"] += row["points"] == 3
                total["settled"] += 1
        # Les égalités gardent le même rang ; l'identifiant stabilise seulement l'affichage.
        return sorted(totals.values(), key=lambda r: (-r["points"], r["user_id"]))

    def _predictions(self, conn, guild, user_id=None):
        query = select(bets, matches.c.team1, matches.c.team2, matches.c.best_of,
                       matches.c.state, matches.c.lock_at, matches.c.score1.label("result1"),
                       matches.c.score2.label("result2")).join(matches, bets.c.match_id == matches.c.id).where(bets.c.guild == guild)
        if user_id is not None:
            query = query.where(bets.c.user_id == user_id)
        rows = [dict(r) for r in conn.execute(query.order_by(matches.c.starts_at)).mappings()]
        for r in rows:
            r["points"] = None
            if r["state"] == "finished":
                r["points"] = (points(r["best_of"], (r["score1"], r["score2"]),
                               (r["result1"], r["result2"])) if r["submitted_at"] < r["lock_at"] else 0)
        return rows

    def predictions(self, guild, user_id):
        with self.engine.connect() as conn:
            return self._predictions(conn, guild, user_id)

    def _find(self, conn, guild, fixture):
        match_id = conn.execute(select(aliases.c.match_id).where(aliases.c.guild == guild,
                   aliases.c.source == fixture.source, aliases.c.source_id == fixture.source_id)).scalar()
        if match_id is not None:
            return self._match(conn, guild, match_id)
        rows = [dict(r) for r in conn.execute(select(matches).where(matches.c.guild == guild,
                matches.c.team1 == fixture.team1, matches.c.team2 == fixture.team2)).mappings()]
        near = [r for r in rows if abs(r["starts_at"] - fixture.starts_at) <= 12 * 3600]
        if len(near) == 1:
            already_mapped = conn.execute(select(aliases.c.source_id).where(
                aliases.c.guild == guild, aliases.c.source == fixture.source,
                aliases.c.match_id == near[0]["id"])).first()
            if already_mapped:
                raise WorldsError("Deux identifiants de la même source : association manuelle requise.")
            return near[0]
        if near or any(r["state"] not in ("finished", "cancelled") for r in rows):
            raise WorldsError("Rapprochement ambigu : utiliser /worlds_admin associer pour cette source.")
        return None

    def ingest(self, guild, fixtures):
        report = {"imported": 0, "errors": []}
        with self.transaction() as conn:
            self._enabled(conn, guild)
            for raw in fixtures:
                try:
                    fixture = raw.normalized()
                    old = self._find(conn, guild, fixture)
                    now = utcnow()
                    if fixture.state == "finished" and now < fixture.starts_at:
                        raise WorldsError("Résultat daté dans le futur : ignoré.")
                    values = {k: getattr(fixture, k) for k in (
                        "team1", "team2", "starts_at", "best_of", "state", "score1", "score2", "stage", "source")}
                    values.update(guild=guild, updated_at=now,
                                  lock_at=min(fixture.starts_at, now) if fixture.state != "scheduled" else fixture.starts_at)
                    if old:
                        match_id = old["id"]
                        self._upsert(conn, aliases, dict(guild=guild, source=fixture.source,
                                     source_id=fixture.source_id, match_id=match_id), ["guild", "source", "source_id"])
                        if old["manual"] or old["state"] == "disputed":
                            continue
                        if ((old["team1"], old["team2"], old["best_of"]) !=
                                (fixture.team1, fixture.team2, fixture.best_of)):
                            conn.execute(matches.update().where(matches.c.id == match_id).values(state="disputed"))
                            self._audit(conn, guild, "conflit_match", {"match": match_id, "source": fixture.source,
                                        "before": old, "incoming": values})
                            raise WorldsError(f"Match #{match_id} : équipes ou format modifiés ; contrôle manuel requis.")
                        if (old["state"] == "finished" and fixture.state in ("finished", "cancelled")
                                and (old["score1"], old["score2"], old["state"]) !=
                                (fixture.score1, fixture.score2, fixture.state)):
                            conn.execute(matches.update().where(matches.c.id == match_id).values(state="disputed"))
                            self._audit(conn, guild, "conflit_resultat", {"match": match_id, "source": fixture.source, "result": values})
                            raise WorldsError(f"Match #{match_id} : résultats contradictoires, points suspendus.")
                        # Un fournisseur en retard ne doit ni rouvrir ni effacer un résultat.
                        if old["state"] in ("finished", "cancelled"):
                            continue
                        if old["state"] == "running" and fixture.state == "scheduled":
                            continue
                        values["lock_at"] = min(old["lock_at"], values["lock_at"])
                        conn.execute(matches.update().where(matches.c.id == match_id).values(**values))
                    else:
                        match_id = conn.execute(matches.insert().values(**values, manual=False)).inserted_primary_key[0]
                        self._upsert(conn, aliases, dict(guild=guild, source=fixture.source,
                                     source_id=fixture.source_id, match_id=match_id), ["guild", "source", "source_id"])
                    report["imported"] += 1
                except WorldsError as exc:
                    report["errors"].append(f"{raw.source}/{raw.source_id}: {exc}")
            if report["errors"]:
                self._audit(conn, guild, "import_incomplet", report)
        return report

    def manual_match(self, guild, fixture, actor):
        fixture = fixture.normalized()
        with self.transaction() as conn:
            self._enabled(conn, guild)
            existing = self._find(conn, guild, fixture)
            if existing and existing["state"] != "cancelled":
                raise WorldsError("Ce match existe déjà. Utiliser son identifiant.")
            values = {k: getattr(fixture, k) for k in (
                "team1", "team2", "starts_at", "best_of", "state", "score1", "score2", "stage", "source")}
            match_id = conn.execute(matches.insert().values(**values, guild=guild,
                       lock_at=fixture.starts_at, updated_at=utcnow(), manual=False)).inserted_primary_key[0]
            self._audit(conn, guild, "ajout_match", {"match": match_id, **values}, actor)
            return match_id

    def resolve(self, guild, match_id, state, score1, score2, reason, actor):
        if not reason.strip():
            raise WorldsError("Une justification est obligatoire.")
        with self.transaction() as conn:
            old = self._match(conn, guild, match_id)
            if state == "finished":
                validate_score(old["best_of"], score1, score2)
                if utcnow() < old["lock_at"]:
                    raise WorldsError("Impossible de saisir un résultat avant la fermeture du match.")
            elif state != "cancelled":
                raise WorldsError("État administratif invalide.")
            else:
                score1 = score2 = None
            conn.execute(matches.update().where(matches.c.id == match_id).values(
                state=state, score1=score1, score2=score2, manual=True, source="manual", updated_at=utcnow()))
            self._audit(conn, guild, "resultat_manuel", {"before": old, "state": state,
                        "score": [score1, score2], "reason": reason}, actor)

    def reschedule(self, guild, match_id, starts_at, actor):
        with self.transaction() as conn:
            old = self._match(conn, guild, match_id)
            Fixture("manual", str(match_id), old["team1"], old["team2"], starts_at, old["best_of"]).normalized()
            if old["state"] != "scheduled":
                raise WorldsError("Seul un match à venir peut être replanifié.")
            conn.execute(matches.update().where(matches.c.id == match_id).values(
                starts_at=starts_at, lock_at=min(starts_at, old["lock_at"]), updated_at=utcnow()))
            self._audit(conn, guild, "horaire", {"match": match_id, "before": old["starts_at"], "after": starts_at}, actor)

    def associate(self, guild, match_id, source, source_id, actor):
        if source not in ("leaguepedia", "lolesports", "pandascore") or not source_id or len(source_id) > 255:
            raise WorldsError("Source ou identifiant invalide.")
        with self.transaction() as conn:
            self._match(conn, guild, match_id)
            existing = conn.execute(select(aliases.c.match_id).where(aliases.c.guild == guild,
                       aliases.c.source == source, aliases.c.source_id == source_id)).scalar()
            if existing is not None and existing != match_id:
                raise WorldsError("Cet identifiant est déjà associé à un autre match.")
            self._upsert(conn, aliases, dict(guild=guild, source=source, source_id=source_id,
                         match_id=match_id), ["guild", "source", "source_id"])
            self._audit(conn, guild, "association", {"match": match_id, "source": source, "source_id": source_id}, actor)

    def record_health(self, source, message, success=False):
        with self.transaction() as conn:
            values = dict(source=source, attempt_at=utcnow(), message=message[:4000])
            if success:
                values["success_at"] = utcnow()
            self._upsert(conn, health, values, ["source"])

    def status(self, guild):
        with self.engine.connect() as conn:
            sources = [dict(r) for r in conn.execute(select(health)).mappings()]
            events = [dict(r) for r in conn.execute(select(audit).where(audit.c.guild == guild,
                      audit.c.action != "pronostic").order_by(audit.c.id.desc()).limit(10)).mappings()]
            return sources, events
