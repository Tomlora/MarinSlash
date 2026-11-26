"""Pronostics Worlds 2026 : /worlds et /worlds_admin."""
import asyncio
import logging
import os
import uuid

import interactions as ip
from interactions.ext.paginators import Paginator
from sqlalchemy import create_engine

from fonctions.worlds2026.domain import Fixture, WorldsError, timestamp, utcnow
from fonctions.worlds2026.service import Synchronizer
from fonctions.worlds2026.store import Store

log = logging.getLogger(__name__)
RULES = ("**Worlds 2026 — règles**\n"
         "BO1 : bon vainqueur = **1 point**.\n"
         "BO3 / BO5 : bon vainqueur = **1 point** ; score exact = **3 points au total**.\n"
         "Mauvais vainqueur = 0. Match annulé/forfait = aucun point.\n"
         "Pronostic modifiable jusqu'à la fermeture affichée ; jamais après.\n"
         "Le score suit l'ordre des équipes affichées dans /worlds matchs.\n"
         "Les pronostics personnels restent privés. Les égalités partagent le même rang.\n"
         "Inscription : /worlds inscription ; jouer : /worlds parier.")


def option(name, description, kind=ip.OptionType.STRING, **kwargs):
    return ip.SlashCommandOption(name=name, description=description, type=kind, **kwargs)


def match_option():
    return option("match_id", "Identifiant affiché par /worlds matchs", ip.OptionType.INTEGER, min_value=1)


def score_options():
    return [option("score1", "Victoires de la première équipe affichée", ip.OptionType.INTEGER, min_value=0, max_value=3),
            option("score2", "Victoires de la seconde équipe affichée", ip.OptionType.INTEGER, min_value=0, max_value=3)]


def pages(lines, title="Worlds 2026"):
    if isinstance(lines, str):
        lines = lines.splitlines()
    descriptions, chunk = [], ""
    for line in lines or ["Aucune donnée pour le moment."]:
        line = str(line)[:3000]
        if len(chunk) + len(line) + 1 > 3500:
            descriptions.append(chunk)
            chunk = ""
        chunk += line + "\n"
    if chunk:
        descriptions.append(chunk)
    return [ip.Embed(title=title, description=body, color=0xC8AA6E) for body in descriptions]


def match_lines(rows):
    labels = {"scheduled": "à venir", "running": "en cours", "finished": "terminé",
              "cancelled": "annulé", "disputed": "résultat à vérifier"}
    result = []
    for r in rows:
        state = labels[r["state"]]
        if r["state"] == "scheduled" and utcnow() >= r["lock_at"]:
            state = "verrouillé — résultat attendu"
        score = f" — **{r['score1']}-{r['score2']}**" if r["state"] == "finished" else ""
        result.append(f"**#{r['id']} · {r['team1']} / {r['team2']} · BO{r['best_of']}**{score}\n"
                      f"<t:{int(r['starts_at'])}:f> · {state} · source : {r['source']}\n"
                      f"Fermeture : <t:{int(r['lock_at'])}:f>")
    return result


class Worlds2026(ip.Extension):
    def __init__(self, bot):
        self.bot = bot
        self.store = None
        self.syncer = None
        self.init_lock = asyncio.Lock()

    async def ready(self):
        async with self.init_lock:
            if self.store is None:
                def initialize():
                    url = os.getenv("API_SQL")
                    if not url:
                        raise WorldsError("La connexion API_SQL n'est pas configurée.")
                    engine = create_engine(url, pool_pre_ping=True)
                    store = Store(engine)
                    try:
                        store.initialize()
                    except Exception:
                        engine.dispose()
                        raise
                    return store
                self.store = await asyncio.to_thread(initialize)
                self.syncer = Synchronizer(self.store)

    @ip.listen()
    async def on_startup(self):
        self.refresh.start()
        await self.refresh()

    def drop(self):
        self.refresh.stop()
        super().drop()

    @ip.Task.create(ip.IntervalTrigger(minutes=10))
    async def refresh(self):
        try:
            await self.ready()
            await self.syncer.automatic()
        except Exception:
            log.exception("Worlds 2026 : synchronisation automatique échouée")

    async def begin(self, ctx, admin=False, public=False):
        await ctx.defer(ephemeral=not public)
        if not ctx.guild_id:
            await ctx.send("Cette commande s'utilise dans un serveur Discord.")
            return False
        if admin and not ctx.author.has_permission(ip.Permissions.MANAGE_GUILD):
            await ctx.send("La permission Gérer le serveur est requise.")
            return False
        await self.ready()
        return True

    async def send_lines(self, ctx, lines):
        embeds = pages(lines)
        if len(embeds) == 1:
            await ctx.send(embeds=embeds[0], allowed_mentions=ip.AllowedMentions.none())
        else:
            await Paginator.create_from_embeds(self.bot, *embeds).send(ctx)

    async def execute(self, ctx, action, admin=False, public=False):
        try:
            if await self.begin(ctx, admin, public):
                result = await asyncio.to_thread(action, self.store)
                await self.send_lines(ctx, result or "Opération enregistrée.")
        except WorldsError as exc:
            await ctx.send(str(exc))
        except Exception:
            log.exception("Worlds 2026 : commande échouée")
            await ctx.send("Opération indisponible. Les données conservées restent intactes ; consulte les logs du bot.")

    @ip.slash_command(name="worlds", description="Pronostics Worlds 2026", dm_permission=False)
    async def worlds(self, ctx):
        pass

    @worlds.subcommand("regles", sub_cmd_description="Barème et fonctionnement des pronostics")
    async def rules(self, ctx):
        await self.execute(ctx, lambda store: RULES)

    @worlds.subcommand("inscription", sub_cmd_description="Participer aux pronostics Worlds 2026")
    async def register(self, ctx):
        def action(store):
            store.register(int(ctx.guild_id), int(ctx.author_id))
            return "Inscription enregistrée. Consulte /worlds matchs puis utilise /worlds parier."
        await self.execute(ctx, action)

    @worlds.subcommand("retrait", sub_cmd_description="Se retirer en conservant ses pronostics et ses points")
    async def withdraw(self, ctx):
        def action(store):
            store.register(int(ctx.guild_id), int(ctx.author_id), False)
            return "Participation désactivée. Historique et points conservés ; /worlds inscription pour revenir."
        await self.execute(ctx, action)

    @worlds.subcommand("participants", sub_cmd_description="Participants de ce serveur")
    async def participants(self, ctx):
        await self.execute(ctx, lambda store: [f"<@{r['user_id']}> — {'inscrit' if r['active'] else 'retiré'}"
                           for r in store.standings(int(ctx.guild_id))])

    @worlds.subcommand("equipes", sub_cmd_description="Équipes présentes dans le calendrier importé")
    async def teams(self, ctx):
        await self.execute(ctx, lambda store: sorted({r[k] for r in store.list_matches(int(ctx.guild_id))
                           for k in ("team1", "team2")}))

    @worlds.subcommand("matchs", sub_cmd_description="Calendrier, identifiants, horaires et résultats",
                      options=[option("tous", "Inclure les matchs terminés et annulés", ip.OptionType.BOOLEAN, required=False)])
    async def fixtures(self, ctx, tous=False):
        await self.execute(ctx, lambda store: match_lines([r for r in store.list_matches(int(ctx.guild_id))
                           if tous or r["state"] not in ("finished", "cancelled")]))

    @worlds.subcommand("parier", sub_cmd_description="Enregistrer ou modifier ton pronostic avant le match",
                      options=[match_option(), *score_options()])
    async def predict(self, ctx, match_id, score1, score2):
        def action(store):
            row = store.predict(int(ctx.guild_id), int(ctx.author_id), match_id, score1, score2)
            return f"Pronostic enregistré : **{row['team1']} {score1}–{score2} {row['team2']}** (match #{match_id})."
        await self.execute(ctx, action)

    @worlds.subcommand("mes_pronos", sub_cmd_description="Tes pronostics et leurs points, en privé")
    async def my_predictions(self, ctx):
        def action(store):
            result = []
            for r in store.predictions(int(ctx.guild_id), int(ctx.author_id)):
                label = f"{r['points']} point(s)" if r["points"] is not None else {
                    "cancelled": "annulé", "disputed": "points suspendus"}.get(r["state"], "en attente")
                result.append(f"#{r['match_id']} · {r['team1']} **{r['score1']}–{r['score2']}** {r['team2']} · {label}")
            return result
        await self.execute(ctx, action)

    @worlds.subcommand("classement", sub_cmd_description="Classement public de ce serveur")
    async def leaderboard(self, ctx):
        def action(store):
            lines, last_score, rank = [], None, 0
            for position, r in enumerate(store.standings(int(ctx.guild_id)), 1):
                if r["points"] != last_score:
                    rank, last_score = position, r["points"]
                lines.append(f"**{rank}.** <@{r['user_id']}> · **{r['points']} pts** · "
                             f"{r['correct']} vainqueur(s), {r['exact']} score(s) exact(s) BO3/5"
                             + (" · retiré" if not r["active"] else ""))
            return lines
        await self.execute(ctx, action, public=True)

    @ip.slash_command(name="worlds_admin", description="Administration des Worlds 2026", dm_permission=False,
                      default_member_permissions=ip.Permissions.MANAGE_GUILD)
    async def admin(self, ctx):
        pass

    @admin.subcommand("activer", sub_cmd_description="Activer les inscriptions et la synchronisation",
                      options=[option("actif", "Activer ou désactiver sans supprimer les données", ip.OptionType.BOOLEAN)])
    async def enable(self, ctx, actif):
        def action(store):
            store.configure(int(ctx.guild_id), actif, int(ctx.author_id))
            return "Activé. Lance /worlds_admin synchroniser pour remplir le calendrier." if actif else "Désactivé ; données conservées."
        await self.execute(ctx, action, admin=True)

    @admin.subcommand("synchroniser", sub_cmd_description="Récupérer calendrier et résultats (délai minimum 10 min)")
    async def synchronize(self, ctx):
        try:
            if await self.begin(ctx, admin=True):
                await self.send_lines(ctx, await self.syncer.run())
        except WorldsError as exc:
            await ctx.send(str(exc))
        except Exception:
            log.exception("Worlds 2026 : synchronisation manuelle échouée")
            await ctx.send("Synchronisation indisponible ; les données précédentes sont conservées.")

    @admin.subcommand("statut", sub_cmd_description="Santé des fournisseurs et dernières opérations administratives")
    async def status(self, ctx):
        def action(store):
            sources, events = store.status(int(ctx.guild_id))
            configured = {s.name for s in self.syncer.sources}
            lines = [f"{name} : non configuré" for name in ("lolesports", "pandascore") if name not in configured]
            for r in sources:
                last = f"<t:{int(r['success_at'])}:R>" if r["success_at"] else "jamais"
                lines.append(f"**{r['source']}** : {r['message']} · dernier succès : {last}")
            lines.append("**Dernières opérations**")
            lines.extend(f"<t:{int(r['at'])}:f> · {r['action']} · {r['detail'][:1800]}" for r in events)
            return lines
        await self.execute(ctx, action, admin=True)

    @admin.subcommand("ajouter", sub_cmd_description="Créer un match si les sources sont indisponibles",
                      options=[option("equipe1", "Première équipe", max_length=100),
                               option("equipe2", "Deuxième équipe", max_length=100),
                               option("debut", "Date ISO avec fuseau : 2026-10-23T19:00:00+02:00"),
                               option("bo", "Format de série", ip.OptionType.INTEGER,
                                      choices=[ip.SlashCommandChoice(name=f"BO{v}", value=v) for v in (1, 3, 5)])])
    async def add(self, ctx, equipe1, equipe2, debut, bo):
        def action(store):
            fixture = Fixture("manual", uuid.uuid4().hex, equipe1, equipe2, timestamp(debut), bo)
            match_id = store.manual_match(int(ctx.guild_id), fixture, int(ctx.author_id))
            return f"Match #{match_id} créé. Vérifie l'ordre des équipes dans /worlds matchs avant de parier."
        await self.execute(ctx, action, admin=True)

    @admin.subcommand("resultat", sub_cmd_description="Valider/corriger un résultat et recalculer les points",
                      options=[match_option(), *score_options(), option("raison", "Justification / source du résultat", max_length=500)])
    async def result(self, ctx, match_id, score1, score2, raison):
        await self.execute(ctx, lambda store: store.resolve(int(ctx.guild_id), match_id, "finished", score1, score2,
                           raison, int(ctx.author_id)), admin=True)

    @admin.subcommand("annuler", sub_cmd_description="Annuler un match et neutraliser ses points",
                      options=[match_option(), option("raison", "Justification de l'annulation", max_length=500)])
    async def cancel(self, ctx, match_id, raison):
        await self.execute(ctx, lambda store: store.resolve(int(ctx.guild_id), match_id, "cancelled", None, None,
                           raison, int(ctx.author_id)), admin=True)

    @admin.subcommand("horaire", sub_cmd_description="Corriger l'horaire sans rouvrir les paris déjà fermés",
                      options=[match_option(), option("debut", "Date ISO avec fuseau : 2026-10-23T19:00:00+02:00")])
    async def reschedule(self, ctx, match_id, debut):
        await self.execute(ctx, lambda store: store.reschedule(int(ctx.guild_id), match_id, timestamp(debut),
                           int(ctx.author_id)), admin=True)

    @admin.subcommand("associer", sub_cmd_description="Relier un identifiant fournisseur à un match ambigu",
                      options=[match_option(), option("source", "Fournisseur",
                               choices=[ip.SlashCommandChoice(name=s, value=s) for s in ("leaguepedia", "lolesports", "pandascore")]),
                               option("identifiant", "Identifiant exact du match chez le fournisseur", max_length=255)])
    async def associate(self, ctx, match_id, source, identifiant):
        await self.execute(ctx, lambda store: store.associate(int(ctx.guild_id), match_id, source, identifiant,
                           int(ctx.author_id)), admin=True)
