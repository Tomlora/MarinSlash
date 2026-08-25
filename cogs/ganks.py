import re

import interactions
import pandas as pd
from interactions import Extension, SlashCommandChoice, SlashCommandOption, SlashContext, slash_command
from interactions.ext.paginators import Paginator

from fonctions.autocomplete import autocomplete_riotid
from fonctions.gestion_bdd import get_tag, lire_bdd_perso
from fonctions.match.gank_recap import install_gank_recap
from fonctions.match import MatchLol
from utils.emoji import emote_champ_discord
from utils.params import Version, saison


LANES = ("top", "mid", "bot")
LANE_LABELS = {"top": "TOP", "mid": "MID", "bot": "BOT"}
PHASE_LABELS = {"early": "Early", "mid": "Mid", "late": "Late"}
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
STYLE_LABELS = {
    "early_aggro": "agressif early",
    "balanced": "équilibré",
    "mid_focused": "orienté mid-game",
    "late_scaler": "plutôt tardif",
    "passive": "peu actif",
}


# Le patch est idempotent et rend le focus jungle disponible dans le champ
# Insights du récap construit par leagueoflegends.py.
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
        if match_id is not None and str(match_id).strip():
            requested = str(match_id).strip()
            requested_without_prefix = requested.replace("EUW1_", "")
            df = lire_bdd_perso(
                """
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
                  AND (
                        CAST(matchs.match_id AS TEXT) = :match_id
                     OR CAST(matchs.match_id AS TEXT) = :match_id_without_prefix
                  )
                LIMIT 1
                """,
                index_col=None,
                params={
                    "riot_id": riot_id,
                    "riot_tag": riot_tag,
                    "match_id": requested,
                    "match_id_without_prefix": requested_without_prefix,
                },
            ).T
        else:
            df = lire_bdd_perso(
                """
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
                ORDER BY matchs.datetime DESC, matchs.match_id DESC
                LIMIT 1 OFFSET :offset
                """,
                index_col=None,
                params={
                    "riot_id": riot_id,
                    "riot_tag": riot_tag,
                    "offset": numerogame,
                },
            ).T
        return None if df.empty else df.iloc[0].to_dict()

    @staticmethod
    def _tracked_team(match: dict) -> int:
        return 100 if _safe_int(match.get("id_participant")) < 5 else 200

    @staticmethod
    def _load_summary(match_id, team_id: int) -> dict | None:
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
        return None if df.empty else df.iloc[0].to_dict()

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
            ORDER BY timestamp_ms, team_id, gank_id
            """,
            index_col=None,
            params={"match_id": match_id},
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

        if str(match.get("mode")) not in {"RANKED", "FLEX", "SWIFTPLAY"}:
            return None, None, None, "L'analyse des ganks n'est disponible qu'en Ranked, Flex et Swiftplay."

        team_id = self._tracked_team(match)
        summary = self._load_summary(match["match_id"], team_id)
        events = self._load_events(match["match_id"])
        if summary is None:
            return None, None, None, (
                "La partie existe, mais aucune analyse de ganks n'est enregistrée pour elle."
            )

        return riot_id, riot_tag, (match, team_id, summary, events), None

    @staticmethod
    def _base_embed(title: str, match: dict, numerogame: int, requested_match_id: str | None, champion: str | None = None):
        description = (
            f"Match ID · `{match['match_id']}`"
            if requested_match_id
            else f"Partie #{numerogame} · `{match['match_id']}`"
        )
        embed = interactions.Embed(
            title=title,
            description=description,
            color=interactions.Color.random(),
        )
        if champion:
            icon = _champion_icon_url(champion)
            if icon:
                embed.set_thumbnail(url=icon)
        embed.set_footer(text=f"Détection hybride V2 · Version {Version}")
        return embed

    @staticmethod
    def _lane_counts(events: pd.DataFrame, team_id: int) -> dict[str, int]:
        result = {lane: 0 for lane in LANES}
        if events.empty:
            return result
        team_events = events[pd.to_numeric(events["team_id"], errors="coerce") == int(team_id)]
        for lane in LANES:
            result[lane] = int((team_events["lane"].astype(str).str.lower() == lane).sum())
        return result

    @staticmethod
    def _lane_distribution(counts: dict[str, int]) -> str:
        return " · ".join(f"**{LANE_LABELS[lane]} {counts[lane]}**" for lane in LANES)

    @slash_command(name="gank", description="Analyse des ganks d'une partie League of Legends")
    async def gank(self, ctx: SlashContext):
        pass

    @gank.subcommand("resume", sub_cmd_description="Résumé de l'activité des deux junglers", options=_game_options())
    async def resume(self, ctx: SlashContext, riot_id: str, riot_tag: str = None, numerogame: int = 0, match_id: str = None):
        await ctx.defer(ephemeral=False)
        riot_id, riot_tag, payload, error = await self._context(riot_id, riot_tag, numerogame, match_id)
        if error:
            return await ctx.send(error)

        match, team_id, summary, events = payload
        enemy_team = 200 if team_id == 100 else 100
        ally_champ = str(summary.get("ally_jungler_champion") or "?")
        enemy_champ = str(summary.get("enemy_jungler_champion") or "?")
        ally_emoji = _champion_emoji(ally_champ)
        enemy_emoji = _champion_emoji(enemy_champ)

        embed = self._base_embed(
            f"Ganks — {riot_id.upper()} #{riot_tag}",
            match,
            numerogame,
            match_id,
            ally_champ,
        )

        made = _safe_int(summary.get("total_ganks_made"))
        made_success = _safe_int(summary.get("successful_made"))
        made_failed = _safe_int(summary.get("failed_made"))
        received = _safe_int(summary.get("total_ganks_received"))
        received_success = _safe_int(summary.get("successful_received"))
        received_failed = _safe_int(summary.get("failed_received"))

        ally_first = summary.get("ally_first_gank_time")
        enemy_first = summary.get("enemy_first_gank_time")
        ally_first_text = "—" if ally_first is None or pd.isna(ally_first) else _format_time(ally_first)
        enemy_first_text = "—" if enemy_first is None or pd.isna(enemy_first) else _format_time(enemy_first)

        embed.add_field(
            name=f"🔵 {ally_emoji} {ally_champ} — jungle alliée",
            value=(
                f"Tentatives **{made}** · succès **{made_success}** ({_pct(made_success, made)}) · ratées **{made_failed}**\n"
                f"Premier gank **{ally_first_text}** {str(summary.get('ally_first_gank_lane') or '').upper()}\n"
                f"Style **{STYLE_LABELS.get(str(summary.get('ally_style')), str(summary.get('ally_style') or '—'))}**"
            ),
            inline=False,
        )
        embed.add_field(
            name=f"🔴 {enemy_emoji} {enemy_champ} — jungle ennemie",
            value=(
                f"Tentatives **{received}** · succès **{received_success}** ({_pct(received_success, received)}) · ratées **{received_failed}**\n"
                f"Premier gank **{enemy_first_text}** {str(summary.get('enemy_first_gank_lane') or '').upper()}\n"
                f"Style **{STYLE_LABELS.get(str(summary.get('enemy_style')), str(summary.get('enemy_style') or '—'))}**"
            ),
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

        exact = _safe_int(summary.get("exact_attempts_made"))
        inferred = _safe_int(summary.get("inferred_attempts_made"))
        high = _safe_int(summary.get("high_confidence_made"))
        counter = _safe_int(summary.get("counter_ganks"))
        diff = _safe_int(summary.get("differential"))
        embed.add_field(
            name="🔬 Qualité / lecture",
            value=(
                f"Différentiel de tentatives **{diff:+d}** · counter-ganks **{counter}**\n"
                f"Jungle alliée : **{exact} exactes** · **{inferred} inférées** · **{high} haute confiance**"
            ),
            inline=False,
        )
        await ctx.send(embeds=embed)

    @gank.subcommand("events", sub_cmd_description="Timeline chronologique des tentatives de gank", options=_game_options())
    async def events(self, ctx: SlashContext, riot_id: str, riot_tag: str = None, numerogame: int = 0, match_id: str = None):
        await ctx.defer(ephemeral=False)
        riot_id, riot_tag, payload, error = await self._context(riot_id, riot_tag, numerogame, match_id)
        if error:
            return await ctx.send(error)

        match, team_id, summary, events = payload
        if events.empty:
            return await ctx.send("Aucune tentative de gank détectée sur cette partie.")

        ally_champ = str(summary.get("ally_jungler_champion") or "?")
        lines = []
        for _, row in events.iterrows():
            is_ally = _safe_int(row.get("team_id")) == team_id
            side = "🔵" if is_ally else "🔴"
            champ = str(row.get("jungler_champion") or "?")
            champ_emoji = _champion_emoji(champ)
            lane = LANE_LABELS.get(str(row.get("lane") or "").lower(), str(row.get("lane") or "?").upper())
            outcome = OUTCOME_LABELS.get(str(row.get("outcome")), str(row.get("outcome") or "—"))
            source = SOURCE_LABELS.get(str(row.get("detection_source")), str(row.get("detection_source") or "—"))
            confidence = _safe_float(row.get("confidence"))
            counter = " · 🔁 counter" if _safe_bool(row.get("is_counter_gank")) else ""
            kda = f"{_safe_int(row.get('jungler_kills'))}/{_safe_int(row.get('jungler_deaths'))}/{_safe_int(row.get('jungler_assists'))}"
            lines.append(
                f"{side} **{_format_time(row.get('timestamp_ms'))} {lane}** · {champ_emoji} {champ} · {outcome}{counter}\n"
                f"↳ K/D/A jungler **{kda}** · {source} · confiance **{confidence:.0%}**"
            )

        pages = []
        for start in range(0, len(lines), 8):
            embed = self._base_embed(
                f"Timeline ganks — {riot_id.upper()} #{riot_tag}",
                match,
                numerogame,
                match_id,
                ally_champ,
            )
            embed.add_field(
                name=f"Tentatives {start + 1}–{min(start + 8, len(lines))}",
                value="\n\n".join(lines[start:start + 8])[:1024],
                inline=False,
            )
            pages.append(embed)

        if len(pages) == 1:
            return await ctx.send(embeds=pages[0])
        paginator = Paginator.create_from_embeds(self.bot, *pages)
        paginator.show_select_menu = True
        await paginator.send(ctx)

    @gank.subcommand("lanes", sub_cmd_description="Compare les appuis TOP / MID / BOT", options=_game_options())
    async def lanes(self, ctx: SlashContext, riot_id: str, riot_tag: str = None, numerogame: int = 0, match_id: str = None):
        await ctx.defer(ephemeral=False)
        riot_id, riot_tag, payload, error = await self._context(riot_id, riot_tag, numerogame, match_id)
        if error:
            return await ctx.send(error)

        match, team_id, summary, events = payload
        enemy_team = 200 if team_id == 100 else 100
        ally_champ = str(summary.get("ally_jungler_champion") or "?")
        embed = self._base_embed(
            f"Appuis par lane — {riot_id.upper()} #{riot_tag}",
            match,
            numerogame,
            match_id,
            ally_champ,
        )

        for lane in LANES:
            lane_rows = events[events["lane"].astype(str).str.lower() == lane] if not events.empty else events
            ally = lane_rows[pd.to_numeric(lane_rows["team_id"], errors="coerce") == team_id] if not lane_rows.empty else lane_rows
            enemy = lane_rows[pd.to_numeric(lane_rows["team_id"], errors="coerce") == enemy_team] if not lane_rows.empty else lane_rows

            def line(rows: pd.DataFrame, icon: str) -> str:
                total = len(rows)
                successes = int(rows["successful"].apply(_safe_bool).sum()) if total else 0
                phases = {
                    phase: int((rows["game_phase"].astype(str).str.lower() == phase).sum()) if total else 0
                    for phase in ("early", "mid", "late")
                }
                return (
                    f"{icon} **{total}** tentatives · **{successes}** succès ({_pct(successes, total)}) · "
                    f"E/M/L **{phases['early']}/{phases['mid']}/{phases['late']}**"
                )

            embed.add_field(
                name=LANE_LABELS[lane],
                value=f"{line(ally, '🔵')}\n{line(enemy, '🔴')}",
                inline=False,
            )
        await ctx.send(embeds=embed)

    @gank.subcommand("records", sub_cmd_description="Records de ganks sur les parties enregistrées", options=_record_options())
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
        ]
        params = {"mode": mode}
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
                    COUNT(*) FILTER (WHERE game_phase = 'early') AS gank_early,
                    MIN(timestamp_ms) FILTER (WHERE successful = true) AS first_successful_gank
                FROM match_gank_events
                GROUP BY match_id, team_id
            )
            SELECT
                matchs.match_id,
                matchs.champion,
                matchs.url,
                matchs.season,
                tracker.riot_id,
                tracker.riot_tagline,
                gs.total_ganks_made,
                gs.total_ganks_received,
                gs.successful_made,
                gs.failed_made,
                gs.counter_ganks,
                gs.differential,
                CASE
                    WHEN gs.total_ganks_made >= 4
                    THEN 100.0 * gs.successful_made / NULLIF(gs.total_ganks_made, 0)
                END AS gank_success_rate,
                ea.gank_early,
                ea.first_successful_gank
            FROM matchs
            INNER JOIN tracker ON tracker.id_compte = matchs.joueur
            INNER JOIN match_gank_summary AS gs
                ON gs.match_id = matchs.match_id
               AND gs.team_id = CASE WHEN matchs.id_participant < 5 THEN 100 ELSE 200 END
            LEFT JOIN event_agg AS ea
                ON ea.match_id = matchs.match_id
               AND ea.team_id = gs.team_id
            WHERE {' AND '.join(conditions)}
        """
        df = lire_bdd_perso(query, index_col=None, params=params).T
        if df.empty:
            return await ctx.send("Aucune donnée de gank disponible pour ce périmètre.")

        records = [
            ("total_ganks_made", "PLUS DE TENTATIVES", "max", "int"),
            ("successful_made", "PLUS DE GANKS RÉUSSIS", "max", "int"),
            ("gank_success_rate", "MEILLEUR TAUX (MIN. 4)", "max", "pct"),
            ("failed_made", "PLUS DE TENTATIVES RATÉES", "max", "int"),
            ("counter_ganks", "PLUS DE COUNTER-GANKS", "max", "int"),
            ("differential", "PLUS GROS DIFFÉRENTIEL", "max", "signed"),
            ("gank_early", "PLUS DE GANKS AVANT 14 MIN", "max", "int"),
            ("first_successful_gank", "GANK RÉUSSI LE PLUS TÔT", "min", "time"),
            ("total_ganks_received", "PLUS FORTE PRESSION JUNGLE ENNEMIE", "max", "int"),
        ]

        title_scope = "serveur" if scope == "server" else "global"
        title_season = f"S{season}" if season != 0 else "toutes saisons"
        embed = interactions.Embed(
            title=f"Records ganks — {mode} {title_season} — {title_scope}",
            color=interactions.Color.random(),
        )

        for column, label, method, fmt in records:
            numeric = pd.to_numeric(df[column], errors="coerce")
            valid = df[numeric.notna()].copy()
            if valid.empty:
                continue
            valid["_value"] = pd.to_numeric(valid[column], errors="coerce")
            record_value = valid["_value"].min() if method == "min" else valid["_value"].max()
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
                emoji = _champion_emoji(champion)
                player = str(row.get("riot_id") or "?")
                tag = str(row.get("riot_tagline") or "")
                lines.append(f"{emoji} **{player} #{tag}** · {champion} · `{row.get('match_id')}`")
            embed.add_field(
                name=f"{label} — {display_value}",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(text=f"Ganks V2 · Version {Version}")
        await ctx.send(embeds=embed)

    @resume.autocomplete("riot_id")
    async def autocomplete_resume(self, ctx: interactions.AutocompleteContext):
        await ctx.send(choices=await autocomplete_riotid(int(ctx.guild.id), ctx.input_text))

    @events.autocomplete("riot_id")
    async def autocomplete_events(self, ctx: interactions.AutocompleteContext):
        await ctx.send(choices=await autocomplete_riotid(int(ctx.guild.id), ctx.input_text))

    @lanes.autocomplete("riot_id")
    async def autocomplete_lanes(self, ctx: interactions.AutocompleteContext):
        await ctx.send(choices=await autocomplete_riotid(int(ctx.guild.id), ctx.input_text))
