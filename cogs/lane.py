import re

import interactions
import pandas as pd
from interactions import Extension, SlashCommandChoice, SlashCommandOption, SlashContext, slash_command

from fonctions.autocomplete import autocomplete_riotid
from fonctions.gestion_bdd import get_tag, lire_bdd_perso
from fonctions.match.lane_domination import (
    LANE_DOMINATION_VERSION,
    calculate_lane_domination_score,
    lane_domination_label,
    lane_domination_sql,
)
from utils.emoji import emote_champ_discord
from utils.params import Version, saison


ELIGIBLE_ROLES = {"TOP", "MID", "ADC"}


def _normalize_champion(champion: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(champion or "").lower())


_CHAMPION_EMOJIS = {
    _normalize_champion(champion): emoji
    for champion, emoji in emote_champ_discord.items()
}


def _champion_emoji(champion: str) -> str:
    return _CHAMPION_EMOJIS.get(_normalize_champion(champion), "")


def _champion_icon_url(champion: str) -> str | None:
    match = re.search(r"<a?:[^:]+:(\d+)>", _champion_emoji(champion))
    if match is None:
        return None
    return f"https://cdn.discordapp.com/emojis/{match.group(1)}.png?size=128&quality=lossless"


def _number(value, default=0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _signed(value, decimals=0) -> str:
    numeric = _number(value)
    if decimals == 0:
        return f"{int(round(numeric)):+d}"
    return f"{numeric:+.{decimals}f}"


def _game_options():
    return [
        SlashCommandOption(
            name="riot_id",
            description="Joueur",
            type=interactions.OptionType.STRING,
            required=True,
            autocomplete=True,
        ),
        SlashCommandOption(
            name="riot_tag",
            description="Tag Riot",
            type=interactions.OptionType.STRING,
            required=False,
        ),
        SlashCommandOption(
            name="numerogame",
            description="Numéro de la partie (0 = dernière partie enregistrée)",
            type=interactions.OptionType.INTEGER,
            required=False,
            min_value=0,
            max_value=100,
        ),
        SlashCommandOption(
            name="match_id",
            description="Match ID Riot (prioritaire sur numerogame)",
            type=interactions.OptionType.STRING,
            required=False,
        ),
    ]


def _record_options():
    choices = [
        SlashCommandChoice(name="Ranked", value="RANKED"),
        SlashCommandChoice(name="Flex", value="FLEX"),
        SlashCommandChoice(name="Swiftplay", value="SWIFTPLAY"),
    ]
    return [
        SlashCommandOption(
            name="mode",
            description="Mode de jeu",
            type=interactions.OptionType.STRING,
            required=False,
            choices=choices,
        ),
        SlashCommandOption(
            name="season",
            description="Saison (0 = toutes)",
            type=interactions.OptionType.INTEGER,
            required=False,
            min_value=0,
            max_value=99,
        ),
        SlashCommandOption(
            name="scope",
            description="Périmètre",
            type=interactions.OptionType.STRING,
            required=False,
            choices=[
                SlashCommandChoice(name="Serveur Discord", value="server"),
                SlashCommandChoice(name="Global", value="global"),
            ],
        ),
    ]


class LaneAnalysis(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @staticmethod
    def _resolve_account(riot_id: str, riot_tag: str | None) -> tuple[str, str]:
        riot_id = riot_id.lower().replace(" ", "")
        if riot_tag is None:
            riot_tag = get_tag(riot_id)
        return riot_id, riot_tag.upper()

    @staticmethod
    def _load_match(riot_id: str, riot_tag: str, numerogame: int, match_id: str | None):
        common_select = """
            SELECT
                matchs.match_id,
                matchs.id_participant,
                matchs.champion,
                matchs.mode,
                matchs.season,
                matchs.datetime,
                matchs.cs_max_avantage,
                matchs.level_max_avantage,
                matchs.solokills,
                mps.role,
                mps.gold_at_15,
                mps.cs_at_15,
                mps.gold_diff_15,
                mps.cs_diff_15
            FROM matchs
            INNER JOIN tracker ON tracker.id_compte = matchs.joueur
            LEFT JOIN match_player_scoring_data AS mps
                ON mps.match_id = matchs.match_id
               AND mps.player_index = matchs.id_participant
            WHERE LOWER(tracker.riot_id) = :riot_id
              AND UPPER(tracker.riot_tagline) = :riot_tag
        """
        params = {"riot_id": riot_id, "riot_tag": riot_tag}
        if match_id is not None and str(match_id).strip():
            requested = str(match_id).strip()
            params.update(
                {
                    "match_id": requested,
                    "match_id_without_prefix": requested.replace("EUW1_", ""),
                }
            )
            query = common_select + """
              AND (
                    CAST(matchs.match_id AS TEXT) = :match_id
                 OR CAST(matchs.match_id AS TEXT) = :match_id_without_prefix
              )
            LIMIT 1
            """
        else:
            params["offset"] = numerogame
            query = common_select + """
            ORDER BY matchs.datetime DESC, matchs.match_id DESC
            LIMIT 1 OFFSET :offset
            """
        df = lire_bdd_perso(query, index_col=None, params=params).T
        return None if df.empty else df.iloc[0].to_dict()

    @staticmethod
    def _history(riot_id: str, riot_tag: str, mode: str, season_filter: int):
        score_sql = lane_domination_sql("mps", "matchs")
        conditions = [
            "LOWER(tracker.riot_id) = :riot_id",
            "UPPER(tracker.riot_tagline) = :riot_tag",
            "matchs.mode = :mode",
            "matchs.time >= 15",
            "mps.role IN ('TOP', 'MID', 'ADC')",
        ]
        params = {"riot_id": riot_id, "riot_tag": riot_tag, "mode": mode}
        if season_filter != 0:
            conditions.append("matchs.season = :season")
            params["season"] = season_filter
        return lire_bdd_perso(
            f"""
            SELECT
                matchs.match_id,
                matchs.champion,
                matchs.victoire,
                mps.role,
                mps.gold_diff_15,
                mps.cs_diff_15,
                {score_sql} AS lane_domination_score
            FROM matchs
            INNER JOIN tracker ON tracker.id_compte = matchs.joueur
            INNER JOIN match_player_scoring_data AS mps
                ON mps.match_id = matchs.match_id
               AND mps.player_index = matchs.id_participant
            WHERE {' AND '.join(conditions)}
            """,
            index_col=None,
            params=params,
        ).T

    @slash_command(name="lane", description="Analyse de domination de lane")
    async def lane(self, ctx: SlashContext):
        pass

    @lane.subcommand("resume", sub_cmd_description="Analyse la lane d'une partie", options=_game_options())
    async def resume(self, ctx: SlashContext, riot_id: str, riot_tag: str = None, numerogame: int = 0, match_id: str = None):
        await ctx.defer(ephemeral=False)
        try:
            riot_id, riot_tag = self._resolve_account(riot_id, riot_tag)
        except (ValueError, KeyError, IndexError, AttributeError):
            return await ctx.send("Compte introuvable ou Riot ID ambigu. Précise le tag.")

        match = self._load_match(riot_id, riot_tag, numerogame, match_id)
        if match is None:
            return await ctx.send("Cette partie enregistrée est introuvable.")

        role = str(match.get("role") or "").upper()
        if role not in ELIGIBLE_ROLES:
            return await ctx.send(
                f"L'indice de domination de lane n'est pas calculé pour le rôle **{role or 'inconnu'}**. "
                "Il est réservé à TOP / MID / ADC pour éviter un score CS trompeur."
            )

        gold_diff = _number(match.get("gold_diff_15"))
        cs_diff = _number(match.get("cs_diff_15"))
        cs_peak = _number(match.get("cs_max_avantage"))
        level_peak = _number(match.get("level_max_avantage"))
        solo = _number(match.get("solokills"))
        score = calculate_lane_domination_score(gold_diff, cs_diff, cs_peak, level_peak, solo)
        label = lane_domination_label(score)
        champion = str(match.get("champion") or "?")

        embed = interactions.Embed(
            title=f"Lane — {riot_id.upper()} #{riot_tag} — {champion}",
            description=(
                f"Match ID · `{match['match_id']}`"
                if match_id
                else f"Partie #{numerogame} · `{match['match_id']}`"
            ),
            color=interactions.Color.random(),
        )
        icon = _champion_icon_url(champion)
        if icon:
            embed.set_thumbnail(url=icon)

        embed.add_field(
            name=f"Indice de domination — {score:.1f}/100",
            value=f"**{label}** · rôle **{role}**",
            inline=False,
        )
        embed.add_field(
            name="À 15 minutes",
            value=(
                f"💰 Gold diff **{_signed(gold_diff)}**\n"
                f"👻 CS diff **{_signed(cs_diff)}**\n"
                f"Stock personnel : **{int(_number(match.get('gold_at_15')))} gold** · **{int(_number(match.get('cs_at_15')))} CS**"
            ),
            inline=False,
        )
        embed.add_field(
            name="Signaux secondaires",
            value=(
                f"Pic CS **{_signed(cs_peak)}** · Pic niveau **{_signed(level_peak)}** · "
                f"Solokills **{int(solo)}**"
            ),
            inline=False,
        )

        history = self._history(riot_id, riot_tag, str(match.get("mode") or "RANKED"), int(match.get("season") or saison))
        if not history.empty:
            scores = pd.to_numeric(history["lane_domination_score"], errors="coerce").dropna()
            if not scores.empty:
                avg = scores.mean()
                percentile = 100.0 * (scores <= score).sum() / len(scores)
                gold_series = pd.to_numeric(history["gold_diff_15"], errors="coerce").dropna()
                lane_win = 100.0 * (gold_series > 0).sum() / len(gold_series) if len(gold_series) else 0.0
                embed.add_field(
                    name="Par rapport à son historique",
                    value=(
                        f"Score moyen **{avg:.1f}** · cette game est au **{percentile:.0f}e percentile**\n"
                        f"Avantage gold @15 sur **{lane_win:.0f}%** des {len(scores)} games analysées"
                    ),
                    inline=False,
                )

        embed.set_footer(text=f"Indice lane v{LANE_DOMINATION_VERSION} · Version {Version}")
        await ctx.send(embeds=embed)

    @lane.subcommand("records", sub_cmd_description="Records de domination de lane", options=_record_options())
    async def records(self, ctx: SlashContext, mode: str = "RANKED", season: int = saison, scope: str = "server"):
        await ctx.defer(ephemeral=False)
        mode = str(mode or "RANKED").upper()
        season = saison if season is None else int(season)
        scope = str(scope or "server").lower()

        conditions = [
            "tracker.banned = false",
            "tracker.save_records = true",
            "matchs.records = true",
            "matchs.mode = :mode",
            "matchs.time >= 15",
            "mps.role IN ('TOP', 'MID', 'ADC')",
        ]
        params = {"mode": mode}
        if season != 0:
            conditions.append("matchs.season = :season")
            params["season"] = season
        if scope == "server":
            conditions.append("tracker.server_id = :server_id")
            params["server_id"] = int(ctx.guild_id)

        score_sql = lane_domination_sql("mps", "matchs")
        df = lire_bdd_perso(
            f"""
            SELECT
                matchs.match_id,
                matchs.champion,
                matchs.url,
                matchs.season,
                tracker.riot_id,
                tracker.riot_tagline,
                mps.role,
                mps.gold_diff_15,
                mps.cs_diff_15,
                {score_sql} AS lane_domination_score
            FROM matchs
            INNER JOIN tracker ON tracker.id_compte = matchs.joueur
            INNER JOIN match_player_scoring_data AS mps
                ON mps.match_id = matchs.match_id
               AND mps.player_index = matchs.id_participant
            WHERE {' AND '.join(conditions)}
            """,
            index_col=None,
            params=params,
        ).T
        if df.empty:
            return await ctx.send("Aucune donnée de lane disponible pour ce périmètre.")

        title_scope = "serveur" if scope == "server" else "global"
        title_season = f"S{season}" if season != 0 else "toutes saisons"
        embed = interactions.Embed(
            title=f"Records lane — {mode} {title_season} — {title_scope}",
            color=interactions.Color.random(),
        )

        metrics = [
            ("lane_domination_score", "PLUS GROS INDICE DE DOMINATION", "score"),
            ("gold_diff_15", "PLUS GROS ÉCART GOLD @15", "gold"),
            ("cs_diff_15", "PLUS GROS ÉCART CS @15", "int"),
        ]
        for column, label, fmt in metrics:
            valid = df.copy()
            valid["_value"] = pd.to_numeric(valid[column], errors="coerce")
            valid = valid[valid["_value"].notna()]
            if valid.empty:
                continue
            best = valid["_value"].max()
            holders = valid[valid["_value"] == best].head(5)
            if fmt == "score":
                display = f"{best:.1f}/100"
            elif fmt == "gold":
                display = f"{int(best):+d} gold"
            else:
                display = f"{int(best):+d}"
            lines = []
            for _, row in holders.iterrows():
                champion = str(row.get("champion") or "?")
                lines.append(
                    f"{_champion_emoji(champion)} **{row.get('riot_id')} #{row.get('riot_tagline')}** · "
                    f"{champion} ({row.get('role')}) · `{row.get('match_id')}`"
                )
            embed.add_field(name=f"{label} — {display}", value="\n".join(lines), inline=False)

        embed.add_field(
            name="Lecture de l'indice",
            value="80+ domination totale · 70+ dominante · 60+ avantage net · 45–59 équilibrée · <45 en difficulté",
            inline=False,
        )
        embed.set_footer(text=f"Indice lane v{LANE_DOMINATION_VERSION} · Version {Version}")
        await ctx.send(embeds=embed)

    @resume.autocomplete("riot_id")
    async def autocomplete_resume(self, ctx: interactions.AutocompleteContext):
        await ctx.send(choices=await autocomplete_riotid(int(ctx.guild.id), ctx.input_text))
