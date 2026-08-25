import re

import interactions
import pandas as pd
from interactions import Extension, SlashCommandOption, SlashContext, slash_command
from interactions.ext.paginators import Paginator

from fonctions.autocomplete import autocomplete_riotid
from fonctions.gestion_bdd import get_tag, lire_bdd_perso
from utils.emoji import emote_champ_discord


TAKEN_COLUMNS = (
    "damage_taken_frame_window",
    "physical_damage_taken_frame_window",
    "magic_damage_taken_frame_window",
    "true_damage_taken_frame_window",
)


def _normalize_champion(champion: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(champion or "").lower())


_CHAMPION_EMOJIS = {
    _normalize_champion(champion): emoji
    for champion, emoji in emote_champ_discord.items()
}


def _champion_emoji(champion: str) -> str:
    return _CHAMPION_EMOJIS.get(_normalize_champion(champion), "")


def _champion_icon_url(champion: str) -> str | None:
    """Réutilise l'image du custom emoji de champion déjà employé par le bot."""
    match = re.search(r"<a?:[^:]+:(\d+)>", _champion_emoji(champion))
    if match is None:
        return None
    return (
        f"https://cdn.discordapp.com/emojis/{match.group(1)}.png"
        "?size=128&quality=lossless"
    )


def _has_value(value) -> bool:
    return value is not None and not pd.isna(value)


def _safe_bool(value) -> bool:
    if isinstance(value, str):
        return value.lower() in {"true", "t", "1", "yes"}
    if not _has_value(value):
        return False
    return bool(value)


def _safe_int(value) -> int:
    try:
        if not _has_value(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _damage_value(value) -> float:
    try:
        if not _has_value(value):
            return 0.0
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, numeric)


def _format_damage(value) -> str:
    return f"{int(round(_damage_value(value))):,}".replace(",", " ")


def _format_damage_or_na(value) -> str:
    return _format_damage(value) if _has_value(value) else "N/A"


def _format_timestamp(timestamp_ms) -> str:
    try:
        seconds = max(0, int(float(timestamp_ms)) // 1000)
    except (TypeError, ValueError):
        seconds = 0
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _same_team(team_a, team_b) -> bool:
    if not _has_value(team_a) or not _has_value(team_b):
        return False
    return str(team_a) == str(team_b)


def _is_tie(winner) -> bool:
    return str(winner).lower() in {"égalité", "egalite", "draw", "tie"}


def _fight_result(player_row: pd.Series) -> tuple[str, bool | None]:
    winner = player_row.get("winner")
    if not _has_value(winner) or _is_tie(winner):
        return "⚪", None

    won = _same_team(player_row.get("team"), winner)
    return ("🟢" if won else "🔴"), won


def _fight_kda(row: pd.Series) -> str:
    return (
        f"{_safe_int(row.get('fight_kills'))}/"
        f"{_safe_int(row.get('fight_deaths'))}/"
        f"{_safe_int(row.get('fight_assists'))}"
    )


def _fight_label(row: pd.Series) -> str:
    core = row.get("fight_type")
    proximity = row.get("fight_type_with_proximity")
    category = row.get("fight_category")

    if _has_value(core) and str(core).strip():
        if (
            _has_value(proximity)
            and str(proximity).strip()
            and str(proximity) != str(core)
        ):
            return f"{core} (avec proximité {proximity})"
        return str(core)

    if _has_value(category) and str(category).strip():
        return str(category)

    return "combat"


def _compact_fight_label(row: pd.Series, tracked: pd.Series) -> str:
    """Version courte pour la timeline de /teamfight combats."""
    core = row.get("fight_type")
    proximity = row.get("fight_type_with_proximity")
    category = row.get("fight_category")

    if _has_value(core) and str(core).strip():
        label = str(core)
    elif _has_value(category) and str(category).strip():
        label = str(category)
    else:
        label = "combat"

    if (
        _has_value(proximity)
        and str(proximity).strip()
        and str(proximity) != label
    ):
        return f"**{label}** · prox {proximity}"

    if _safe_bool(tracked.get("is_proximity_participant")):
        return f"**{label}** · prox"

    return f"**{label}**"


def _tracked_row(fight_df: pd.DataFrame, analyzed_puuid: str) -> pd.Series | None:
    tracked = fight_df[fight_df["puuid"].astype(str) == str(analyzed_puuid)]
    return None if tracked.empty else tracked.iloc[0]


def _team_damage(fight_df: pd.DataFrame, team) -> float:
    """Somme d'équipe fondée exclusivement sur damage_frame_window."""
    team_rows = fight_df[fight_df["team"].astype(str) == str(team)]
    return float(
        pd.to_numeric(team_rows["damage_frame_window"], errors="coerce")
        .fillna(0)
        .clip(lower=0)
        .sum()
    )


def _damage_share(fight_df: pd.DataFrame, player_row: pd.Series) -> float:
    """Part de dégâts fondée exclusivement sur damage_frame_window."""
    team_total = _team_damage(fight_df, player_row.get("team"))
    if team_total <= 0:
        return 0.0
    return 100.0 * _damage_value(player_row.get("damage_frame_window")) / team_total


def _damage_taken_available(row: pd.Series) -> bool:
    return _has_value(row.get("damage_taken_frame_window"))


def _damage_ratio(row: pd.Series) -> str:
    """Ratio dégâts champions infligés / dégâts toutes sources reçus."""
    if not _damage_taken_available(row):
        return "N/A"

    taken = _damage_value(row.get("damage_taken_frame_window"))
    if taken <= 0:
        return "—"

    dealt = _damage_value(row.get("damage_frame_window"))
    return f"{dealt / taken:.2f}"


def _taken_breakdown(row: pd.Series) -> str:
    if not _damage_taken_available(row):
        return "Dégâts reçus : **N/A**"

    return (
        f"🛡️ **{_format_damage(row.get('damage_taken_frame_window'))} reçus**\n"
        f"↳ Physique **{_format_damage_or_na(row.get('physical_damage_taken_frame_window'))}** · "
        f"Magique **{_format_damage_or_na(row.get('magic_damage_taken_frame_window'))}** · "
        f"True **{_format_damage_or_na(row.get('true_damage_taken_frame_window'))}**"
    )


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
            description="Match ID Riot (prioritaire sur numerogame si renseigné)",
            type=interactions.OptionType.STRING,
            required=False,
        ),
    ]


def _detail_options():
    return [
        SlashCommandOption(
            name="riot_id",
            description="Joueur",
            type=interactions.OptionType.STRING,
            required=True,
            autocomplete=True,
        ),
        SlashCommandOption(
            name="fight",
            description="Identifiant du combat",
            type=interactions.OptionType.INTEGER,
            required=True,
            min_value=1,
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
            description="Match ID Riot (prioritaire sur numerogame si renseigné)",
            type=interactions.OptionType.STRING,
            required=False,
        ),
    ]


class Teamfight(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @staticmethod
    def _resolve_account(
        riot_id: str,
        riot_tag: str | None,
    ) -> tuple[str, str]:
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
        """Sélectionne par match_id s'il est fourni, sinon par numerogame."""
        if match_id is not None and str(match_id).strip():
            requested = str(match_id).strip()
            requested_without_prefix = requested.replace("EUW1_", "")
            df = lire_bdd_perso(
                """
                SELECT
                    matchs.match_id,
                    tracker.puuid AS analyzed_puuid,
                    matchs.datetime
                FROM matchs
                INNER JOIN tracker
                    ON tracker.id_compte = matchs.joueur
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
                    tracker.puuid AS analyzed_puuid,
                    matchs.datetime
                FROM matchs
                INNER JOIN tracker
                    ON tracker.id_compte = matchs.joueur
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
    def _load_teamfights(match_id, analyzed_puuid: str) -> pd.DataFrame:
        """Charge les données nécessaires aux trois affichages Teamfight."""
        return lire_bdd_perso(
            """
            SELECT
                match_id,
                analyzed_puuid,
                fight_id,
                participant_id,
                puuid,
                player_name,
                champion,
                team,
                start_ms,
                end_ms,
                winner,
                fight_type,
                fight_type_with_proximity,
                fight_category,
                is_teamfight,
                outnumbered_team,
                won_while_outnumbered,
                is_core_participant,
                is_proximity_participant,
                fight_kills,
                fight_deaths,
                fight_assists,
                survived,
                damage_frame_window,
                damage_taken_frame_window,
                physical_damage_taken_frame_window,
                magic_damage_taken_frame_window,
                true_damage_taken_frame_window
            FROM match_teamfight_damage
            WHERE match_id = :match_id
              AND analyzed_puuid = :analyzed_puuid
            ORDER BY fight_id, participant_id
            """,
            index_col=None,
            params={
                "match_id": match_id,
                "analyzed_puuid": analyzed_puuid,
            },
        ).T

    async def _load_context(
        self,
        riot_id: str,
        riot_tag: str | None,
        numerogame: int,
        match_id: str | None = None,
    ):
        try:
            riot_id, riot_tag = self._resolve_account(riot_id, riot_tag)
        except (ValueError, KeyError, IndexError):
            return None, None, None, (
                "Compte introuvable ou Riot ID ambigu. Merci de préciser le tag."
            )

        match = self._load_selected_match(
            riot_id,
            riot_tag,
            numerogame,
            match_id=match_id,
        )
        if match is None:
            if match_id:
                return None, None, None, (
                    f"Le match `{match_id}` est introuvable pour ce joueur."
                )
            return None, None, None, "Cette partie enregistrée est introuvable."

        fights = self._load_teamfights(
            match["match_id"],
            str(match["analyzed_puuid"]),
        )
        if fights.empty:
            return None, None, None, (
                "Cette partie existe, mais aucune donnée de teamfight "
                "n'est enregistrée pour elle."
            )

        return riot_id, riot_tag, (match, fights), None

    @staticmethod
    def _player_fights(
        fights: pd.DataFrame,
        analyzed_puuid: str,
    ) -> list[tuple[object, pd.DataFrame, pd.Series]]:
        player_fights = []
        for fight_id, fight_df in fights.groupby("fight_id", sort=True):
            tracked = _tracked_row(fight_df, analyzed_puuid)
            if tracked is not None:
                player_fights.append((fight_id, fight_df, tracked))
        return player_fights

    @staticmethod
    def _base_embed(
        title: str,
        champion: str,
        selected_match_id,
        numerogame: int,
        requested_match_id: str | None,
    ) -> interactions.Embed:
        if requested_match_id:
            description = f"Match ID · `{selected_match_id}`"
        else:
            description = f"Partie #{numerogame} · `{selected_match_id}`"

        embed = interactions.Embed(
            title=title,
            description=description,
            color=interactions.Color.random(),
        )

        icon_url = _champion_icon_url(champion)
        if icon_url:
            embed.set_thumbnail(url=icon_url)

        return embed

    @classmethod
    def _build_pages(
        cls,
        title: str,
        champion: str,
        selected_match_id,
        numerogame: int,
        requested_match_id: str | None,
        fields: list[tuple[str, str, bool]],
        max_content_chars: int = 4800,
        max_fields: int = 20,
    ) -> list[interactions.Embed]:
        """Construit plusieurs embeds avant d'approcher les limites Discord."""
        pages = []
        current_fields = []
        current_chars = 0

        for name, value, inline in fields:
            name = str(name)
            value = str(value)
            field_chars = len(name) + len(value)

            if current_fields and (
                len(current_fields) >= max_fields
                or current_chars + field_chars > max_content_chars
            ):
                page = cls._base_embed(
                    title,
                    champion,
                    selected_match_id,
                    numerogame,
                    requested_match_id,
                )
                for field_name, field_value, field_inline in current_fields:
                    page.add_field(
                        name=field_name,
                        value=field_value,
                        inline=field_inline,
                    )
                pages.append(page)
                current_fields = []
                current_chars = 0

            current_fields.append((name, value, inline))
            current_chars += field_chars

        if current_fields or not pages:
            page = cls._base_embed(
                title,
                champion,
                selected_match_id,
                numerogame,
                requested_match_id,
            )
            for field_name, field_value, field_inline in current_fields:
                page.add_field(
                    name=field_name,
                    value=field_value,
                    inline=field_inline,
                )
            pages.append(page)

        return pages

    async def _send_pages(
        self,
        ctx: SlashContext,
        pages: list[interactions.Embed],
    ) -> None:
        if len(pages) == 1:
            await ctx.send(embeds=pages[0])
            return

        paginator = Paginator.create_from_embeds(self.bot, *pages)
        paginator.show_select_menu = True
        await paginator.send(ctx)

    @staticmethod
    def _add_missing_taken_warning(
        embed: interactions.Embed,
        player_fights: list[tuple[object, pd.DataFrame, pd.Series]],
    ) -> None:
        if any(not _damage_taken_available(tracked) for _, _, tracked in player_fights):
            embed.add_field(
                name="⚠️ Dégâts reçus incomplets",
                value=(
                    "Au moins un combat n'a pas encore été backfill. "
                    "Les valeurs concernées sont affichées `N/A`."
                ),
                inline=False,
            )

    @slash_command(
        name="teamfight",
        description="Analyse des combats d'une partie League of Legends",
    )
    async def teamfight(self, ctx: SlashContext):
        pass

    @teamfight.subcommand(
        "resume",
        sub_cmd_description="Résumé des combats d'une partie",
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

        riot_id, riot_tag, payload, error = await self._load_context(
            riot_id,
            riot_tag,
            numerogame,
            match_id=match_id,
        )
        if error:
            return await ctx.send(error)

        match, fights = payload
        analyzed_puuid = str(match["analyzed_puuid"])
        player_fights = self._player_fights(fights, analyzed_puuid)
        if not player_fights:
            return await ctx.send(
                "Le joueur n'apparaît dans aucun combat détecté pour cette partie."
            )

        champion = str(player_fights[0][2].get("champion") or "?")
        champion_emoji = _champion_emoji(champion)
        embed = self._base_embed(
            f"Teamfights — {riot_id.upper()} #{riot_tag} — {champion}",
            champion,
            match["match_id"],
            numerogame,
            match_id,
        )

        teamfights = []
        skirmishes = 0
        duels = 0
        duels_won = 0
        outnumbered_wins = 0

        for fight_id, fight_df, tracked in player_fights:
            first = fight_df.iloc[0]
            category = str(first.get("fight_category") or "").lower()

            if _safe_bool(first.get("is_teamfight")):
                teamfights.append((fight_id, fight_df, tracked))
            if category == "skirmish":
                skirmishes += 1
            if category == "duel" and _safe_bool(tracked.get("is_core_participant")):
                duels += 1
                if _fight_result(tracked)[1] is True:
                    duels_won += 1
            if (
                _safe_bool(first.get("won_while_outnumbered"))
                and _same_team(
                    tracked.get("team"),
                    first.get("outnumbered_team"),
                )
            ):
                outnumbered_wins += 1

        wins = losses = ties = 0
        for _, _, tracked in teamfights:
            _, result = _fight_result(tracked)
            if result is True:
                wins += 1
            elif result is False:
                losses += 1
            else:
                ties += 1

        tf_line = (
            f"⚔️ **{len(teamfights)}** teamfights — "
            f"**{wins}** gagnés / **{losses}** perdus"
        )
        if ties:
            tf_line += f" / **{ties}** égalités"

        embed.add_field(
            name="Résumé",
            value="\n".join(
                [
                    (
                        f"{champion_emoji} **{champion}**"
                        if champion_emoji
                        else f"**{champion}**"
                    ),
                    tf_line,
                    f"🤺 **{skirmishes}** skirmishes",
                    f"🥊 **{duels}** duels — **{duels_won}** gagnés",
                    f"🔥 **{outnumbered_wins}** combats gagnés en infériorité",
                ]
            ),
            inline=False,
        )

        if teamfights:
            best_id, best_df, best_player = max(
                teamfights,
                key=lambda item: _damage_value(item[2].get("damage_frame_window")),
            )
            best_first = best_df.iloc[0]
            result_icon, _ = _fight_result(best_player)

            embed.add_field(
                name="Meilleur teamfight en dégâts infligés",
                value=(
                    f"{result_icon} **Fight #{best_id}** · "
                    f"{_format_timestamp(best_first.get('start_ms'))} → "
                    f"{_format_timestamp(best_first.get('end_ms'))}\n"
                    f"**{_fight_label(best_first)}** · "
                    f"KDA **{_fight_kda(best_player)}**\n"
                    f"🎯 **{_format_damage(best_player.get('damage_frame_window'))} "
                    f"infligés** · **{_damage_share(best_df, best_player):.1f}%** "
                    "des dégâts de l'équipe\n"
                    f"🛡️ **{_format_damage_or_na(best_player.get('damage_taken_frame_window'))} reçus**"
                ),
                inline=False,
            )

            teamfights_with_taken = [
                item for item in teamfights
                if _damage_taken_available(item[2])
            ]
            if teamfights_with_taken:
                taken_id, taken_df, taken_player = max(
                    teamfights_with_taken,
                    key=lambda item: _damage_value(
                        item[2].get("damage_taken_frame_window")
                    ),
                )
                taken_first = taken_df.iloc[0]
                taken_result_icon, _ = _fight_result(taken_player)
                survived = "✅" if _safe_bool(taken_player.get("survived")) else "❌"
                embed.add_field(
                    name="Plus de dégâts reçus en teamfight",
                    value=(
                        f"{taken_result_icon} **Fight #{taken_id}** · "
                        f"{_format_timestamp(taken_first.get('start_ms'))} → "
                        f"{_format_timestamp(taken_first.get('end_ms'))}\n"
                        f"**{_fight_label(taken_first)}** · "
                        f"KDA **{_fight_kda(taken_player)}** · Survie {survived}\n"
                        f"🛡️ **{_format_damage_or_na(taken_player.get('damage_taken_frame_window'))} reçus**\n"
                        f"🎯 **{_format_damage(taken_player.get('damage_frame_window'))} infligés** · "
                        f"Ratio **{_damage_ratio(taken_player)}**"
                    ),
                    inline=False,
                )

        self._add_missing_taken_warning(embed, player_fights)
        await ctx.send(embeds=embed)

    @teamfight.subcommand(
        "combats",
        sub_cmd_description="Liste chronologique des combats d'une partie",
        options=_game_options(),
    )
    async def combats(
        self,
        ctx: SlashContext,
        riot_id: str,
        riot_tag: str = None,
        numerogame: int = 0,
        match_id: str = None,
    ):
        await ctx.defer(ephemeral=False)

        riot_id, riot_tag, payload, error = await self._load_context(
            riot_id,
            riot_tag,
            numerogame,
            match_id=match_id,
        )
        if error:
            return await ctx.send(error)

        match, fights = payload
        analyzed_puuid = str(match["analyzed_puuid"])
        player_fights = self._player_fights(fights, analyzed_puuid)
        if not player_fights:
            return await ctx.send(
                "Le joueur n'apparaît dans aucun combat détecté pour cette partie."
            )

        champion = str(player_fights[0][2].get("champion") or "?")
        title = f"Combats — {riot_id.upper()} #{riot_tag} — {champion}"

        blocks = []
        for fight_id, fight_df, tracked in player_fights:
            first = fight_df.iloc[0]
            result_icon, _ = _fight_result(tracked)

            flags = []
            if (
                _safe_bool(first.get("won_while_outnumbered"))
                and _same_team(
                    tracked.get("team"),
                    first.get("outnumbered_team"),
                )
            ):
                flags.append("🔥")

            suffix = f" · {' · '.join(flags)}" if flags else ""
            blocks.append(
                (
                    f"{result_icon} **#{fight_id}** · "
                    f"{_format_timestamp(first.get('start_ms'))} · "
                    f"{_compact_fight_label(first, tracked)} · "
                    f"KDA **{_fight_kda(tracked)}**{suffix}\n"
                    f"↳ 🎯 **{_format_damage(tracked.get('damage_frame_window'))}** "
                    f"({_damage_share(fight_df, tracked):.1f}%) · "
                    f"🛡️ **{_format_damage_or_na(tracked.get('damage_taken_frame_window'))}**"
                )
            )

        chunks = []
        current = []
        current_length = 0
        for block in blocks:
            extra = len(block) + (2 if current else 0)
            if current and current_length + extra > 900:
                chunks.append("\n\n".join(current))
                current = []
                current_length = 0
            current.append(block)
            current_length += extra
        if current:
            chunks.append("\n\n".join(current))

        fields = []
        for index, chunk in enumerate(chunks, start=1):
            field_name = "Combats" if index == 1 else f"Combats (suite {index})"
            fields.append((field_name, chunk, False))

        fields.append(
            (
                "Légende",
                (
                    "🟢 gagné · 🔴 perdu · ⚪ égalité · 🔥 gagné en infériorité\n"
                    "🎯 dégâts infligés (% équipe) · 🛡️ dégâts reçus (toutes sources) · "
                    "prox = participants avec proximité"
                ),
                False,
            )
        )

        if any(
            not _damage_taken_available(tracked)
            for _, _, tracked in player_fights
        ):
            fields.append(
                (
                    "⚠️ Dégâts reçus incomplets",
                    (
                        "Au moins un combat n'a pas encore été backfill. "
                        "Les valeurs concernées sont affichées `N/A`."
                    ),
                    False,
                )
            )

        pages = self._build_pages(
            title,
            champion,
            match["match_id"],
            numerogame,
            match_id,
            fields,
        )
        await self._send_pages(ctx, pages)

    @teamfight.subcommand(
        "detail",
        sub_cmd_description="Détail joueur par joueur d'un combat",
        options=_detail_options(),
    )
    async def detail(
        self,
        ctx: SlashContext,
        riot_id: str,
        fight: int,
        riot_tag: str = None,
        numerogame: int = 0,
        match_id: str = None,
    ):
        await ctx.defer(ephemeral=False)

        riot_id, riot_tag, payload, error = await self._load_context(
            riot_id,
            riot_tag,
            numerogame,
            match_id=match_id,
        )
        if error:
            return await ctx.send(error)

        match, fights = payload
        selected = fights[
            pd.to_numeric(fights["fight_id"], errors="coerce") == int(fight)
        ].copy()
        if selected.empty:
            available = sorted(
                {
                    _safe_int(value)
                    for value in fights["fight_id"].tolist()
                    if _safe_int(value) > 0
                }
            )
            return await ctx.send(
                f"Fight #{fight} introuvable. "
                f"Fights disponibles : {', '.join(map(str, available)) or 'aucun'}."
            )

        analyzed_puuid = str(match["analyzed_puuid"])
        tracked = _tracked_row(selected, analyzed_puuid)
        if tracked is None:
            return await ctx.send(
                "Le joueur tracké ne participe pas à ce combat."
            )

        first = selected.iloc[0]
        champion = str(tracked.get("champion") or "?")
        champion_emoji = _champion_emoji(champion)
        result_icon, result = _fight_result(tracked)
        result_label = (
            "Victoire"
            if result is True
            else "Défaite"
            if result is False
            else "Égalité"
        )

        title = (
            f"{result_icon} Teamfight #{fight} — "
            f"{_format_timestamp(first.get('start_ms'))} → "
            f"{_format_timestamp(first.get('end_ms'))}"
        )
        fields = [
            (
                "Combat",
                f"**{_fight_label(first)}** · **{result_label}**",
                False,
            )
        ]

        tracked_team = tracked.get("team")
        teams = list(dict.fromkeys(selected["team"].astype(str).tolist()))
        teams.sort(key=lambda team: 0 if team == str(tracked_team) else 1)

        for team in teams:
            team_rows = selected[selected["team"].astype(str) == team].copy()
            team_rows["_damage_sort"] = team_rows["damage_frame_window"].apply(
                _damage_value
            )
            team_rows.sort_values(
                ["_damage_sort", "participant_id"],
                ascending=[False, True],
                inplace=True,
            )

            team_total = _team_damage(selected, team)
            player_lines = []
            for _, player in team_rows.iterrows():
                champ = str(player.get("champion") or "?")
                emoji = _champion_emoji(champ)
                icon_prefix = f"{emoji} " if emoji else ""
                proximity = (
                    " · *proximité*"
                    if _safe_bool(player.get("is_proximity_participant"))
                    else ""
                )
                player_damage = _damage_value(player.get("damage_frame_window"))
                share = (
                    100.0 * player_damage / team_total
                    if team_total > 0
                    else 0.0
                )

                player_lines.append(
                    f"{icon_prefix}**{champ}** · {_fight_kda(player)} · "
                    f"🎯 **{_format_damage(player_damage)}** ({share:.1f}%) · "
                    f"🛡️ **{_format_damage_or_na(player.get('damage_taken_frame_window'))}**"
                    f"{proximity}"
                )

            team_title = (
                f"{team} — équipe du joueur"
                if team == str(tracked_team)
                else team
            )
            fields.append(
                (
                    team_title,
                    "\n".join(player_lines) or "Aucun joueur",
                    False,
                )
            )

        survived = "✅" if _safe_bool(tracked.get("survived")) else "❌"
        tracked_prefix = f"{champion_emoji} " if champion_emoji else ""
        fields.append(
            (
                f"{tracked_prefix}{champion} — focus",
                (
                    f"KDA **{_fight_kda(tracked)}** · Survie {survived}\n"
                    f"🎯 **{_format_damage(tracked.get('damage_frame_window'))} infligés** · "
                    f"**{_damage_share(selected, tracked):.1f}%** des dégâts de l'équipe\n"
                    f"{_taken_breakdown(tracked)}\n"
                    f"Ratio infligés/reçus : **{_damage_ratio(tracked)}**"
                ),
                False,
            )
        )

        if not _damage_taken_available(tracked):
            fields.append(
                (
                    "⚠️ Dégâts reçus non backfill",
                    (
                        "Les colonnes de dégâts reçus sont encore NULL pour ce combat. "
                        "Exécute le script de backfill pour obtenir une valeur fiable."
                    ),
                    False,
                )
            )

        pages = self._build_pages(
            title,
            champion,
            match["match_id"],
            numerogame,
            match_id,
            fields,
        )
        await self._send_pages(ctx, pages)

    @resume.autocomplete("riot_id")
    async def autocomplete_resume(self, ctx: interactions.AutocompleteContext):
        choices = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        await ctx.send(choices=choices)

    @combats.autocomplete("riot_id")
    async def autocomplete_combats(self, ctx: interactions.AutocompleteContext):
        choices = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        await ctx.send(choices=choices)

    @detail.autocomplete("riot_id")
    async def autocomplete_detail(self, ctx: interactions.AutocompleteContext):
        choices = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        await ctx.send(choices=choices)
