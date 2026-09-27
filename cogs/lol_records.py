"""Bouton persistant de consultation des records et prévisualisation sans API Riot.

Les interactions de pagination sont autonomes : un redémarrage du bot ne rend
pas les boutons des récapitulatifs publics inutilisables. Les réponses sont
éphémères et les snapshots sont propres au match et au compte suivi.
"""
import asyncio
import logging
import os
import re
import tempfile

import interactions
from interactions import (
    ActionRow,
    Button,
    ButtonStyle,
    ComponentContext,
    Extension,
    OptionType,
    SlashCommandChoice,
    SlashCommandOption,
    SlashContext,
    component_callback,
    slash_command,
)

from fonctions.match.records_display import (
    PERCENT_RECORDS,
    RECORD_LABELS,
    RecordEntry,
    RecordsCollector,
)
from fonctions.match.records_ui import (
    SCOPES,
    add_featured_records,
    build_record_pages,
    get_match_record_accounts,
    load_record_snapshot,
)

log = logging.getLogger(__name__)
RECORD_LOAD_TIMEOUT_SECONDS = 8

OPEN_RE = re.compile(r"^lolrec_open_([A-Z0-9]+_[0-9]+)_([0-9]+)$")
DEMO_OPEN_RE = re.compile(r"^lolrec_demo_open_([a-z0-9_]+)$")
PAGE_RE = re.compile(r"^lolrec_page_([rd])_([A-Za-z0-9_]+)_([0-9]+)_([0-9]+)$")

# Ces scénarios sont volontairement indépendants de Riot et de PostgreSQL.
DEMO_SCENARIOS = {
    "none": "0 record",
    "alltime": "1 record All-Time",
    "personal": "1 record personnel",
    "season": "1 record de saison",
    "alltime_personal": "1 statistique · All-Time + personnel",
    "all_scopes": "1 statistique · trois catégories",
    "tie": "Égalisations",
    "podium": "Podiums sans record absolu",
    "ten": "10 records distincts",
    "twenty_five": "25 records · pagination",
    "fifty": "50 records · pagination longue",
    "mixed": "Records multiples et catégories croisées",
}

DEMO_CATEGORIES = [
    "dmg_min", "tf_damage_window", "vision_score", "gold_min", "cs_min",
    "kills", "assists", "turret_plates_taken", "objectives_participated",
    "tf_clutches_won",
]


def demo_collector(scenario):
    """Construit des scénarios reproductibles, y compris les doublons de scopes."""
    if scenario not in DEMO_SCENARIOS:
        raise ValueError("Scénario de démonstration inconnu.")

    result = RecordsCollector()

    def add(scope, category, place=1, value=1250, previous=1100, tie=False):
        result.add(RecordEntry(
            scope=scope,
            place=place,
            category=category,
            value=float(value),
            old_record=float(previous),
            old_holder="Ancien détenteur (fictif)",
            old_champion="Ahri",
            is_tie=tie,
        ))

    if scenario == "none":
        return result
    if scenario == "alltime":
        add("alltime", "dmg_min")
    elif scenario == "personal":
        add("perso", "vision_score", value=92, previous=87)
    elif scenario == "season":
        add("general", "tf_damage_window", value=18400, previous=16800)
    elif scenario == "alltime_personal":
        add("alltime", "dmg_min")
        add("perso", "dmg_min", previous=980)
    elif scenario == "all_scopes":
        for scope, old in (("alltime", 1100), ("general", 1050), ("perso", 980)):
            add(scope, "dmg_min", previous=old)
    elif scenario == "tie":
        add("alltime", "dmg_min", tie=True, previous=1250)
        add("general", "vision_score", place=2, value=92, previous=92, tie=True)
    elif scenario == "podium":
        add("alltime", "dmg_min", place=2, value=1090, previous=1050)
        add("general", "vision_score", place=3, value=92, previous=85)
        add("perso", "cs_min", place=2, value=10.2, previous=9.8)
    elif scenario == "mixed":
        for category in DEMO_CATEGORIES[:7]:
            for index, scope in enumerate(SCOPES):
                add(scope, category, place=1 + index % 3,
                    value=1250 + index * 10, previous=1100 - index * 15)
    else:
        count = {"ten": 10, "twenty_five": 25, "fifty": 50}[scenario]
        categories = list(dict.fromkeys(DEMO_CATEGORIES + list(RECORD_LABELS)))
        for index, category in enumerate(categories[:count]):
            scope = SCOPES[index % len(SCOPES)]
            if category in PERCENT_RECORDS:
                value, previous = 60 + index % 25, 50 + index % 25
            else:
                value, previous = 800 + index * 37, 700 + index * 31
            add(scope, category, place=1 + index % 4,
                value=value, previous=previous)
    return result


def _normalize_match_id(value):
    value = str(value or "").strip().upper().replace("-", "_", 1)
    if value.isdecimal():
        return "EUW1_" + value
    if not re.fullmatch(r"[A-Z0-9]+_[0-9]+", value):
        raise ValueError("Utilise un ID comme EUW1_1234567890 ou son numéro seul.")
    return value


def _demo_embed(scenario, image_url=None):
    collector = demo_collector(scenario)
    embed = interactions.Embed(
        title=f"🧪 [DÉMO] Marin#TEST · Victoire RANKED (Jungle)",
        description=(
            "**Viego** · **12/3/9** · **32 min** · **+24 LP**\n"
            f"Scénario : **{DEMO_SCENARIOS[scenario]}**\n"
            "Toutes les données ci-dessous sont fictives."
        ),
        color=0x379C7A,
    )
    add_featured_records(embed, collector)
    embed.add_field(
        name="🎯 Objectifs",
        value="Premier dragon · 3 dragons · 1 Baron · 6 tours",
        inline=False,
    )
    embed.add_field(
        name="💡 Insights",
        value="3 ganks réussis · 68 % de participation aux kills · 92 de vision",
        inline=False,
    )
    if image_url:
        embed.set_image(url=image_url)
    embed.set_footer(text="DÉMO — aucun match créé, aucun résultat enregistré")
    return embed


def _demo_image():
    """Petit tableau de score fictif, autonome et sans accès au réseau."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1140, 430), (18, 24, 37))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 23)
        bold = ImageFont.truetype("arialbd.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
        bold = font

    draw.rounded_rectangle((14, 14, 1126, 416), radius=18, outline=(80, 100, 132), width=2)
    draw.text((38, 30), "MATCH FICTIF - APERCU BOTMARIN", font=bold, fill=(250, 204, 99))
    draw.text((40, 89), "EQUIPE BLEUE     38 / 26 / 67", font=font, fill=(100, 195, 255))
    draw.text((600, 89), "EQUIPE ROUGE     26 / 38 / 41", font=font, fill=(255, 130, 150))
    blue = [("Viego", "12/3/9", 245, 18400), ("Ahri", "8/6/14", 198, 13200),
            ("Jinx", "9/5/11", 212, 14000), ("Nautilus", "7/8/12", 101, 7100),
            ("Ornn", "2/4/21", 185, 8900)]
    red = [("Lee Sin", "4/8/6", 190, 12100), ("Syndra", "6/9/8", 215, 11400),
           ("Kai'Sa", "8/7/7", 221, 12600), ("Leona", "6/8/9", 87, 10800),
           ("Gnar", "2/6/11", 205, 7200)]
    for index, team in enumerate((blue, red)):
        left = 40 if index == 0 else 600
        for row, (champ, kda, cs, dmg) in enumerate(team):
            y = 137 + 48 * row
            draw.rounded_rectangle((left - 7, y - 4, left + 495, y + 37),
                                   radius=7, fill=(26, 46, 65) if index == 0 else (54, 33, 46))
            draw.text((left, y), champ, font=font, fill=(233, 239, 249))
            draw.text((left + 160, y), kda, font=font, fill=(228, 235, 245))
            draw.text((left + 265, y), str(cs), font=font, fill=(174, 194, 219))
            draw.text((left + 345, y), f"{dmg // 1000}.{dmg % 1000 // 100}k", font=font,
                      fill=(174, 194, 219))
    with tempfile.NamedTemporaryFile(
        prefix="marin_records_demo_", suffix=".png", delete=False
    ) as output:
        image.save(output, format="PNG")
        return output.name


def _demo_components(scenario):
    select = interactions.StringSelectMenu(
        *(
            interactions.StringSelectOption(label=label, value=key)
            for key, label in DEMO_SCENARIOS.items()
        ),
        custom_id="lolrec_demo_select",
        placeholder="Choisir un autre scénario fictif",
    )
    button = Button(
        style=ButtonStyle.PRIMARY,
        label="🏆 Voir tous les records",
        custom_id=f"lolrec_demo_open_{scenario}",
    )
    return [ActionRow(select), ActionRow(button)]


def _page_components(kind, key, joueur, pages, index):
    """Deux rangées (3 boutons de navigation et jusqu'à 4 accès rapides)."""
    token = f"{kind}_{key}_{joueur}"
    previous = Button(
        style=ButtonStyle.SECONDARY,
        label="◀ Précédent",
        custom_id=f"lolrec_page_{token}_{max(0, index - 1)}",
        disabled=index <= 0,
    )
    following = Button(
        style=ButtonStyle.PRIMARY,
        label="Suivant ▶",
        custom_id=f"lolrec_page_{token}_{min(index + 1, len(pages) - 1)}",
        disabled=index >= len(pages) - 1,
    )
    close = Button(
        style=ButtonStyle.DANGER, label="Fermer", custom_id="lolrec_close"
    )
    rows = [ActionRow(previous, following, close)]
    shortcuts = []
    for scope, label in (
        ("aperçu", "Aperçu"),
        ("alltime", "All-Time"),
        ("general", "Saison"),
        ("perso", "Personnel"),
    ):
        first_page = next((i for i, (kind_of_page, _) in enumerate(pages)
                           if kind_of_page == scope), None)
        if first_page is None:
            continue
        shortcuts.append(Button(
            style=ButtonStyle.SUCCESS if first_page == index else ButtonStyle.SECONDARY,
            label=label,
            custom_id=f"lolrec_page_{token}_{first_page}",
            disabled=first_page == index,
        ))
    if shortcuts:
        rows.append(ActionRow(*shortcuts))
    return rows


class LolRecords(Extension):
    def __init__(self, bot):
        self.bot = bot

    @slash_command(
        name="lol_records_demo",
        description="Tester le récap fictif et toutes les situations de records sans lancer de game",
        options=[SlashCommandOption(
            name="scenario",
            description="Choisir un cas de test (modifiable ensuite avec le menu)",
            type=OptionType.STRING,
            required=False,
            choices=[
                SlashCommandChoice(name=label, value=key)
                for key, label in DEMO_SCENARIOS.items()
            ],
        )],
    )
    async def lol_records_demo(self, ctx: SlashContext, scenario: str = "none"):
        if scenario not in DEMO_SCENARIOS:
            scenario = "none"
        image_path = _demo_image()
        try:
            embed = _demo_embed(scenario, f"attachment://{os.path.basename(image_path)}")
            await ctx.send(
                embeds=embed,
                files=interactions.File(image_path),
                components=_demo_components(scenario),
                ephemeral=True,
            )
        finally:
            os.unlink(image_path)

    @component_callback("lolrec_demo_select")
    async def on_demo_select(self, ctx: ComponentContext):
        scenario = ctx.values[0] if ctx.values else "none"
        if scenario not in DEMO_SCENARIOS:
            return await ctx.send("Scénario inconnu.", ephemeral=True)

        # Conserver l'image déjà jointe au message : pas de nouvelle pièce jointe
        # à chaque changement de scénario.
        image_url = None
        try:
            image_url = ctx.message.embeds[0].image.url
        except (AttributeError, IndexError, TypeError):
            pass
        await ctx.edit_origin(
            embeds=_demo_embed(scenario, image_url),
            components=_demo_components(scenario),
        )

    @component_callback(DEMO_OPEN_RE)
    async def on_demo_open(self, ctx: ComponentContext):
        matched = DEMO_OPEN_RE.fullmatch(ctx.custom_id)
        if not matched or matched.group(1) not in DEMO_SCENARIOS:
            return await ctx.send("Scénario inconnu.", ephemeral=True)
        # Même chemin d'acquittement que pour une vraie partie : le spinner
        # de Discord doit toujours être remplacé par une réponse terminale.
        await ctx.defer(ephemeral=True)
        scenario = matched.group(1)
        try:
            pages = build_record_pages(
                demo_collector(scenario), "EUW1_1234567890", "Marin#TEST", demo=True
            )
            await ctx.send(
                embeds=pages[0][1],
                components=_page_components("d", scenario, 0, pages, 0),
                ephemeral=True,
            )
        except Exception:
            log.exception("Ouverture des records de démonstration impossible")
            await ctx.send(
                "Impossible d'afficher les records fictifs. Consulte les logs du bot.",
                ephemeral=True,
            )

    @component_callback(OPEN_RE)
    async def on_real_open(self, ctx: ComponentContext):
        matched = OPEN_RE.fullmatch(ctx.custom_id)
        if not matched:
            return
        match_id, joueur = matched.groups()
        await ctx.defer(ephemeral=True)
        try:
            # Les accès SQL synchrones bloquaient la boucle asyncio. Au-delà
            # du délai, la réponse différée restait sur « réfléchit... ».
            collector = await asyncio.wait_for(
                asyncio.to_thread(load_record_snapshot, match_id, int(joueur)),
                timeout=RECORD_LOAD_TIMEOUT_SECONDS,
            )
            if collector is None:
                return await ctx.send(
                    "Le détail de cette partie n'est pas disponible. "
                    "Le snapshot doit être enregistré lors du récap.",
                    ephemeral=True,
                )
            pages = build_record_pages(collector, match_id)
            await ctx.send(
                embeds=pages[0][1],
                components=_page_components("r", match_id, joueur, pages, 0),
                ephemeral=True,
            )
        except asyncio.TimeoutError:
            log.warning("Timeout lecture du snapshot records %s / %s", match_id, joueur)
            await ctx.send(
                "La lecture des records prend trop de temps. Réessaie ou vérifie PostgreSQL.",
                ephemeral=True,
            )
        except Exception:
            log.exception("Ouverture des records impossible : %s / %s", match_id, joueur)
            await ctx.send(
                "Impossible d'afficher les records. L'erreur est enregistrée "
                "dans les logs du bot.",
                ephemeral=True,
            )

    @component_callback(PAGE_RE)
    async def on_page(self, ctx: ComponentContext):
        matched = PAGE_RE.fullmatch(ctx.custom_id)
        if not matched:
            return
        kind, key, joueur, target = matched.groups()
        # Modifier le message éphémère existant, et non créer un nouveau
        # message. L'ACK immédiat empêche Discord de rester bloqué si la
        # requête de records est lente.
        await ctx.defer(edit_origin=True)
        try:
            if kind == "d":
                collector = demo_collector(key)
                pages = build_record_pages(
                    collector, "EUW1_1234567890", "Marin#TEST", demo=True
                )
            else:
                collector = await asyncio.wait_for(
                    asyncio.to_thread(load_record_snapshot, key, int(joueur)),
                    timeout=RECORD_LOAD_TIMEOUT_SECONDS,
                )
                if collector is None:
                    return await ctx.edit_origin(
                        content="Le détail de ce match n'est plus disponible.",
                        embeds=[],
                        components=[],
                    )
                pages = build_record_pages(collector, key)
            target_page = max(0, min(int(target), len(pages) - 1))
            await ctx.edit_origin(
                embeds=pages[target_page][1],
                components=_page_components(kind, key, joueur, pages, target_page),
            )
        except asyncio.TimeoutError:
            log.warning("Timeout changement de page des records : %s", key)
            await ctx.edit_origin(
                content="PostgreSQL ne répond pas assez vite. "
                "Relance /match_records ou réessaie plus tard.",
                embeds=[],
                components=[],
            )
        except Exception:
            log.exception("Erreur lors de la pagination des records : %s", key)
            await ctx.edit_origin(
                content="Impossible de charger cette page. "
                "Le détail de l'erreur figure dans les logs du bot.",
                embeds=[],
                components=[],
            )

    @component_callback("lolrec_close")
    async def on_close(self, ctx: ComponentContext):
        await ctx.edit_origin(
            content="Consultation des records terminée.",
            embeds=[],
            components=[],
        )

    @slash_command(
        name="match_records",
        description="Consulter le détail enregistré des records d'un match LoL",
        options=[
            SlashCommandOption(
                name="match_id",
                description="Ex. EUW1_1234567890 ou numéro seul",
                type=OptionType.STRING,
                required=True,
            ),
            SlashCommandOption(
                name="riot_id",
                description="Facultatif si un seul compte suivi participe au match",
                type=OptionType.STRING,
                required=False,
            ),
            SlashCommandOption(
                name="riot_tag",
                description="Tag Riot, utile si plusieurs comptes portent le même nom",
                type=OptionType.STRING,
                required=False,
            ),
        ],
    )
    async def match_records(self, ctx: SlashContext, match_id: str,
                            riot_id: str = None, riot_tag: str = None):
        await ctx.defer(ephemeral=True)
        try:
            match_id = _normalize_match_id(match_id)
            accounts = await asyncio.wait_for(
                asyncio.to_thread(get_match_record_accounts, match_id),
                timeout=RECORD_LOAD_TIMEOUT_SECONDS,
            )
        except ValueError as error:
            return await ctx.send(str(error), ephemeral=True)
        except Exception:
            log.exception("Recherche des records sauvegardés impossible")
            return await ctx.send(
                "Records indisponibles : vérifie la migration match_records.",
                ephemeral=True,
            )

        if accounts.empty:
            return await ctx.send(
                f"Aucun snapshot pour {match_id}. Les anciens matchs ne sont "
                "pas recalculés automatiquement.",
                ephemeral=True,
            )
        if riot_id:
            accounts = accounts[
                accounts["riot_id"].fillna("").str.casefold() == riot_id.strip().casefold()
            ]
        if riot_tag:
            accounts = accounts[
                accounts["riot_tagline"].fillna("").str.casefold() == riot_tag.strip().casefold()
            ]
        if accounts.empty:
            return await ctx.send("Aucun compte correspondant pour ce match.", ephemeral=True)
        if len(accounts) > 1:
            labels = [
                f"• {row.get('riot_id') or 'Compte inconnu'}#{row.get('riot_tagline') or '?'}"
                for _, row in accounts.head(15).iterrows()
            ]
            return await ctx.send(
                "Plusieurs comptes suivis ont ce match. Précise riot_id "
                "et éventuellement riot_tag :\n" + "\n".join(labels),
                ephemeral=True,
            )

        account = accounts.iloc[0]
        try:
            collector = await asyncio.wait_for(
                asyncio.to_thread(
                    load_record_snapshot, match_id, int(account["joueur"])
                ),
                timeout=RECORD_LOAD_TIMEOUT_SECONDS,
            )
            if collector is None:
                return await ctx.send("Aucune donnée pour ce compte.", ephemeral=True)
            pages = build_record_pages(
                collector, match_id,
                player_name=f"{account.get('riot_id') or '?'}#{account.get('riot_tagline') or '?'}",
            )
            await ctx.send(
                embeds=pages[0][1],
                components=_page_components(
                    "r", match_id, int(account["joueur"]), pages, 0
                ),
                ephemeral=True,
            )
        except asyncio.TimeoutError:
            await ctx.send(
                "PostgreSQL prend trop de temps pour renvoyer ces records.",
                ephemeral=True,
            )
        except Exception:
            log.exception("Impossible de retrouver le snapshot de %s", match_id)
            await ctx.send("Impossible de charger ces records.", ephemeral=True)


def setup(bot):
    LolRecords(bot)
