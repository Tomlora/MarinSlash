"""Hub challenges et consultation persistante depuis les récaps MatchLoL."""
import asyncio
import logging
import re
import secrets
import time
from contextlib import asynccontextmanager

import interactions
from interactions import (Extension, SlashContext, ComponentContext, SlashCommandOption,
    SlashCommandChoice, slash_command, component_callback, listen, Task, TimeTrigger)

from fonctions import challenge_store as store
from fonctions.gestion_challenge import observe
from fonctions.challenge_progress import clean
from fonctions.challenge_ui import (COLOR, fmt, match_pages, profile_pages,
    pages_for_entries, finish, page_components)

log = logging.getLogger(__name__)
OPEN_RE = re.compile(r'lolchal_open_([A-Za-z0-9]+_[0-9]+)_([0-9]+)')
PAGE_RE = re.compile(r'lolchal_page_(match|session)_([A-Za-z0-9_]+)_([0-9]+)_([0-9]+)')


def player_options():
    return [SlashCommandOption(name='riot_id', description='Nom du compte suivi', type=3, required=True),
            SlashCommandOption(name='riot_tag', description='Tag si plusieurs comptes ont le même nom', type=3)]


def challenge_options(actions=False):
    options = [player_options()[0], SlashCommandOption(name='defi',
        description='Nom exact ou identifiant du défi (voir catalogue)', type=3, required=True)]
    if actions:
        options.append(SlashCommandOption(name='action', description='Préférence à modifier', type=3,
            required=True, choices=[SlashCommandChoice(name=k, value=k)
                for k in ('suivre', 'retirer', 'exclure', 'inclure')]))
    return options + [player_options()[1]]


async def db(function, *args, **kwargs):
    return await asyncio.wait_for(asyncio.to_thread(function, *args, **kwargs), timeout=10)


@asynccontextmanager
async def response(ctx):
    await ctx.defer(ephemeral=True)
    try:
        yield
    except ValueError as exc:
        await ctx.send(str(exc), ephemeral=True)
    except Exception:
        log.exception('Commande challenges indisponible')
        await ctx.send('Les challenges sont momentanément indisponibles. Réessaie dans un instant.', ephemeral=True)


class Challenges(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = {}

    @listen()
    async def on_startup(self):
        self.challenges_maj.start()

    @Task.create(TimeTrigger(hour=6, minute=0))
    async def challenges_maj(self):
        try:
            accounts = await db(store.accounts, daily=True)
        except Exception:
            log.exception('Lecture des comptes challenges impossible')
            return
        for account in accounts:
            try:
                # Les comptes suivis en live conservent leur référence entre deux matchs.
                await asyncio.wait_for(observe(account['id_compte'], account['puuid'],
                    initialize_only=bool(account['challenges'])), timeout=35)
            except Exception:
                log.exception('Mise à jour challenges impossible pour %s', account['id_compte'])
            await asyncio.sleep(2)

    async def account(self, ctx, riot_id=None, riot_tag=None, joueur=None):
        if not ctx.guild_id:
            raise ValueError('Utilise cette commande dans le serveur de ton compte suivi.')
        accounts = await db(store.accounts, int(ctx.guild_id))
        if joueur is not None:
            matches = [a for a in accounts if a['id_compte'] == int(joueur)]
        else:
            matches = [a for a in accounts if a['riot_id'].replace(' ', '').casefold() == riot_id.replace(' ', '').casefold()
                       and (not riot_tag or a['riot_tagline'].casefold() == riot_tag.casefold())]
        if not matches:
            raise ValueError('Compte introuvable sur ce serveur.')
        if len(matches) > 1:
            raise ValueError('Plusieurs comptes portent ce nom : précise riot_tag.')
        return matches[0]

    async def data(self, account):
        current, preferences = await db(store.profile, account['id_compte'])
        if current is None:
            await asyncio.wait_for(observe(account['id_compte'], account['puuid'], initialize_only=True), timeout=35)
            current, preferences = await db(store.profile, account['id_compte'])
        return current, preferences

    async def send_pages(self, ctx, pages):
        now = time.monotonic()
        self.sessions = {k: v for k, v in self.sessions.items() if v['expires'] > now}
        if len(self.sessions) >= 256:
            self.sessions.pop(next(iter(self.sessions)))
        key = secrets.token_hex(8)
        self.sessions[key] = {'pages': pages, 'author': int(ctx.author.id),
                              'guild': int(ctx.guild_id), 'expires': now + 900}
        await ctx.send(embeds=pages[0], components=page_components(key, 0, 0, len(pages), 'session'), ephemeral=True)

    async def show_profile(self, ctx, riot_id, riot_tag, view):
        async with response(ctx):
            account = await self.account(ctx, riot_id, riot_tag)
            current, preferences = await self.data(account)
            await self.send_pages(ctx, profile_pages(current, preferences,
                f"{account['riot_id']}#{account['riot_tagline']}", view))

    @slash_command(name='lol_challenges', description='Tes défis, objectifs et évolutions League of Legends', dm_permission=False)
    async def lol_challenges(self, ctx: SlashContext):
        pass

    @lol_challenges.subcommand('profil', sub_cmd_description='Points, catégories, favoris et objectifs', options=player_options())
    async def challenges_profil(self, ctx: SlashContext, riot_id: str, riot_tag: str = None):
        await self.show_profile(ctx, riot_id, riot_tag, 'profil')

    @lol_challenges.subcommand('objectifs', sub_cmd_description='Défis les plus proches du prochain palier', options=player_options())
    async def challenges_objectifs(self, ctx: SlashContext, riot_id: str, riot_tag: str = None):
        await self.show_profile(ctx, riot_id, riot_tag, 'objectifs')

    @lol_challenges.subcommand('best', sub_cmd_description='Tes meilleurs classements Riot', options=player_options())
    async def challenges_best(self, ctx: SlashContext, riot_id: str, riot_tag: str = None):
        await self.show_profile(ctx, riot_id, riot_tag, 'best')

    @lol_challenges.subcommand('catalogue', sub_cmd_description='Trouver un défi par son nom',
        options=player_options() + [SlashCommandOption(name='recherche', description='Mot dans le nom ou la description', type=3)])
    async def challenges_catalogue(self, ctx: SlashContext, riot_id: str, riot_tag: str = None, recherche: str = ''):
        async with response(ctx):
            account = await self.account(ctx, riot_id, riot_tag)
            current, _ = await self.data(account)
            entries = [e for e in current['entries'] if not e['aggregate'] and
                       recherche.casefold() in (e['name'] + ' ' + e['description']).casefold()]
            entries.sort(key=lambda e: e['name'].casefold())
            await self.send_pages(ctx, finish(pages_for_entries('🔎 Catalogue des défis',
                'Défis connus de ce compte · utilise le nom ou le numéro avec /lol_challenges suivre.', entries), 'Catalogue'))

    @lol_challenges.subcommand('suivre', sub_cmd_description='Choisir les favoris ou masquer un défi', options=challenge_options(True))
    async def challenges_suivre(self, ctx: SlashContext, riot_id: str, defi: str, action: str, riot_tag: str = None):
        async with response(ctx):
            account = await self.account(ctx, riot_id, riot_tag)
            if str(account['discord']) != str(ctx.author.id):
                raise ValueError('Seul le propriétaire du compte peut modifier ses défis.')
            current, _ = await self.data(account)
            found = [e for e in current['entries'] if str(e['id']) == defi.lstrip('#') or e['name'].casefold() == defi.casefold()]
            if len(found) != 1:
                raise ValueError('Défi introuvable ou nom ambigu. Utilise son numéro dans /lol_challenges catalogue.')
            entry = found[0]
            await db(store.set_preference, account['id_compte'], entry['id'], action)
            await ctx.send(f"Préférence **{action}** enregistrée pour **{entry['name']}**. "
                           'Elle s’applique aux prochains relevés ; les récaps sauvegardés restent inchangés.', ephemeral=True)

    @lol_challenges.subcommand('preferences', sub_cmd_description='Voir les favoris et les exclusions du compte', options=player_options())
    async def challenges_preferences(self, ctx: SlashContext, riot_id: str, riot_tag: str = None):
        async with response(ctx):
            account = await self.account(ctx, riot_id, riot_tag)
            current, preferences = await self.data(account)
            entries = {e['id']: e for e in current['entries']}
            pages = []
            for key, title in (('favorites', '⭐ Favoris'), ('excluded', '🙈 Défis masqués (dont exclusions globales)')):
                ids = sorted(set(preferences[key]))
                for start in range(0, max(1, len(ids)), 15):
                    lines = [f"**#{cid}** · {entries.get(cid, {}).get('name', 'Défi absent du dernier relevé')}"
                             for cid in ids[start:start + 15]]
                    pages.append(interactions.Embed(title=title, description='\n'.join(lines) or 'Aucun défi.', color=COLOR))
            await self.send_pages(ctx, finish(pages, 'Modifier avec /lol_challenges suivre'))

    @lol_challenges.subcommand('manage', sub_cmd_description='Exclusions globales (propriétaires du bot)',
        options=[SlashCommandOption(name='defi', description='Identifiant numérique du défi', type=4, required=True, min_value=1),
                 SlashCommandOption(name='action', description='Action globale', type=3, required=True,
                    choices=[SlashCommandChoice(name=k, value=k) for k in ('exclure', 'inclure')])])
    async def challenges_manage(self, ctx: SlashContext, defi: int, action: str):
        async with response(ctx):
            from fonctions.permissions import isOwner_slash
            if not await db(isOwner_slash, ctx):
                raise ValueError('Cette commande est réservée aux propriétaires du bot.')
            await db(store.set_preference, -1, defi, action)
            await ctx.send(f'Préférence globale **{action}** enregistrée pour le défi **#{defi}**.', ephemeral=True)

    @lol_challenges.subcommand('classement', sub_cmd_description='Les 20 meilleurs scores de challenges du serveur')
    async def challenges_classement(self, ctx: SlashContext):
        async with response(ctx):
            rows = await db(store.leaderboard, int(ctx.guild_id))
            lines = [f"**{i}. {clean(r['riot_id'], 40)}#{clean(r['riot_tagline'], 15)}** · {fmt(r['data']['total'].get('current'))} pts"
                     for i, r in enumerate(rows, 1)]
            embed = interactions.Embed(title='🏆 Challenges · Classement du serveur',
                description='\n'.join(lines) or 'Aucun relevé disponible. Consulte un profil pour initialiser son suivi.', color=COLOR)
            embed.set_footer(text='Dernier relevé de chaque compte · actualisation quotidienne ou après match')
            await ctx.send(embeds=embed, ephemeral=True)

    @lol_challenges.subcommand('historique', sub_cmd_description='Évolutions des 10 derniers récaps enregistrés', options=player_options())
    async def challenges_historique(self, ctx: SlashContext, riot_id: str, riot_tag: str = None):
        async with response(ctx):
            account = await self.account(ctx, riot_id, riot_tag)
            rows = await db(store.history, account['id_compte'])
            pages = []
            for match_id, snapshot in rows:
                pages.extend(match_pages(snapshot, match_id))
            if not pages:
                return await ctx.send('Aucune évolution sauvegardée. Active les challenges dans /lol_compte modifier_parametres.', ephemeral=True)
            await self.send_pages(ctx, finish(pages, 'Historique · compteurs Riot cumulés'))

    @lol_challenges.subcommand('help', sub_cmd_description='Comprendre le suivi et les nouvelles commandes')
    async def challenges_help(self, ctx: SlashContext):
        embed = interactions.Embed(title='✨ Ton espace Challenges', color=COLOR,
            description='Des objectifs concrets, des progrès visibles et un historique par récap.')
        embed.add_field(name='Explorer', value='`profil` : points et catégories\n`objectifs` : prochains paliers\n'
            '`catalogue` : rechercher un défi\n`best` : meilleurs rangs\n`classement` : classement du serveur', inline=False)
        embed.add_field(name='Personnaliser', value='`suivre` : favoris et exclusions de ton compte. '
            'Les anciennes exclusions sont conservées. Une exclusion globale reste prioritaire.', inline=False)
        embed.add_field(name='Après une partie', value='Active `tracker_challenges` dans `/lol_compte modifier_parametres`. '
            'Le bouton **Challenges** ouvre les évolutions en privé. `historique` retrouve les 10 derniers récaps. '
            'Un bouton grisé indique un relevé indisponible.', inline=False)
        embed.add_field(name='Ce que mesure le bot', value='Évolution depuis le dernier relevé, parfois sur plusieurs parties. '
            'Riot peut publier les mises à jour avec retard. Le premier relevé initialise la référence. '
            'Les profils affichent leur date de relevé ; une consultation ne consomme pas la progression.', inline=False)
        await ctx.send(embeds=embed, ephemeral=True)

    @component_callback(OPEN_RE)
    async def on_open(self, ctx: ComponentContext):
        matched = OPEN_RE.fullmatch(ctx.custom_id)
        if not matched:
            return
        match_id, joueur = matched.groups()
        async with response(ctx):
            await self.account(ctx, joueur=joueur)
            snapshot = await db(store.load_match, match_id, int(joueur))
            if snapshot is None:
                raise ValueError('Aucun relevé challenges enregistré pour cette partie.')
            pages = match_pages(snapshot, match_id)
            await ctx.send(embeds=pages[0], components=page_components(match_id, joueur, 0, len(pages)), ephemeral=True)

    @component_callback(PAGE_RE)
    async def on_page(self, ctx: ComponentContext):
        matched = PAGE_RE.fullmatch(ctx.custom_id)
        if not matched:
            return
        kind, key, joueur, target = matched.groups()
        await ctx.defer(edit_origin=True)
        try:
            if kind == 'session':
                session = self.sessions.get(key)
                if not session or session['expires'] <= time.monotonic():
                    raise ValueError('Cette consultation a expiré. Relance la commande.')
                if session['author'] != int(ctx.author.id) or session['guild'] != int(ctx.guild_id):
                    raise ValueError('Cette consultation appartient à un autre utilisateur.')
                pages = session['pages']
            else:
                await self.account(ctx, joueur=joueur)
                snapshot = await db(store.load_match, key, int(joueur))
                if snapshot is None:
                    raise ValueError('Le relevé de cette partie n’est plus disponible.')
                pages = match_pages(snapshot, key)
            page = max(0, min(int(target), len(pages) - 1))
            await ctx.edit_origin(embeds=pages[page], components=page_components(key, joueur, page, len(pages), kind))
        except ValueError as exc:
            await ctx.edit_origin(content=str(exc), embeds=[], components=[])
        except Exception:
            log.exception('Pagination challenges indisponible')
            await ctx.edit_origin(content='Impossible de charger cette page. Réouvre les challenges.', embeds=[], components=[])


def setup(bot):
    Challenges(bot)
