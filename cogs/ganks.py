import re

import interactions
import pandas as pd
from interactions import (
    Extension,
    SlashCommandChoice,
    SlashCommandOption,
    SlashContext,
    slash_command,
)
from interactions.ext.paginators import Paginator

from fonctions.autocomplete import autocomplete_riotid
from fonctions.gestion_bdd import get_tag, lire_bdd_perso
from fonctions.match import MatchLol
from fonctions.match.gank_laning_rules import (
    FAILED_OUTCOMES,
    GANK_ALGORITHM_VERSION,
    GANK_WINDOW_END_MS,
    STRICT_SUCCESS_OUTCOME,
    TRADE_OUTCOME,
    install_gank_laning_rules,
)
from fonctions.match.gank_recap import install_gank_recap
from utils.emoji import emote_champ_discord
from utils.params import Version, saison


LANES = ("top", "mid", "bot")
LANE_LABELS = {"top": "TOP", "mid": "MID", "bot": "BOT"}
OUTCOME_LABELS = {
    "success": "✅ succès",
    "trade": "🟡 trade",
    "failed": "⚪ raté",
    "jungler_death": "❌ mort du jungler",
}
SOURCE_LABELS = {
    "exact_event": "exact",
    "sampled_combat": "frame",
    "inferred_combat": "inféré",
}
SUPPORTED_MODES = {"RANKED", "FLEX", "SWIFTPLAY"}


# Les règles V3 doivent être installées avant le patch du récap : gank_stats ne
# contient ainsi que les tentatives de phase de lane et les trades ne sont plus
# considérés comme des succès.
install_gank_laning_rules(MatchLol)
install_gank_recap(MatchLol)


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
    return (
        f"https://cdn.discordapp.com/emojis/{match.group(1)}.png"
        "?size=128&quality=lossless"
    )


def _safe_int(value) -> int:
    try:
        if value is None or pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value) -> float:
    try:
        if value is None or pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_bool(value) -> bool:
    if isinstance(value, str):
        return value.lower() in {"true", "t", "1", "yes"}
    if value is None or pd.isna(value):
        return False
    return bool(value)


def _format_time(timestamp_ms) -> str:
    try:
        seconds = max(0, int(float(timestamp_ms)) // 1000)
    except (TypeError, ValueError):
        return "—"
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _pct(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "—"
    return f"{100.0 * numerator / denominator:.0f}%"


def _mode_choices():
    return [
        SlashCommandChoice(name="Ranked", value="RANKED"),
        SlashCommandChoice(name="Flex", value="FLEX"),
        SlashCommandChoice(name="Swiftplay", value="SWIFTPLAY"),
    ]


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
    return [
        SlashCommandOption(
            name="mode",
            description="Mode de jeu",
            type=interactions.OptionType.STRING,
            required=False,
            choices=_mode_choices(),
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
            description="Périmètre du classement",
            type=interactions.OptionType.STRING,
            required=False,
            choices=[
                SlashCommandChoice(name="Serveur Discord", value="server"),
                SlashCommandChoice(name="Global", value="global"),
            ],
        ),
    ]


def _team_rows(events: pd.DataFrame, team_id: int) -> pd.DataFrame:
    if events.empty:
        return events
    return events[
        pd.to_numeric(events["team_id"], errors="coerce") == int(team_id)
    ]


def _outcome_counts(rows: pd.DataFrame) -> dict[str, int]:
    if rows.empty:
        return {"total": 0, "success": 0, "trade": 0, "failed": 0}
    outcome = rows["outcome"].fillna("").astype(str).str.lower()
    return {
        "total": len(rows),
        "success": int((outcome == STRICT_SUCCESS_OUTCOME).sum()),
        "trade": int((outcome == TRADE_OUTCOME).sum()),
        "failed": int(outcome.isin(FAILED_OUTCOMES).sum()),
    }


def _first_event(rows: pd.DataFrame):
    if rows.empty:
        return None
    timestamps = pd.to_numeric(rows["timestamp_ms"], errors="coerce")
    valid = rows[timestamps.notna()].copy()
    if valid.empty:
        return None
    valid["_timestamp"] = pd.to_numeric(valid["timestamp_ms"], errors="coerce")
    return valid.sort_values("_timestamp").iloc[0]


def _jungler_champion(summary: dict, rows: pd.DataFrame, side: str) -> str:
    value = summary.get(f"{side}_jungler_champion") if summary else None
    if value and not pd.isna(value):
        return str(value)
    if not rows.empty:
        value = rows.iloc[0].get("jungler_champion")
        if value and not pd.isna(value):
            return str(value)
    return "?"


class Ganks(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @staticmethod
    def _resolve_account(riot_id: str, riot_tag: str | None) -> tuple[str, str]:
        riot_id = riot_id.lower().replace(" ", "")
        if riot_tag is None:
            riot_tag = get_tag(riot_id)
        return riot_id, riot_tag.upper()

    @staticmethod
    def _load_selected_match(
        riot_id: str,
        riot_tag: str,
        numerogame: int,
        match_id: str | None = None,
    ) -> dict | None:
        common_select = """
            SELECT
                matchs.match_id,
                matchs.id_participant,
                matchs.champion,
                matchs.mode,
                matchs.season,
                matchs.datetime
            FROM matchs
            INNER JOIN tracker ON tracker.id_compte = matchs.joueur
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
    def _tracked_team(match: dict) -> int:
        return 100 if _safe_int(match.get("id_participant")) < 5 else 200

    @staticmethod
    def _load_summary(match_id, team_id: int) -> dict:
        df = lire_bdd_perso(
            """
            SELECT *
            FROM match_gank_summary
            WHERE match_id = :match_id
              AND team_id = :team_id
            LIMIT 1
            """,
            index_col=None,
            params={"match_id": match_id, "team_id": team_id},
        ).T
        return {} if df.empty else df.iloc[0].to_dict()

    @staticmethod
    def _load_events(match_id) -> pd.DataFrame:
        return lire_bdd_perso(
            """
            SELECT
                match_id, team_id, gank_id,
                timestamp_ms, timestamp_formatted, start_ms, end_ms,
                game_phase, lane, jungler_id, jungler_champion,
                successful, outcome, detection_source, confidence,
                is_counter_gank, victim_id,
                kills_for, kills_against,
                jungler_kills, jungler_assists, jungler_deaths,
                participants_allies, participants_enemies,
                jungler_damage_delta, lane_activity_delta, position_evidence,
                algorithm_version
            FROM match_gank_events
            WHERE match_id = :match_id
              AND timestamp_ms >= 0
              AND timestamp_ms < :gank_end
            ORDER BY timestamp_ms, team_id, gank_id
            """,
            index_col=None,
            params={"match_id": match_id, "gank_end": GANK_WINDOW_END_MS},
        ).T

    async def _context(
        self,
        riot_id: str,
        riot_tag: str | None,
        numerogame: int,
        match_id: str | None,
    ):
        try:
            riot_id, riot_tag = self._resolve_account(riot_id, riot_tag)
        except (ValueError, KeyError, IndexError, AttributeError):
            return None, None, None, "Compte introuvable ou Riot ID ambigu. Précise le tag."

        match = self._load_selected_match(riot_id, riot_tag, numerogame, match_id)
        if match is None:
            return None, None, None, "Cette partie enregistrée est introuvable."

        if str(match.get("mode") or "").upper() not in SUPPORTED_MODES:
            return None, None, None, (
                "L'analyse des ganks n'est disponible qu'en Ranked, Flex et Swiftplay."
            )

        team_id = self._tracked_team(match)
        summary = self._load_summary(match["match_id"], team_id)
        events = self._load_events(match["match_id"])
        if not summary and events.empty:
            return None, None, None, (
                "La partie existe, mais aucune analyse de ganks n'est enregistrée pour elle."
            )

        return riot_id, riot_tag, (match, team_id, summary, events), None

    @staticmethod
    def _base_embed(
        title: str,
        match: dict,
        numerogame: int,
        requested_match_id: str | None,
        champion: str | None = None,
    ):
        description = (
            f"Match ID · `{match['match_id']}`"
            if requested_match_id
            else f"Partie #{numerogame} · `{match['match_id']}`"
        )
        embed = interactions.Embed(
            title=title,
            description=description + "\nGanks comptés uniquement entre **0:00 et 13:59**.",
            color=interactions.Color.random(),
        )
        if champion:
            icon = _champion_icon_url(champion)
            if icon:
                embed.set_thumbnail(url=icon)
        embed.set_footer(
            text=f"Détection hybride V{GANK_ALGORITHM_VERSION} · Version {Version}"
        )
        return embed

    @staticmethod
    def _lane_counts(events: pd.DataFrame, team_id: int) -> dict[str, int]:
        result = {lane: 0 for lane in LANES}
        team_events = _team_rows(events, team_id)
        if team_events.empty:
            return result
        for lane in LANES:
            result[lane] = int(
                (team_events["lane"].astype(str).str.lower() == lane).sum()
            )
        return result

    @staticmethod
    def _lane_distribution(counts: dict[str, int]) -> str:
        return " · ".join(
            f"**{LANE_LABELS[lane]} {counts[lane]}**" for lane in LANES
        )

    @slash_command(
        name="gank",
        description="Analyse des ganks d'une partie League of Legends",
    )
    async def gank(self, ctx: SlashContext):
        pass

    @gank.subcommand(
        "resume",
        sub_cmd_description="Résumé de l'activité des deux junglers avant 14 min",
        options=_game_options(),
    )
    async def resume(
        self,
        ctx: SlashContext,
        riot_id: str,
        riot_tag: str = None,
        numerogame: int = 0,
        match_id: str = None,
    ):
        await ctx.defer(ephemeral=False)
        riot_id, riot_tag, payload, error = await self._context(
            riot_id, riot_tag, numerogame, match_id
        )
        if error:
            return await ctx.send(error)

        match, team_id, summary, events = payload
        enemy_team = 200 if team_id == 100 else 100
        ally_rows = _team_rows(events, team_id)
        enemy_rows = _team_rows(events, enemy_team)
        ally_champ = _jungler_champion(summary, ally_rows, "ally")
        enemy_champ = _jungler_champion(summary, enemy_rows, "enemy")

        embed = self._base_embed(
            f"Ganks — {riot_id.upper()} #{riot_tag}",
            match,
            numerogame,
            match_id,
            ally_champ,
        )

        def side_value(rows: pd.DataFrame) -> str:
            counts = _outcome_counts(rows)
            first = _first_event(rows)
            if first is None:
                first_text = "—"
            else:
                first_text = (
                    f"{_format_time(first.get('timestamp_ms'))} "
                    f"{str(first.get('lane') or '').upper()}"
                )
            return (
                f"Tentatives **{counts['total']}** · succès stricts **{counts['success']}** "
                f"({_pct(counts['success'], counts['total'])})\n"
                f"Trades **{counts['trade']}** · ratées/mort jungler **{counts['failed']}**\n"
                f"Premier gank **{first_text}**"
            )

        embed.add_field(
            name=f"🔵 {_champion_emoji(ally_champ)} {ally_champ} — jungle alliée",
            value=side_value(ally_rows),
            inline=False,
        )
        embed.add_field(
            name=f"🔴 {_champion_emoji(enemy_champ)} {enemy_champ} — jungle ennemie",
            value=side_value(enemy_rows),
            inline=False,
        )

        ally_counts = self._lane_counts(events, team_id)
        enemy_counts = self._lane_counts(events, enemy_team)
        embed.add_field(
            name="🗺️ Répartition des appuis",
            value=(
                f"🔵 Alliée : {self._lane_distribution(ally_counts)}\n"
                f"🔴 Ennemie : {self._lane_distribution(enemy_counts)}"
            ),
            inline=False,
        )

        source = ally_rows["detection_source"].fillna("").astype(str) if not ally_rows.empty else pd.Series(dtype=str)
        confidence = pd.to_numeric(ally_rows["confidence"], errors="coerce") if not ally_rows.empty else pd.Series(dtype=float)
        exact = int((source == "exact_event").sum())
        inferred = len(ally_rows) - exact
        high = int((confidence >= 0.80).sum())
        counter = int(ally_rows["is_counter_gank"].apply(_safe_bool).sum()) if not ally_rows.empty else 0
        diff = len(ally_rows) - len(enemy_rows)
        embed.add_field(
            name="🔬 Qualité / lecture",
            value=(
                f"Différentiel de tentatives **{diff:+d}** · counter-ganks **{counter}**\n"
                f"Jungle alliée : **{exact} exactes** · **{inferred} inférées** · "
                f"**{high} haute confiance**\n"
                "Le taux est une **conversion observée** : les passages sans kill et sans "
                "signal de dégâts restent plus difficiles à détecter."
            ),
            inline=False,
        )
        await ctx.send(embeds=embed)

    @gank.subcommand(
        "events",
        sub_cmd_description="Timeline des tentatives détectées avant 14 min",
        options=_game_options(),
    )
    async def events(
        self,
        ctx: SlashContext,
        riot_id: str,
        riot_tag: str = None,
        numerogame: int = 0,
        match_id: str = None,
    ):
        await ctx.defer(ephemeral=False)
        riot_id, riot_tag, payload, error = await self._context(
            riot_id, riot_tag, numerogame, match_id
        )
        if error:
            return await ctx.send(error)

        match, team_id, summary, events = payload
        if events.empty:
            return await ctx.send(
                "Aucune tentative de gank détectée avant 14:00 sur cette partie."
            )

        ally_rows = _team_rows(events, team_id)
        ally_champ = _jungler_champion(summary, ally_rows, "ally")
        lines = []
        for _, row in events.iterrows():
            is_ally = _safe_int(row.get("team_id")) == team_id
            side = "🔵" if is_ally else "🔴"
            champ = str(row.get("jungler_champion") or "?")
            lane = LANE_LABELS.get(
                str(row.get("lane") or "").lower(),
                str(row.get("lane") or "?").upper(),
            )
            outcome = OUTCOME_LABELS.get(
                str(row.get("outcome")), str(row.get("outcome") or "—")
            )
            source = SOURCE_LABELS.get(
                str(row.get("detection_source")),
                str(row.get("detection_source") or "—"),
            )
            confidence = _safe_float(row.get("confidence"))
            counter = " · 🔁 counter" if _safe_bool(row.get("is_counter_gank")) else ""
            kda = (
                f"{_safe_int(row.get('jungler_kills'))}/"
                f"{_safe_int(row.get('jungler_deaths'))}/"
                f"{_safe_int(row.get('jungler_assists'))}"
            )
            lines.append(
                f"{side} **{_format_time(row.get('timestamp_ms'))} {lane}** · "
                f"{_champion_emoji(champ)} {champ} · {outcome}{counter}\n"
                f"↳ K/D/A jungler **{kda}** · {source} · confiance **{confidence:.0%}**"
            )

        pages = []
        page_size = 5
        for start in range(0, len(lines), page_size):
            embed = self._base_embed(
                f"Timeline ganks — {riot_id.upper()} #{riot_tag}",
                match,
                numerogame,
                match_id,
                ally_champ,
            )
            embed.add_field(
                name=(
                    f"Tentatives {start + 1}–"
                    f"{min(start + page_size, len(lines))}"
                ),
                value="\n\n".join(lines[start : start + page_size]),
                inline=False,
            )
            pages.append(embed)

        if len(pages) == 1:
            return await ctx.send(embeds=pages[0])
        paginator = Paginator.create_from_embeds(self.bot, *pages)
        paginator.show_select_menu = True
        await paginator.send(ctx)

    @gank.subcommand(
        "lanes",
        sub_cmd_description="Compare les appuis TOP / MID / BOT avant 14 min",
        options=_game_options(),
    )
    async def lanes(
        self,
        ctx: SlashContext,
        riot_id: str,
        riot_tag: str = None,
        numerogame: int = 0,
        match_id: str = None,
    ):
        await ctx.defer(ephemeral=False)
        riot_id, riot_tag, payload, error = await self._context(
            riot_id, riot_tag, numerogame, match_id
        )
        if error:
            return await ctx.send(error)

        match, team_id, summary, events = payload
        enemy_team = 200 if team_id == 100 else 100
        ally_rows = _team_rows(events, team_id)
        ally_champ = _jungler_champion(summary, ally_rows, "ally")
        embed = self._base_embed(
            f"Appuis par lane — {riot_id.upper()} #{riot_tag}",
            match,
            numerogame,
            match_id,
            ally_champ,
        )

        for lane in LANES:
            lane_rows = (
                events[events["lane"].astype(str).str.lower() == lane]
                if not events.empty
                else events
            )
            ally = _team_rows(lane_rows, team_id)
            enemy = _team_rows(lane_rows, enemy_team)

            def line(rows: pd.DataFrame, icon: str) -> str:
                counts = _outcome_counts(rows)
                return (
                    f"{icon} **{counts['total']}** tentatives · "
                    f"**{counts['success']}** succès ({_pct(counts['success'], counts['total'])}) · "
                    f"**{counts['trade']}** trades · **{counts['failed']}** ratées"
                )

            embed.add_field(
                name=LANE_LABELS[lane],
                value=f"{line(ally, '🔵')}\n{line(enemy, '🔴')}",
                inline=False,
            )
        await ctx.send(embeds=embed)

    @gank.subcommand(
        "records",
        sub_cmd_description="Records de ganks avant 14 min",
        options=_record_options(),
    )
    async def records(
        self,
        ctx: SlashContext,
        mode: str = "RANKED",
        season: int = saison,
        scope: str = "server",
    ):
        await ctx.defer(ephemeral=False)
        mode = str(mode or "RANKED").upper()
        season = saison if season is None else int(season)
        scope = str(scope or "server").lower()

        if mode not in SUPPORTED_MODES:
            return await ctx.send(
                "Les records de ganks sont limités à Ranked, Flex et Swiftplay."
            )

        conditions = [
            "tracker.banned = false",
            "tracker.save_records = true",
            "matchs.records = true",
            "matchs.mode = :mode",
            "matchs.time >= 15",
        ]
        params = {"mode": mode, "gank_end": GANK_WINDOW_END_MS}
        if season != 0:
            conditions.append("matchs.season = :season")
            params["season"] = season
        if scope == "server":
            conditions.append("tracker.server_id = :server_id")
            params["server_id"] = int(ctx.guild_id)

        query = f"""
            WITH event_agg AS (
                SELECT
                    match_id,
                    team_id,
                    COUNT(*) AS attempts,
                    COUNT(*) FILTER (WHERE outcome = 'success') AS successes,
                    COUNT(*) FILTER (WHERE outcome = 'trade') AS trades,
                    COUNT(*) FILTER (
                        WHERE outcome IN ('failed', 'jungler_death')
                    ) AS failed,
                    COUNT(*) FILTER (WHERE is_counter_gank = true) AS counters,
                    MIN(timestamp_ms) FILTER (
                        WHERE outcome = 'success'
                    ) AS first_successful_gank
                FROM match_gank_events
                WHERE timestamp_ms >= 0
                  AND timestamp_ms < :gank_end
                GROUP BY match_id, team_id
            )
            SELECT
                matchs.match_id,
                matchs.champion,
                matchs.url,
                matchs.season,
                tracker.riot_id,
                tracker.riot_tagline,
                COALESCE(ally.attempts, 0) AS total_ganks_made,
                COALESCE(enemy.attempts, 0) AS total_ganks_received,
                COALESCE(ally.successes, 0) AS successful_made,
                COALESCE(ally.trades, 0) AS trades_made,
                COALESCE(ally.failed, 0) AS failed_made,
                COALESCE(ally.counters, 0) AS counter_ganks,
                COALESCE(ally.attempts, 0) - COALESCE(enemy.attempts, 0)
                    AS differential,
                CASE
                    WHEN COALESCE(ally.attempts, 0) >= 4
                    THEN 100.0 * COALESCE(ally.successes, 0)
                         / NULLIF(ally.attempts, 0)
                END AS gank_success_rate,
                ally.first_successful_gank
            FROM matchs
            INNER JOIN tracker ON tracker.id_compte = matchs.joueur
            LEFT JOIN event_agg AS ally
                ON ally.match_id = matchs.match_id
               AND ally.team_id = CASE
                    WHEN matchs.id_participant < 5 THEN 100 ELSE 200
               END
            LEFT JOIN event_agg AS enemy
                ON enemy.match_id = matchs.match_id
               AND enemy.team_id = CASE
                    WHEN matchs.id_participant < 5 THEN 200 ELSE 100
               END
            WHERE {' AND '.join(conditions)}
        """
        df = lire_bdd_perso(query, index_col=None, params=params).T
        if df.empty:
            return await ctx.send(
                "Aucune donnée de gank disponible pour ce périmètre."
            )

        records = [
            ("total_ganks_made", "PLUS DE TENTATIVES", "max", "int"),
            ("successful_made", "PLUS DE GANKS RÉUSSIS", "max", "int"),
            ("gank_success_rate", "MEILLEUR TAUX STRICT (MIN. 4)", "max", "pct"),
            ("failed_made", "PLUS DE TENTATIVES RATÉES", "max", "int"),
            ("trades_made", "PLUS DE TRADES SUR GANK", "max", "int"),
            ("counter_ganks", "PLUS DE COUNTER-GANKS", "max", "int"),
            ("differential", "PLUS GROS DIFFÉRENTIEL", "max", "signed"),
            (
                "first_successful_gank",
                "GANK RÉUSSI LE PLUS TÔT",
                "min",
                "time",
            ),
            (
                "total_ganks_received",
                "PLUS FORTE PRESSION JUNGLE ENNEMIE",
                "max",
                "int",
            ),
        ]

        title_scope = "serveur" if scope == "server" else "global"
        title_season = f"S{season}" if season != 0 else "toutes saisons"
        embed = interactions.Embed(
            title=f"Records ganks <14 — {mode} {title_season} — {title_scope}",
            description=(
                "Succès strict = le gank obtient un kill **sans trade retour**. "
                "Tous les événements à partir de 14:00 sont exclus."
            ),
            color=interactions.Color.random(),
        )

        for column, label, method, fmt in records:
            numeric = pd.to_numeric(df[column], errors="coerce")
            valid = df[numeric.notna()].copy()
            if valid.empty:
                continue
            valid["_value"] = pd.to_numeric(valid[column], errors="coerce")
            record_value = (
                valid["_value"].min()
                if method == "min"
                else valid["_value"].max()
            )
            holders = valid[valid["_value"] == record_value].head(3)

            if fmt == "pct":
                display_value = f"{record_value:.1f}%"
            elif fmt == "time":
                display_value = _format_time(record_value)
            elif fmt == "signed":
                display_value = f"{int(record_value):+d}"
            else:
                display_value = str(int(record_value))

            lines = []
            for _, row in holders.iterrows():
                champion = str(row.get("champion") or "?")
                player = str(row.get("riot_id") or "?")
                tag = str(row.get("riot_tagline") or "")
                lines.append(
                    f"{_champion_emoji(champion)} **{player} #{tag}** · "
                    f"{champion} · `{row.get('match_id')}`"
                )
            embed.add_field(
                name=f"{label} — {display_value}",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(
            text=f"Ganks V{GANK_ALGORITHM_VERSION} · 0:00–13:59 · Version {Version}"
        )
        await ctx.send(embeds=embed)

    @resume.autocomplete("riot_id")
    async def autocomplete_resume(self, ctx: interactions.AutocompleteContext):
        await ctx.send(
            choices=await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        )

    @events.autocomplete("riot_id")
    async def autocomplete_events(self, ctx: interactions.AutocompleteContext):
        await ctx.send(
            choices=await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        )

    @lanes.autocomplete("riot_id")
    async def autocomplete_lanes(self, ctx: interactions.AutocompleteContext):
        await ctx.send(
            choices=await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        )
