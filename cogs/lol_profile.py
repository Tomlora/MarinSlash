import re

import interactions
import pandas as pd
from interactions import Extension, SlashCommandChoice, SlashCommandOption, SlashContext, slash_command

from fonctions.autocomplete import autocomplete_riotid
from fonctions.gestion_bdd import get_tag, lire_bdd_perso
from fonctions.match.lane_domination import lane_domination_sql
from utils.emoji import emote_champ_discord
from utils.params import Version, saison


ROLE_TO_LANE = {
    "TOP": "top",
    "MID": "mid",
    "ADC": "bot",
    "SUPPORT": "bot",
}


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


def _num(value, default=0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value) -> int:
    return int(round(_num(value)))


def _pct(value, decimals=0) -> str:
    return f"{_num(value):.{decimals}f}%"


def _signed(value, suffix="") -> str:
    return f"{_int(value):+d}{suffix}"


def _profile_options():
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
            name="mode",
            description="Mode analysé",
            type=interactions.OptionType.STRING,
            required=False,
            choices=[
                SlashCommandChoice(name="Ranked", value="RANKED"),
                SlashCommandChoice(name="Flex", value="FLEX"),
                SlashCommandChoice(name="Swiftplay", value="SWIFTPLAY"),
                SlashCommandChoice(name="ARAM", value="ARAM"),
            ],
        ),
        SlashCommandOption(
            name="season",
            description="Saison (0 = toutes)",
            type=interactions.OptionType.INTEGER,
            required=False,
            min_value=0,
            max_value=99,
        ),
    ]


class LolProfile(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @staticmethod
    def _resolve_account(riot_id: str, riot_tag: str | None) -> tuple[str, str]:
        riot_id = riot_id.lower().replace(" ", "")
        if riot_tag is None:
            riot_tag = get_tag(riot_id)
        return riot_id, riot_tag.upper()

    @staticmethod
    def _conditions(season_filter: int):
        conditions = [
            "LOWER(tracker.riot_id) = :riot_id",
            "UPPER(tracker.riot_tagline) = :riot_tag",
            "matchs.mode = :mode",
            "matchs.time >= :min_time",
        ]
        if season_filter != 0:
            conditions.append("matchs.season = :season")
        return conditions

    @staticmethod
    def _params(riot_id: str, riot_tag: str, mode: str, season_filter: int):
        params = {
            "riot_id": riot_id,
            "riot_tag": riot_tag,
            "mode": mode,
            "min_time": 10 if mode == "ARAM" else 15,
        }
        if season_filter != 0:
            params["season"] = season_filter
        return params

    @classmethod
    def _core_stats(cls, riot_id: str, riot_tag: str, mode: str, season_filter: int):
        conditions = cls._conditions(season_filter)
        params = cls._params(riot_id, riot_tag, mode, season_filter)
        df = lire_bdd_perso(
            f"""
            SELECT
                COUNT(*) AS games,
                SUM(CASE WHEN matchs.victoire = true THEN 1 ELSE 0 END) AS wins,
                AVG(matchs.kills) AS avg_kills,
                AVG(matchs.deaths) AS avg_deaths,
                AVG(matchs.assists) AS avg_assists,
                AVG(matchs.kda) AS avg_kda,
                AVG(matchs.kp) AS avg_kp,
                AVG(matchs.dmg_min) AS avg_dpm,
                AVG(matchs.cs_min) AS avg_cs_min,
                AVG(matchs.gold_min) AS avg_gpm,
                AVG(matchs.vision_min) AS avg_vision_min
            FROM matchs
            INNER JOIN tracker ON tracker.id_compte = matchs.joueur
            WHERE {' AND '.join(conditions)}
            """,
            index_col=None,
            params=params,
        ).T
        return None if df.empty else df.iloc[0].to_dict()

    @classmethod
    def _role_stats(cls, riot_id: str, riot_tag: str, mode: str, season_filter: int):
        conditions = cls._conditions(season_filter)
        params = cls._params(riot_id, riot_tag, mode, season_filter)
        return lire_bdd_perso(
            f"""
            SELECT
                COALESCE(mps.role, matchs.role) AS role,
                COUNT(*) AS games
            FROM matchs
            INNER JOIN tracker ON tracker.id_compte = matchs.joueur
            LEFT JOIN match_player_scoring_data AS mps
                ON mps.match_id = matchs.match_id
               AND mps.player_index = matchs.id_participant
            WHERE {' AND '.join(conditions)}
            GROUP BY COALESCE(mps.role, matchs.role)
            ORDER BY games DESC
            """,
            index_col=None,
            params=params,
        ).T

    @classmethod
    def _champions(cls, riot_id: str, riot_tag: str, mode: str, season_filter: int):
        conditions = cls._conditions(season_filter)
        params = cls._params(riot_id, riot_tag, mode, season_filter)
        return lire_bdd_perso(
            f"""
            SELECT
                matchs.champion,
                COUNT(*) AS games,
                100.0 * SUM(CASE WHEN matchs.victoire = true THEN 1 ELSE 0 END) / COUNT(*) AS winrate,
                AVG(matchs.kda) AS avg_kda,
                AVG(matchs.dmg_min) AS avg_dpm,
                AVG(matchs.cs_min) AS avg_cs_min
            FROM matchs
            INNER JOIN tracker ON tracker.id_compte = matchs.joueur
            WHERE {' AND '.join(conditions)}
            GROUP BY matchs.champion
            ORDER BY games DESC, winrate DESC
            LIMIT 5
            """,
            index_col=None,
            params=params,
        ).T

    @classmethod
    def _scoring_stats(cls, riot_id: str, riot_tag: str, mode: str, season_filter: int):
        conditions = cls._conditions(season_filter)
        params = cls._params(riot_id, riot_tag, mode, season_filter)
        return lire_bdd_perso(
            f"""
            WITH selected AS (
                SELECT matchs.match_id, matchs.id_participant
                FROM matchs
                INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                WHERE {' AND '.join(conditions)}
            ),
            ranked AS (
                SELECT
                    mps.match_id,
                    mps.player_index,
                    RANK() OVER (
                        PARTITION BY mps.match_id
                        ORDER BY mps.zscore_score DESC NULLS LAST
                    ) AS score_rank
                FROM match_player_scoring_data AS mps
                INNER JOIN selected ON selected.match_id = mps.match_id
            )
            SELECT
                COUNT(*) AS games,
                AVG(mps.zscore_score) AS avg_score,
                AVG(mps.combat_value) AS avg_combat,
                AVG(mps.economic_efficiency) AS avg_economy,
                AVG(mps.objective_contribution) AS avg_objectives,
                AVG(mps.pace_rating) AS avg_tempo,
                AVG(mps.win_impact) AS avg_impact,
                100.0 * SUM(CASE WHEN ranked.score_rank = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS mvp_rate
            FROM selected
            INNER JOIN match_player_scoring_data AS mps
                ON mps.match_id = selected.match_id
               AND mps.player_index = selected.id_participant
            LEFT JOIN ranked
                ON ranked.match_id = selected.match_id
               AND ranked.player_index = selected.id_participant
            """,
            index_col=None,
            params=params,
        ).T

    @classmethod
    def _lane_stats(cls, riot_id: str, riot_tag: str, mode: str, season_filter: int):
        conditions = cls._conditions(season_filter)
        conditions.append("mps.role IN ('TOP', 'MID', 'ADC')")
        params = cls._params(riot_id, riot_tag, mode, season_filter)
        score_sql = lane_domination_sql("mps", "matchs")
        return lire_bdd_perso(
            f"""
            SELECT
                COUNT(*) AS games,
                AVG(mps.gold_diff_15) AS avg_gold_diff_15,
                AVG(mps.cs_diff_15) AS avg_cs_diff_15,
                AVG({score_sql}) AS avg_lane_score,
                100.0 * SUM(CASE WHEN mps.gold_diff_15 > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS gold_lead_rate,
                100.0 * SUM(CASE WHEN {score_sql} >= 70 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS dominant_rate
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

    @classmethod
    def _jungler_gank_stats(cls, riot_id: str, riot_tag: str, mode: str, season_filter: int):
        conditions = cls._conditions(season_filter)
        conditions.append("mps.role = 'JUNGLE'")
        params = cls._params(riot_id, riot_tag, mode, season_filter)
        return lire_bdd_perso(
            f"""
            WITH selected AS (
                SELECT
                    matchs.match_id,
                    CASE WHEN matchs.id_participant < 5 THEN 100 ELSE 200 END AS team_id
                FROM matchs
                INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                INNER JOIN match_player_scoring_data AS mps
                    ON mps.match_id = matchs.match_id
                   AND mps.player_index = matchs.id_participant
                WHERE {' AND '.join(conditions)}
            ),
            early AS (
                SELECT e.match_id, e.team_id, COUNT(*) AS early_attempts
                FROM match_gank_events AS e
                INNER JOIN selected
                    ON selected.match_id = e.match_id
                   AND selected.team_id = e.team_id
                WHERE e.game_phase = 'early'
                GROUP BY e.match_id, e.team_id
            )
            SELECT
                COUNT(*) AS games,
                AVG(gs.total_ganks_made) AS avg_ganks,
                AVG(gs.successful_made) AS avg_successful,
                AVG(gs.failed_made) AS avg_failed,
                AVG(gs.counter_ganks) AS avg_counter_ganks,
                AVG(COALESCE(gs.observed_success_rate_made, gs.success_rate_made) * 100.0) AS avg_success_rate,
                AVG(gs.ally_first_gank_time) AS avg_first_gank_time,
                AVG(COALESCE(early.early_attempts, 0)) AS avg_early_attempts
            FROM selected
            INNER JOIN match_gank_summary AS gs
                ON gs.match_id = selected.match_id
               AND gs.team_id = selected.team_id
            LEFT JOIN early
                ON early.match_id = selected.match_id
               AND early.team_id = selected.team_id
            """,
            index_col=None,
            params=params,
        ).T

    @classmethod
    def _laner_gank_pressure(cls, riot_id: str, riot_tag: str, mode: str, season_filter: int):
        conditions = cls._conditions(season_filter)
        conditions.append("mps.role IN ('TOP', 'MID', 'ADC', 'SUPPORT')")
        params = cls._params(riot_id, riot_tag, mode, season_filter)
        return lire_bdd_perso(
            f"""
            WITH selected AS (
                SELECT
                    matchs.match_id,
                    CASE WHEN matchs.id_participant < 5 THEN 100 ELSE 200 END AS team_id,
                    CASE
                        WHEN mps.role = 'TOP' THEN 'top'
                        WHEN mps.role = 'MID' THEN 'mid'
                        WHEN mps.role IN ('ADC', 'SUPPORT') THEN 'bot'
                    END AS lane
                FROM matchs
                INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                INNER JOIN match_player_scoring_data AS mps
                    ON mps.match_id = matchs.match_id
                   AND mps.player_index = matchs.id_participant
                WHERE {' AND '.join(conditions)}
            ),
            per_game AS (
                SELECT
                    selected.match_id,
                    COUNT(*) FILTER (
                        WHERE e.team_id = selected.team_id AND e.lane = selected.lane
                    ) AS ally_lane_ganks,
                    COUNT(*) FILTER (
                        WHERE e.team_id <> selected.team_id AND e.lane = selected.lane
                    ) AS enemy_lane_ganks,
                    COUNT(*) FILTER (
                        WHERE e.team_id <> selected.team_id
                          AND e.lane = selected.lane
                          AND e.successful = true
                    ) AS enemy_successful
                FROM selected
                LEFT JOIN match_gank_events AS e ON e.match_id = selected.match_id
                GROUP BY selected.match_id
            )
            SELECT
                COUNT(*) AS games,
                AVG(ally_lane_ganks) AS avg_ally_lane_ganks,
                AVG(enemy_lane_ganks) AS avg_enemy_lane_ganks,
                100.0 * SUM(enemy_successful) / NULLIF(SUM(enemy_lane_ganks), 0) AS enemy_success_rate,
                100.0 * SUM(CASE WHEN enemy_lane_ganks >= 2 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS pressured_games_rate
            FROM per_game
            """,
            index_col=None,
            params=params,
        ).T

    @classmethod
    def _teamfight_stats(cls, riot_id: str, riot_tag: str, mode: str, season_filter: int):
        conditions = cls._conditions(season_filter)
        params = cls._params(riot_id, riot_tag, mode, season_filter)
        return lire_bdd_perso(
            f"""
            WITH selected AS (
                SELECT matchs.match_id, tracker.puuid
                FROM matchs
                INNER JOIN tracker ON tracker.id_compte = matchs.joueur
                WHERE {' AND '.join(conditions)}
            ),
            fights AS (
                SELECT mtd.*
                FROM match_teamfight_damage AS mtd
                INNER JOIN selected
                    ON selected.match_id = mtd.match_id
                   AND selected.puuid = mtd.analyzed_puuid
                WHERE mtd.puuid = mtd.analyzed_puuid
                  AND COALESCE(mtd.is_core_participant, true)
                  AND mtd.is_teamfight = true
            ),
            summaries AS (
                SELECT mtps.*
                FROM match_teamfight_player_summary AS mtps
                INNER JOIN selected
                    ON selected.match_id = mtps.match_id
                   AND selected.puuid = mtps.analyzed_puuid
                WHERE mtps.puuid = mtps.analyzed_puuid
            )
            SELECT
                (SELECT COUNT(*) FROM fights) AS teamfights,
                (SELECT 100.0 * SUM(CASE WHEN team = winner THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) FROM fights) AS teamfight_winrate,
                (SELECT 100.0 * SUM(CASE WHEN survived = true THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) FROM fights) AS survival_rate,
                (SELECT AVG(damage_frame_window) FROM fights) AS avg_tf_damage,
                (SELECT SUM(duels) FROM summaries) AS duels,
                (SELECT SUM(duel_wins) FROM summaries) AS duel_wins,
                (SELECT SUM(outnumbered_wins) FROM summaries) AS clutch_wins
            """,
            index_col=None,
            params=params,
        ).T

    @staticmethod
    def _format_time_ms(value) -> str:
        if value is None or pd.isna(value):
            return "—"
        seconds = max(0, int(_num(value)) // 1000)
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes}:{seconds:02d}"

    @slash_command(name="lol_profile", description="Profil statistique historique d'un joueur League of Legends", options=_profile_options())
    async def lol_profile(self, ctx: SlashContext, riot_id: str, riot_tag: str = None, mode: str = "RANKED", season: int = saison):
        await ctx.defer(ephemeral=False)
        try:
            riot_id, riot_tag = self._resolve_account(riot_id, riot_tag)
        except (ValueError, KeyError, IndexError, AttributeError):
            return await ctx.send("Compte introuvable ou Riot ID ambigu. Précise le tag.")

        mode = str(mode or "RANKED").upper()
        season = saison if season is None else int(season)
        core = self._core_stats(riot_id, riot_tag, mode, season)
        if core is None or _int(core.get("games")) == 0:
            return await ctx.send("Aucune partie enregistrée pour ce joueur sur ce périmètre.")

        games = _int(core.get("games"))
        wins = _int(core.get("wins"))
        winrate = 100.0 * wins / games if games else 0.0
        champions = self._champions(riot_id, riot_tag, mode, season)
        roles = self._role_stats(riot_id, riot_tag, mode, season)
        main_role = str(roles.iloc[0].get("role") or "UNKNOWN").upper() if not roles.empty else "UNKNOWN"
        top_champion = str(champions.iloc[0].get("champion") or "?") if not champions.empty else "?"

        season_text = f"S{season}" if season != 0 else "toutes saisons"
        embed = interactions.Embed(
            title=f"Profil LoL — {riot_id.upper()} #{riot_tag}",
            description=f"**{mode} · {season_text}** · {games} parties enregistrées · rôle principal **{main_role}**",
            color=interactions.Color.random(),
        )
        icon = _champion_icon_url(top_champion)
        if icon:
            embed.set_thumbnail(url=icon)

        embed.add_field(
            name="Vue d'ensemble",
            value=(
                f"🏆 **{winrate:.1f}%** WR ({wins}–{games - wins})\n"
                f"⚔️ K/D/A moyen **{_num(core.get('avg_kills')):.1f}/{_num(core.get('avg_deaths')):.1f}/{_num(core.get('avg_assists')):.1f}** · KDA **{_num(core.get('avg_kda')):.2f}**\n"
                f"🎯 **{_int(core.get('avg_dpm'))}** DPM · 👻 **{_num(core.get('avg_cs_min')):.2f}** CS/min · 💰 **{_int(core.get('avg_gpm'))}** GPM\n"
                f"🤝 KP **{_num(core.get('avg_kp')):.1f}%** · 👁️ vision/min **{_num(core.get('avg_vision_min')):.2f}**"
            ),
            inline=False,
        )

        scoring = self._scoring_stats(riot_id, riot_tag, mode, season)
        if not scoring.empty and _int(scoring.iloc[0].get("games")) > 0:
            row = scoring.iloc[0]
            embed.add_field(
                name="Scoring historique",
                value=(
                    f"⭐ Score moyen **{_num(row.get('avg_score')):.2f}/10** · MVP **{_pct(row.get('mvp_rate'))}**\n"
                    f"⚔️ Combat **{_num(row.get('avg_combat')):.1f}** · 💰 Éco **{_num(row.get('avg_economy')):.1f}** · "
                    f"🎯 Obj **{_num(row.get('avg_objectives')):.1f}** · ⚡ Tempo **{_num(row.get('avg_tempo')):.1f}** · 👑 Impact **{_num(row.get('avg_impact')):.1f}**"
                ),
                inline=False,
            )

        if mode != "ARAM":
            lane = self._lane_stats(riot_id, riot_tag, mode, season)
            if not lane.empty and _int(lane.iloc[0].get("games")) > 0:
                row = lane.iloc[0]
                embed.add_field(
                    name="Lane (TOP / MID / ADC)",
                    value=(
                        f"Indice moyen **{_num(row.get('avg_lane_score')):.1f}/100** · domination 70+ sur **{_pct(row.get('dominant_rate'))}** des games\n"
                        f"@15 : gold **{_signed(row.get('avg_gold_diff_15'), 'g')}** · CS **{_signed(row.get('avg_cs_diff_15'))}** · "
                        f"avantage gold sur **{_pct(row.get('gold_lead_rate'))}**"
                    ),
                    inline=False,
                )

            if main_role == "JUNGLE":
                ganks = self._jungler_gank_stats(riot_id, riot_tag, mode, season)
                if not ganks.empty and _int(ganks.iloc[0].get("games")) > 0:
                    row = ganks.iloc[0]
                    embed.add_field(
                        name="Jungle — activité de gank",
                        value=(
                            f"🗺️ **{_num(row.get('avg_ganks')):.2f}** tentatives/game · **{_num(row.get('avg_successful')):.2f}** réussies · succès **{_pct(row.get('avg_success_rate'))}**\n"
                            f"⚪ **{_num(row.get('avg_failed')):.2f}** ratées · 🔁 **{_num(row.get('avg_counter_ganks')):.2f}** counter-ganks · early **{_num(row.get('avg_early_attempts')):.2f}**/game\n"
                            f"⏱️ Premier gank moyen **{self._format_time_ms(row.get('avg_first_gank_time'))}**"
                        ),
                        inline=False,
                    )
            else:
                pressure = self._laner_gank_pressure(riot_id, riot_tag, mode, season)
                if not pressure.empty and _int(pressure.iloc[0].get("games")) > 0:
                    row = pressure.iloc[0]
                    embed.add_field(
                        name="Pression jungle sur sa lane",
                        value=(
                            f"🔵 Appuis alliés **{_num(row.get('avg_ally_lane_ganks')):.2f}/game** · "
                            f"🔴 appuis ennemis **{_num(row.get('avg_enemy_lane_ganks')):.2f}/game**\n"
                            f"Succès des ganks ennemis **{_pct(row.get('enemy_success_rate'))}** · "
                            f"2+ tentatives ennemies sur **{_pct(row.get('pressured_games_rate'))}** des games"
                        ),
                        inline=False,
                    )

        teamfights = self._teamfight_stats(riot_id, riot_tag, mode, season)
        if not teamfights.empty and _int(teamfights.iloc[0].get("teamfights")) > 0:
            row = teamfights.iloc[0]
            duels = _int(row.get("duels"))
            duel_wins = _int(row.get("duel_wins"))
            duel_rate = 100.0 * duel_wins / duels if duels else 0.0
            embed.add_field(
                name="Combats",
                value=(
                    f"⚔️ **{_int(row.get('teamfights'))}** teamfights · WR **{_pct(row.get('teamfight_winrate'))}** · survie **{_pct(row.get('survival_rate'))}**\n"
                    f"🎯 Dégâts moyens / TF **{_int(row.get('avg_tf_damage'))}** · 🥊 duels **{duel_wins}/{duels} ({duel_rate:.0f}%)** · 🔥 clutches **{_int(row.get('clutch_wins'))}**"
                ),
                inline=False,
            )

        if not champions.empty:
            lines = []
            for _, row in champions.iterrows():
                champion = str(row.get("champion") or "?")
                lines.append(
                    f"{_champion_emoji(champion)} **{champion}** — {_int(row.get('games'))} games · "
                    f"{_pct(row.get('winrate'))} WR · KDA {_num(row.get('avg_kda')):.2f} · {_int(row.get('avg_dpm'))} DPM"
                )
            embed.add_field(name="Champions les plus joués", value="\n".join(lines), inline=False)

        if not roles.empty:
            role_lines = [f"**{row.get('role')}** {_int(row.get('games'))}" for _, row in roles.iterrows()]
            embed.add_field(name="Répartition des rôles", value=" · ".join(role_lines)[:1024], inline=False)

        embed.set_footer(text=f"Données enregistrées par Marin · Version {Version}")
        await ctx.send(embeds=embed)

    @lol_profile.autocomplete("riot_id")
    async def autocomplete_profile(self, ctx: interactions.AutocompleteContext):
        await ctx.send(choices=await autocomplete_riotid(int(ctx.guild.id), ctx.input_text))
