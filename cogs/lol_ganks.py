import pandas as pd
import interactions
from interactions import Extension, SlashContext, SlashCommandOption, slash_command
from interactions.ext.paginators import Paginator

from fonctions.gestion_bdd import lire_bdd_perso


EVENTS_PER_PAGE = 5

LANE_LABELS = {
    "top": "Top",
    "mid": "Mid",
    "bot": "Bot",
    "jungle": "Jungle",
}

PHASE_LABELS = {
    "early": "Début de partie",
    "mid": "Milieu de partie",
    "late": "Fin de partie",
}

STYLE_LABELS = {
    "early_aggro": "Agressif en début de partie",
    "balanced": "Équilibré",
    "mid_focused": "Très actif en milieu de partie",
    "late_scaler": "Plutôt orienté fin de partie",
    "passive": "Peu actif en gank",
}

OUTCOME_LABELS = {
    "success": ("✅", "Réussi"),
    "trade": ("🔁", "Échange de kills"),
    "failed": ("⚪", "Sans kill"),
    "jungler_death": ("💀", "Jungler mort"),
}

SOURCE_LABELS = {
    "exact_event": "Événement de combat exact",
    "sampled_combat": "Combat détecté entre deux relevés",
    "inferred_combat": "Tentative de gank inférée",
}

POSITION_LABELS = {
    "exact_event": "confirmée par l'événement",
    "both": "confirmée avant et après l'action",
    "start": "confirmée au début de l'action",
    "end": "confirmée à la fin de l'action",
    "none": "non confirmée par la position échantillonnée",
}

SIDE_LABELS = {
    "ally": "Équipe suivie",
    "enemy": "Équipe adverse",
    "even": "Égalité",
    "none": "Aucune",
}


class LolGanks(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @slash_command(
        name="lol_ganks",
        description="Affiche une analyse lisible des ganks d'une partie LoL",
        options=[
            SlashCommandOption(
                name="match_id",
                description="ID Riot du match, ex. EUW1_1234567890 (le numéro seul fonctionne aussi)",
                type=interactions.OptionType.STRING,
                required=True,
            )
        ],
    )
    async def lol_ganks(self, ctx: SlashContext, match_id: str):
        await ctx.defer(ephemeral=False)

        normalized_match_id = self._normalize_match_id(match_id)

        summaries = lire_bdd_perso(
            """
            SELECT *
            FROM match_gank_summary
            WHERE match_id = :match_id
            ORDER BY team_id
            """,
            params={"match_id": normalized_match_id},
            index_col=None,
        ).T

        events = lire_bdd_perso(
            """
            SELECT *
            FROM match_gank_events
            WHERE match_id = :match_id
            ORDER BY timestamp_ms, team_id, gank_id
            """,
            params={"match_id": normalized_match_id},
            index_col=None,
        ).T

        if summaries.empty and events.empty:
            return await ctx.send(
                f":x: Aucune donnée de gank trouvée pour `{normalized_match_id}`. "
                "Vérifie l'ID du match et que son analyse de ganks a bien été enregistrée."
            )

        embeds = []
        tracked_team_ids = self._tracked_team_ids(summaries)

        if summaries.empty:
            embeds.append(self._build_missing_summary_embed(normalized_match_id, len(events)))
        else:
            for _, summary in summaries.iterrows():
                embeds.append(self._build_summary_embed(normalized_match_id, summary, len(events)))

        if not events.empty:
            for start in range(0, len(events), EVENTS_PER_PAGE):
                page = events.iloc[start:start + EVENTS_PER_PAGE]
                embeds.append(
                    self._build_events_embed(
                        match_id=normalized_match_id,
                        page=page,
                        first_event_number=start + 1,
                        total_events=len(events),
                        tracked_team_ids=tracked_team_ids,
                    )
                )

        total_pages = len(embeds)
        for page_number, embed in enumerate(embeds, start=1):
            embed.set_footer(text=f"Match {normalized_match_id} • Page {page_number}/{total_pages}")

        if len(embeds) == 1:
            await ctx.send(embeds=embeds[0])
            return

        paginator = Paginator.create_from_embeds(self.bot, *embeds)
        paginator.show_select_menu = True
        await paginator.send(ctx)

    @staticmethod
    def _normalize_match_id(match_id: str) -> str:
        value = str(match_id or "").strip().upper()
        if value.isdigit():
            return f"EUW1_{value}"
        if value.startswith("EUW1-"):
            return value.replace("EUW1-", "EUW1_", 1)
        return value

    @staticmethod
    def _tracked_team_ids(summaries) -> set[int]:
        team_ids = set()
        if summaries.empty or "team_id" not in summaries.columns:
            return team_ids
        for value in summaries["team_id"]:
            clean = LolGanks._clean(value)
            if clean is not None:
                team_ids.add(int(clean))
        return team_ids

    @staticmethod
    def _clean(value, default=None):
        if value is None:
            return default
        try:
            if pd.isna(value):
                return default
        except (TypeError, ValueError):
            pass
        return value

    @classmethod
    def _get(cls, row, key, default=None):
        if key not in row.index:
            return default
        return cls._clean(row[key], default)

    @classmethod
    def _as_int(cls, value, default=0) -> int:
        value = cls._clean(value)
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _format_percent(cls, value) -> str:
        value = cls._clean(value)
        if value is None:
            return "—"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "—"
        if abs(numeric) <= 1:
            numeric *= 100
        return f"{numeric:.0f} %"

    @classmethod
    def _format_lane(cls, value) -> str:
        value = cls._clean(value)
        if value is None:
            return "—"
        return LANE_LABELS.get(str(value).lower(), str(value).title())

    @classmethod
    def _format_style(cls, value) -> str:
        value = cls._clean(value)
        if value is None:
            return "—"
        return STYLE_LABELS.get(str(value).lower(), str(value).replace("_", " ").title())

    @classmethod
    def _format_side(cls, value) -> str:
        value = cls._clean(value)
        if value is None:
            return "—"
        return SIDE_LABELS.get(str(value).lower(), str(value).replace("_", " ").title())

    @classmethod
    def _format_bool(cls, value) -> str:
        value = cls._clean(value)
        if value is None:
            return "—"
        return "Oui" if bool(value) else "Non"

    @classmethod
    def _format_diff(cls, value) -> str:
        numeric = cls._as_int(value)
        return f"+{numeric}" if numeric > 0 else str(numeric)

    @classmethod
    def _format_jungler(cls, row, prefix: str) -> str:
        name = cls._get(row, f"{prefix}_jungler_name", "Nom inconnu")
        champion = cls._get(row, f"{prefix}_jungler_champion", "Champion inconnu")
        return f"**{name}** — {champion}"

    @classmethod
    def _format_first_gank(cls, row, prefix: str) -> str:
        timestamp = cls._get(row, f"{prefix}_first_gank_time")
        lane = cls._get(row, f"{prefix}_first_gank_lane")
        success = cls._get(row, f"{prefix}_first_gank_success")

        if timestamp is None:
            return "Aucun gank détecté"

        status = "réussi" if bool(success) else "sans kill"
        return f"**{timestamp}** sur **{cls._format_lane(lane)}** ({status})"

    @classmethod
    def _build_summary_embed(cls, match_id: str, row, total_events: int):
        ally_total = cls._as_int(cls._get(row, "total_ganks_made"))
        enemy_total = cls._as_int(cls._get(row, "total_ganks_received"))
        ally_success = cls._as_int(cls._get(row, "successful_made"))
        enemy_success = cls._as_int(cls._get(row, "successful_received"))

        ally_rate = cls._get(
            row,
            "observed_success_rate_made",
            cls._get(row, "success_rate_made"),
        )
        enemy_rate = cls._get(
            row,
            "observed_death_rate_received",
            cls._get(row, "death_rate_received"),
        )

        team_id = cls._get(row, "team_id")
        team_suffix = ""
        if team_id is not None:
            team_suffix = f" • équipe {cls._team_color_name(team_id)}"

        embed = interactions.Embed(
            title="🧭 Analyse des ganks",
            description=(
                f"Résumé du duel jungle pour `{match_id}`{team_suffix}.\n"
                "Les termes techniques stockés en base sont traduits ci-dessous pour faciliter la lecture."
            ),
            color=interactions.Color.random(),
        )

        embed.add_field(
            name="🥊 Duel des junglers",
            value=(
                f"**Équipe suivie :** {cls._format_jungler(row, 'ally')}\n"
                f"**Équipe adverse :** {cls._format_jungler(row, 'enemy')}"
            ),
            inline=False,
        )

        embed.add_field(
            name="📊 Volume et efficacité",
            value=(
                f"**Équipe suivie :** {ally_total} tentatives • {ally_success} réussies • "
                f"{cls._format_percent(ally_rate)} de réussite\n"
                f"**Équipe adverse :** {enemy_total} tentatives • {enemy_success} réussies • "
                f"{cls._format_percent(enemy_rate)} de réussite\n"
                f"**Différentiel :** {cls._format_diff(cls._get(row, 'differential'))} gank(s)"
            ),
            inline=False,
        )

        embed.add_field(
            name="⏱️ Tempo",
            value=(
                f"**Premier gank allié :** {cls._format_first_gank(row, 'ally')}\n"
                f"**Premier gank adverse :** {cls._format_first_gank(row, 'enemy')}\n"
                f"**Premier à agir :** {cls._format_side(cls._get(row, 'first_to_gank'))}\n"
                f"**Avantage en début de partie :** {cls._format_side(cls._get(row, 'early_winner'))}"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎯 Priorités de lanes",
            value=(
                f"**Lane la plus gankée par l'équipe suivie :** "
                f"{cls._format_lane(cls._get(row, 'most_ganked_by_ally'))}\n"
                f"**Lane la plus ciblée par l'adversaire :** "
                f"{cls._format_lane(cls._get(row, 'most_targeted_by_enemy'))}\n"
                f"**Counter-ganks détectés :** {cls._as_int(cls._get(row, 'counter_ganks'))}"
            ),
            inline=False,
        )

        embed.add_field(
            name="🧠 Lecture du duel",
            value=(
                f"**Domination jungle :** {cls._format_side(cls._get(row, 'jungle_dominance'))}\n"
                f"**Style allié :** {cls._format_style(cls._get(row, 'ally_style'))}\n"
                f"**Style adverse :** {cls._format_style(cls._get(row, 'enemy_style'))}"
            ),
            inline=False,
        )

        if cls._get(row, "algorithm_version") is not None:
            embed.add_field(
                name="🔎 Qualité de la détection",
                value=(
                    f"**Tentatives exactes :** {cls._as_int(cls._get(row, 'exact_attempts_made'))} alliées / "
                    f"{cls._as_int(cls._get(row, 'exact_attempts_received'))} adverses\n"
                    f"**Tentatives inférées :** {cls._as_int(cls._get(row, 'inferred_attempts_made'))} alliées / "
                    f"{cls._as_int(cls._get(row, 'inferred_attempts_received'))} adverses\n"
                    f"**Haute confiance :** {cls._as_int(cls._get(row, 'high_confidence_made'))} alliées / "
                    f"{cls._as_int(cls._get(row, 'high_confidence_received'))} adverses\n"
                    f"**Tentatives sans kill :** {cls._as_int(cls._get(row, 'failed_made'))} alliées / "
                    f"{cls._as_int(cls._get(row, 'failed_received'))} adverses\n"
                    f"**Version de l'analyse :** v{cls._as_int(cls._get(row, 'algorithm_version'))}"
                ),
                inline=False,
            )

        embed.add_field(
            name="📚 Détail disponible",
            value=f"{total_events} tentative(s) de gank enregistrée(s) dans `match_gank_events`.",
            inline=False,
        )

        return embed

    @classmethod
    def _build_missing_summary_embed(cls, match_id: str, total_events: int):
        embed = interactions.Embed(
            title="🧭 Analyse des ganks",
            description=(
                f"Des événements existent pour `{match_id}`, mais aucun résumé n'a été trouvé dans "
                "`match_gank_summary`. Les pages suivantes affichent tout de même les tentatives détectées."
            ),
            color=interactions.Color.random(),
        )
        embed.add_field(
            name="📚 Événements disponibles",
            value=f"{total_events} tentative(s) enregistrée(s).",
            inline=False,
        )
        return embed

    @classmethod
    def _build_events_embed(
        cls,
        match_id: str,
        page,
        first_event_number: int,
        total_events: int,
        tracked_team_ids: set[int],
    ):
        last_event_number = first_event_number + len(page) - 1
        embed = interactions.Embed(
            title="🎬 Chronologie des ganks",
            description=(
                f"Tentatives **{first_event_number} à {last_event_number}** sur **{total_events}** "
                f"pour `{match_id}`. Elles sont affichées dans l'ordre du match."
            ),
            color=interactions.Color.random(),
        )

        for offset, (_, event) in enumerate(page.iterrows()):
            event_number = first_event_number + offset
            timestamp = cls._get(event, "timestamp_formatted", "—")
            lane = cls._format_lane(cls._get(event, "lane"))
            phase = PHASE_LABELS.get(
                str(cls._get(event, "game_phase", "")).lower(),
                str(cls._get(event, "game_phase", "—")).replace("_", " ").title(),
            )

            outcome = str(cls._get(event, "outcome", "success" if cls._get(event, "successful") else "failed")).lower()
            icon, outcome_label = OUTCOME_LABELS.get(
                outcome,
                ("ℹ️", outcome.replace("_", " ").title()),
            )

            source = str(cls._get(event, "detection_source", "exact_event")).lower()
            source_label = SOURCE_LABELS.get(source, source.replace("_", " ").title())
            confidence = cls._format_percent(cls._get(event, "confidence", 1.0))

            team_id = cls._as_int(cls._get(event, "team_id"), default=-1)
            team_label = cls._event_team_label(team_id, tracked_team_ids)
            champion = cls._get(event, "jungler_champion", "Champion inconnu")

            kills_for = cls._as_int(cls._get(event, "kills_for"))
            kills_against = cls._as_int(cls._get(event, "kills_against"))
            jungler_kills = cls._as_int(cls._get(event, "jungler_kills"))
            jungler_assists = cls._as_int(cls._get(event, "jungler_assists"))
            jungler_deaths = cls._as_int(cls._get(event, "jungler_deaths"))

            allies = cls._get(event, "participants_allies")
            enemies = cls._get(event, "participants_enemies")
            participants_line = ""
            if allies is not None and enemies is not None:
                participants_line = (
                    f"\n**Participants :** {cls._as_int(allies)} allié(s) vs {cls._as_int(enemies)} ennemi(s)"
                )

            context_parts = []
            if bool(cls._get(event, "is_counter_gank", False)):
                context_parts.append("counter-gank")

            position = cls._get(event, "position_evidence")
            if position is not None:
                context_parts.append(
                    f"position {POSITION_LABELS.get(str(position).lower(), str(position))}"
                )

            jungler_damage = cls._as_int(cls._get(event, "jungler_damage_delta"))
            lane_activity = cls._as_int(cls._get(event, "lane_activity_delta"))
            if source != "exact_event" and (jungler_damage or lane_activity):
                context_parts.append(
                    f"signal combat : +{jungler_damage} dégâts jungler / +{lane_activity} activité lane"
                )

            context_line = ""
            if context_parts:
                context_line = f"\n**Contexte :** {' • '.join(context_parts)}"

            embed.add_field(
                name=f"{icon} #{event_number} • {timestamp} • {lane} • {outcome_label}",
                value=(
                    f"**Équipe :** {team_label}\n"
                    f"**Jungler :** {champion}\n"
                    f"**Phase :** {phase}\n"
                    f"**Détection :** {source_label} • confiance {confidence}\n"
                    f"**Bilan de l'action :** {kills_for} kill(s) pour / {kills_against} contre\n"
                    f"**Jungler sur l'action :** {jungler_kills} kill(s), {jungler_assists} assist(s), "
                    f"{jungler_deaths} mort(s)"
                    f"{participants_line}{context_line}"
                ),
                inline=False,
            )

        return embed

    @staticmethod
    def _team_color_name(team_id) -> str:
        try:
            team_id = int(team_id)
        except (TypeError, ValueError):
            return str(team_id)
        if team_id == 100:
            return "bleue"
        if team_id == 200:
            return "rouge"
        return str(team_id)

    @classmethod
    def _event_team_label(cls, team_id: int, tracked_team_ids: set[int]) -> str:
        if team_id == -1:
            return "Équipe inconnue"

        label = f"Équipe {cls._team_color_name(team_id)}"
        if len(tracked_team_ids) == 1:
            tracked_team = next(iter(tracked_team_ids))
            if team_id == tracked_team:
                return f"{label} (équipe suivie)"
            return f"{label} (équipe adverse)"
        return label
