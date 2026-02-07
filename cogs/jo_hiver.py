"""
Extension Discord pour le suivi des médailles des JO d'hiver 2026 (Milan-Cortina)

Récupère le tableau des médailles depuis Wikipedia et l'affiche dans un embed Discord.
Intégration avec le bot MatchLol (interactions.py).

Structure : cogs/olympics/jo_2026.py
Dépendances : pip install requests beautifulsoup4 pandas
"""

import interactions
from interactions import (
    Extension,
    slash_command,
    slash_option,
    SlashContext,
    OptionType,
    Embed,
    Button,
    ButtonStyle,
    ActionRow,
    component_callback,
    ComponentContext,
)
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
import re

# =============================================================================
# CONSTANTES
# =============================================================================

WIKI_URL = "https://en.wikipedia.org/wiki/2026_Winter_Olympics_medal_table"
OLYMPICS_URL = "https://www.olympics.com/en/milano-cortina-2026/medals"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Emojis médailles
MEDAL_EMOJIS = {"Or": "🥇", "Argent": "🥈", "Bronze": "🥉"}

# Drapeaux des pays (les plus courants aux JO d'hiver)
COUNTRY_FLAGS = {
    # Noms français
    "Norvège": "🇳🇴", "Allemagne": "🇩🇪", "États-Unis": "🇺🇸",
    "Suède": "🇸🇪", "Suisse": "🇨🇭", "Canada": "🇨🇦",
    "Autriche": "🇦🇹", "Pays-Bas": "🇳🇱", "Italie": "🇮🇹",
    "France": "🇫🇷", "Japon": "🇯🇵", "Corée du Sud": "🇰🇷",
    "Chine": "🇨🇳", "Finlande": "🇫🇮", "Russie": "🇷🇺",
    "République tchèque": "🇨🇿", "Slovénie": "🇸🇮",
    "Australie": "🇦🇺", "Nouvelle-Zélande": "🇳🇿",
    "Royaume-Uni": "🇬🇧", "Biélorussie": "🇧🇾",
    "Estonie": "🇪🇪", "Lettonie": "🇱🇻", "Lituanie": "🇱🇹",
    "Pologne": "🇵🇱", "Espagne": "🇪🇸", "Roumanie": "🇷🇴",
    "Slovaquie": "🇸🇰", "Croatie": "🇭🇷", "Belgique": "🇧🇪",
    "Danemark": "🇩🇰", "Ukraine": "🇺🇦", "Kazakhstan": "🇰🇿",
    "Géorgie": "🇬🇪",
    # Noms anglais (Wikipedia)
    "Norway": "🇳🇴", "Germany": "🇩🇪", "United States": "🇺🇸",
    "Sweden": "🇸🇪", "Switzerland": "🇨🇭", "Canada": "🇨🇦",
    "Austria": "🇦🇹", "Netherlands": "🇳🇱", "Italy": "🇮🇹",
    "France": "🇫🇷", "Japan": "🇯🇵", "South Korea": "🇰🇷",
    "China": "🇨🇳", "Finland": "🇫🇮", "Russia": "🇷🇺",
    "Czech Republic": "🇨🇿", "Czechia": "🇨🇿", "Slovenia": "🇸🇮",
    "Australia": "🇦🇺", "New Zealand": "🇳🇿",
    "Great Britain": "🇬🇧", "Belarus": "🇧🇾",
    "Estonia": "🇪🇪", "Latvia": "🇱🇻", "Lithuania": "🇱🇹",
    "Poland": "🇵🇱", "Spain": "🇪🇸", "Romania": "🇷🇴",
    "Slovakia": "🇸🇰", "Croatia": "🇭🇷", "Belgium": "🇧🇪",
    "Denmark": "🇩🇰", "Ukraine": "🇺🇦", "Kazakhstan": "🇰🇿",
    "Georgia": "🇬🇪",
}

# Traduction des noms de pays anglais → français
COUNTRY_TRANSLATION = {
    "Norway": "Norvège", "Germany": "Allemagne", "United States": "États-Unis",
    "Sweden": "Suède", "Switzerland": "Suisse", "Austria": "Autriche",
    "Netherlands": "Pays-Bas", "Italy": "Italie", "Japan": "Japon",
    "South Korea": "Corée du Sud", "China": "Chine", "Finland": "Finlande",
    "Russia": "Russie", "Czech Republic": "République tchèque",
    "Czechia": "République tchèque", "Slovenia": "Slovénie",
    "Australia": "Australie", "New Zealand": "Nouvelle-Zélande",
    "Great Britain": "Royaume-Uni", "Belarus": "Biélorussie",
    "Estonia": "Estonie", "Latvia": "Lettonie", "Lithuania": "Lituanie",
    "Poland": "Pologne", "Spain": "Espagne", "Romania": "Roumanie",
    "Slovakia": "Slovaquie", "Croatia": "Croatie", "Belgium": "Belgique",
    "Denmark": "Danemark", "Ukraine": "Ukraine", "Kazakhstan": "Kazakhstan",
    "Georgia": "Géorgie",
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MedalData:
    """Données de médailles d'un pays."""
    pays: str
    or_count: int = 0
    argent_count: int = 0
    bronze_count: int = 0

    @property
    def total(self) -> int:
        return self.or_count + self.argent_count + self.bronze_count

    @property
    def flag(self) -> str:
        return COUNTRY_FLAGS.get(self.pays, "🏳️")

    @property
    def pays_fr(self) -> str:
        return COUNTRY_TRANSLATION.get(self.pays, self.pays)

    @property
    def display_name(self) -> str:
        """Nom affiché avec drapeau."""
        return f"{self.flag} {self.pays_fr}"


@dataclass
class MedalTable:
    """Tableau complet des médailles."""
    countries: list[MedalData] = field(default_factory=list)
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def total_medals(self) -> int:
        return sum(c.total for c in self.countries)

    @property
    def total_countries(self) -> int:
        return len(self.countries)

    def sorted(self) -> list[MedalData]:
        """Tri par Or > Argent > Bronze."""
        return sorted(
            self.countries,
            key=lambda c: (c.or_count, c.argent_count, c.bronze_count),
            reverse=True,
        )


# =============================================================================
# FONCTIONS DE RÉCUPÉRATION DES DONNÉES
# =============================================================================

def fetch_medal_table_wikipedia() -> MedalTable:
    """Récupère le tableau des médailles depuis Wikipedia (BeautifulSoup)."""
    response = requests.get(WIKI_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table", class_="wikitable")

    medal_table = None
    for table in tables:
        header_text = table.get_text().lower()
        if "gold" in header_text and "silver" in header_text and "bronze" in header_text:
            medal_table = table
            break

    if medal_table is None:
        raise ValueError("Tableau des médailles introuvable.")

    rows = medal_table.find_all("tr")
    countries = []

    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 5:
            continue

        texts = [cell.get_text(strip=True) for cell in cells]

        if "total" in texts[0].lower():
            continue

        try:
            country_name = None
            numeric_values = []

            for cell in cells:
                text = cell.get_text(strip=True)
                if text.isdigit() and not country_name:
                    continue
                elif not text.replace(",", "").isdigit() and not country_name:
                    country_name = text.strip("* ")
                else:
                    numeric_values.append(
                        int(text.replace(",", "")) if text.replace(",", "").isdigit() else 0
                    )

            if country_name and len(numeric_values) >= 3:
                countries.append(MedalData(
                    pays=country_name,
                    or_count=numeric_values[0],
                    argent_count=numeric_values[1],
                    bronze_count=numeric_values[2],
                ))
        except (ValueError, IndexError):
            continue

    if not countries:
        raise ValueError("Aucune donnée de médailles trouvée.")

    return MedalTable(countries=countries, source="Wikipedia")


def fetch_medal_table_pandas() -> MedalTable:
    """Méthode alternative via pandas.read_html."""
    tables = pd.read_html(WIKI_URL, match="Gold|Or", header=0)

    if not tables:
        raise ValueError("Aucun tableau trouvé.")

    df = tables[0]

    rename_map = {}
    for col in df.columns:
        col_lower = str(col).lower()
        if "nation" in col_lower or "country" in col_lower or "noc" in col_lower:
            rename_map[col] = "Pays"
        elif "gold" in col_lower:
            rename_map[col] = "Or"
        elif "silver" in col_lower:
            rename_map[col] = "Argent"
        elif "bronze" in col_lower:
            rename_map[col] = "Bronze"

    df = df.rename(columns=rename_map)
    df = df[~df["Pays"].astype(str).str.contains("Total|total", na=False)]

    countries = []
    for _, row in df.iterrows():
        try:
            countries.append(MedalData(
                pays=str(row["Pays"]).strip("* "),
                or_count=int(row.get("Or", 0)),
                argent_count=int(row.get("Argent", 0)),
                bronze_count=int(row.get("Bronze", 0)),
            ))
        except (ValueError, KeyError):
            continue

    if not countries:
        raise ValueError("Aucune donnée extraite.")

    return MedalTable(countries=countries, source="Wikipedia (pandas)")


def get_medal_table() -> MedalTable:
    """
    Tente de récupérer les médailles avec plusieurs méthodes.
    Retourne le MedalTable ou lève une exception si tout échoue.
    """
    methods = [
        ("Wikipedia (BS4)", fetch_medal_table_wikipedia),
        ("Wikipedia (pandas)", fetch_medal_table_pandas),
    ]

    last_error = None
    for name, func in methods:
        try:
            table = func()
            table.source = name
            return table
        except Exception as e:
            last_error = e
            continue

    raise ValueError(
        f"Impossible de récupérer les données. "
        f"Les médailles n'ont peut-être pas encore été décernées. "
        f"Dernière erreur : {last_error}"
    )


# =============================================================================
# FONCTIONS D'AFFICHAGE
# =============================================================================

def build_medal_embed(table: MedalTable, page: int = 0, per_page: int = 15) -> Embed:
    """Construit un embed Discord avec le tableau des médailles."""

    sorted_countries = table.sorted()
    total_pages = max(1, (len(sorted_countries) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    start = page * per_page
    end = min(start + per_page, len(sorted_countries))
    page_countries = sorted_countries[start:end]

    embed = Embed(
        title="🏅 JO d'hiver 2026 — Milan-Cortina",
        description=f"**Tableau des médailles** • {table.total_countries} pays • {table.total_medals} médailles",
        color=0x0077B6,  # Bleu olympique
        timestamp=table.timestamp,
    )

    # Construction du tableau
    header = f"` # ` `{'Pays':<18}` `🥇` `🥈` `🥉` `Tot`"

    lines = [header, ""]
    for i, country in enumerate(page_countries):
        rank = start + i + 1
        rank_display = _rank_emoji(rank)

        line = (
            f"{rank_display} `{country.display_name:<18}` "
            f"`{country.or_count:>2}` `{country.argent_count:>2}` "
            f"`{country.bronze_count:>2}` `{country.total:>3}`"
        )
        lines.append(line)

    embed.add_field(
        name="\u200b",  # Champ invisible
        value="\n".join(lines),
        inline=False,
    )

    # Totaux
    total_or = sum(c.or_count for c in sorted_countries)
    total_argent = sum(c.argent_count for c in sorted_countries)
    total_bronze = sum(c.bronze_count for c in sorted_countries)

    embed.add_field(
        name="Total",
        value=f"🥇 {total_or}  •  🥈 {total_argent}  •  🥉 {total_bronze}  •  **{table.total_medals}**",
        inline=False,
    )

    embed.set_footer(
        text=f"Source : {table.source} • Page {page + 1}/{total_pages}"
    )

    embed.set_thumbnail(
        url="https://upload.wikimedia.org/wikipedia/fr/4/48/Logo_JO_d%27hiver_-_Milan_Cortina_2026.svg"
    )

    return embed


def build_country_embed(country: MedalData, rank: int, total_countries: int) -> Embed:
    """Construit un embed détaillé pour un pays."""
    embed = Embed(
        title=f"{country.display_name}",
        description=f"**Rang #{rank}** sur {total_countries} pays médaillés",
        color=_rank_color(rank),
    )

    # Barres visuelles
    max_val = max(country.or_count, country.argent_count, country.bronze_count, 1)

    def bar(val: int) -> str:
        width = int((val / max_val) * 10) if max_val > 0 else 0
        return "█" * width + "░" * (10 - width)

    medal_text = (
        f"🥇 Or      : **{country.or_count}** {bar(country.or_count)}\n"
        f"🥈 Argent  : **{country.argent_count}** {bar(country.argent_count)}\n"
        f"🥉 Bronze  : **{country.bronze_count}** {bar(country.bronze_count)}\n"
        f"\n**Total : {country.total}**"
    )

    embed.add_field(name="Médailles", value=medal_text, inline=False)
    embed.set_footer(text="JO d'hiver 2026 — Milan-Cortina")

    return embed


def _rank_emoji(rank: int) -> str:
    """Emoji de rang."""
    if rank == 1:
        return "🥇"
    elif rank == 2:
        return "🥈"
    elif rank == 3:
        return "🥉"
    else:
        return f"`{rank:>2}`"


def _rank_color(rank: int) -> int:
    """Couleur Discord selon le rang."""
    if rank == 1:
        return 0xFFD700  # Or
    elif rank == 2:
        return 0xC0C0C0  # Argent
    elif rank == 3:
        return 0xCD7F32  # Bronze
    elif rank <= 5:
        return 0x0077B6  # Bleu
    else:
        return 0x6C757D  # Gris


# =============================================================================
# EXTENSION DISCORD
# =============================================================================

class JO2026(Extension):
    """Extension pour le suivi des médailles des JO d'hiver 2026."""

    def __init__(self, bot):
        self.bot = bot
        self._cache: Optional[MedalTable] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = 300  # 5 minutes de cache

    def _get_cached_table(self) -> Optional[MedalTable]:
        """Retourne le cache s'il est encore valide."""
        if self._cache and self._cache_time:
            elapsed = (datetime.now() - self._cache_time).total_seconds()
            if elapsed < self._cache_ttl:
                return self._cache
        return None

    def _set_cache(self, table: MedalTable):
        """Met à jour le cache."""
        self._cache = table
        self._cache_time = datetime.now()

    async def _fetch_table(self) -> MedalTable:
        """Récupère le tableau (avec cache)."""
        cached = self._get_cached_table()
        if cached:
            return cached

        table = get_medal_table()
        self._set_cache(table)
        return table

    # =========================================================================
    # COMMANDE : /jo medals
    # =========================================================================

    @slash_command(
        name="jo",
        description="Jeux Olympiques d'hiver 2026",
        sub_cmd_name="medals",
        sub_cmd_description="Tableau des médailles par pays",
    )
    @slash_option(
        name="pays",
        description="Filtrer par pays (optionnel)",
        opt_type=OptionType.STRING,
        required=False,
    )
    async def jo_medals(self, ctx: SlashContext, pays: str = None):
        await ctx.defer()

        try:
            table = await self._fetch_table()
        except ValueError as e:
            embed = Embed(
                title="⚠️ JO d'hiver 2026",
                description=str(e),
                color=0xFF6B6B,
            )
            await ctx.send(embeds=embed)
            return

        if pays:
            # Recherche d'un pays spécifique
            pays_lower = pays.lower()
            sorted_countries = table.sorted()

            found = None
            rank = 0
            for i, c in enumerate(sorted_countries):
                if (
                    pays_lower in c.pays.lower()
                    or pays_lower in c.pays_fr.lower()
                ):
                    found = c
                    rank = i + 1
                    break

            if found:
                embed = build_country_embed(found, rank, table.total_countries)
                await ctx.send(embeds=embed)
            else:
                await ctx.send(
                    f"❌ Pays **{pays}** non trouvé dans le tableau des médailles.",
                    ephemeral=True,
                )
        else:
            # Tableau complet
            embed = build_medal_embed(table, page=0)

            # Boutons de pagination si > 15 pays
            if table.total_countries > 15:
                buttons = ActionRow(
                    Button(
                        style=ButtonStyle.SECONDARY,
                        label="◀ Précédent",
                        custom_id="jo_medals_prev_0",
                        disabled=True,
                    ),
                    Button(
                        style=ButtonStyle.SECONDARY,
                        label="Suivant ▶",
                        custom_id="jo_medals_next_0",
                    ),
                )
                await ctx.send(embeds=embed, components=[buttons])
            else:
                await ctx.send(embeds=embed)

    # =========================================================================
    # COMMANDE : /jo top
    # =========================================================================

    @slash_command(
        name="jo",
        description="Jeux Olympiques d'hiver 2026",
        sub_cmd_name="top",
        sub_cmd_description="Top N pays au tableau des médailles",
    )
    @slash_option(
        name="nombre",
        description="Nombre de pays à afficher (défaut: 10)",
        opt_type=OptionType.INTEGER,
        required=False,
        min_value=3,
        max_value=30,
    )
    @slash_option(
        name="tri",
        description="Trier par quel type de médaille",
        opt_type=OptionType.STRING,
        required=False,
        choices=[
            interactions.SlashCommandChoice(name="Or (défaut)", value="or"),
            interactions.SlashCommandChoice(name="Total", value="total"),
            interactions.SlashCommandChoice(name="Argent", value="argent"),
            interactions.SlashCommandChoice(name="Bronze", value="bronze"),
        ],
    )
    async def jo_top(self, ctx: SlashContext, nombre: int = 10, tri: str = "or"):
        await ctx.defer()

        try:
            table = await self._fetch_table()
        except ValueError as e:
            await ctx.send(f"⚠️ {e}", ephemeral=True)
            return

        # Tri personnalisé
        sort_keys = {
            "or": lambda c: (c.or_count, c.argent_count, c.bronze_count),
            "total": lambda c: (c.total, c.or_count, c.argent_count),
            "argent": lambda c: (c.argent_count, c.or_count, c.bronze_count),
            "bronze": lambda c: (c.bronze_count, c.or_count, c.argent_count),
        }

        sorted_countries = sorted(
            table.countries,
            key=sort_keys.get(tri, sort_keys["or"]),
            reverse=True,
        )[:nombre]

        tri_label = {"or": "🥇 Or", "total": "📊 Total", "argent": "🥈 Argent", "bronze": "🥉 Bronze"}

        embed = Embed(
            title=f"🏅 Top {nombre} — JO d'hiver 2026",
            description=f"Classement par {tri_label.get(tri, 'Or')}",
            color=0x0077B6,
            timestamp=table.timestamp,
        )

        lines = []
        for i, country in enumerate(sorted_countries):
            rank = _rank_emoji(i + 1)
            lines.append(
                f"{rank} {country.display_name} — "
                f"🥇 {country.or_count}  🥈 {country.argent_count}  "
                f"🥉 {country.bronze_count}  ({country.total})"
            )

        embed.add_field(name="\u200b", value="\n".join(lines), inline=False)
        embed.set_footer(text=f"Source : {table.source}")

        await ctx.send(embeds=embed)

    # =========================================================================
    # PAGINATION (boutons)
    # =========================================================================

    @component_callback(re.compile(r"jo_medals_(prev|next)_(\d+)"))
    async def on_medal_page(self, ctx: ComponentContext):
        match = re.match(r"jo_medals_(prev|next)_(\d+)", ctx.custom_id)
        if not match:
            return

        direction = match.group(1)
        current_page = int(match.group(2))
        new_page = current_page + (1 if direction == "next" else -1)

        try:
            table = await self._fetch_table()
        except ValueError:
            await ctx.send("⚠️ Erreur lors du chargement.", ephemeral=True)
            return

        total_pages = max(1, (table.total_countries + 14) // 15)
        new_page = max(0, min(new_page, total_pages - 1))

        embed = build_medal_embed(table, page=new_page)

        buttons = ActionRow(
            Button(
                style=ButtonStyle.SECONDARY,
                label="◀ Précédent",
                custom_id=f"jo_medals_prev_{new_page}",
                disabled=(new_page == 0),
            ),
            Button(
                style=ButtonStyle.SECONDARY,
                label="Suivant ▶",
                custom_id=f"jo_medals_next_{new_page}",
                disabled=(new_page >= total_pages - 1),
            ),
        )

        await ctx.edit_origin(embeds=embed, components=[buttons])


# =============================================================================
# SETUP
# =============================================================================

def setup(bot):
    JO2026(bot)
