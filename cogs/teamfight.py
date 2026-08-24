import re

import interactions
import pandas as pd
from interactions import Extension, SlashCommandOption, SlashContext, slash_command

from fonctions.autocomplete import autocomplete_riotid
from fonctions.gestion_bdd import get_tag, lire_bdd_perso
from utils.emoji import emote_champ_discord
from utils.params import Version


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
    return f"https://cdn.discordapp.com/emojis/{match.group(1)}.png?size=128&quality=lossless"


def _safe_bool(value) -> bool:
    if isinstance(value, str):
        return value.lower() in {"true", "t", "1", "yes"}
    if value is None or pd.isna(value):
        return False
    return bool(value)


def _safe_int(value) -> int:
    try:
        if value is None or pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _damage_value(value) -> float:
    """Normalise une valeur provenant exclusivement de damage_frame_window."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if pd.isna(numeric):
        return 0.0
    return max(0.0, numeric)


def _format_damage(value) -> str:
    return f"{int(round(_damage_value(value))):,}".replace(",", " ")


def _format_timestamp(timestamp_ms) -> str:
    try:
        seconds = max(0, int(float(timestamp_ms)) // 1000)
    except (TypeError, ValueError):
        seconds = 0
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _same_team(team_a, team_b) -> bool:
    if team_a is None or team_b is None or pd.isna(team_a) or pd.isna(team_b):
        return False
    return str(team_a) == str(team_b)


def _is_tie(winner) -> bool:
    return str(winner).lower() in {"égalité", "egalite", "draw", "tie"}


def _fight_result(player_row: pd.Series) -> tuple[str, bool | None]:
    winner = player_row.get("winner")
    if winner is None or pd.isna(winner) or _is_tie(winner):
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

    if core is not None and not pd.isna(core) and str(core).strip():
        if (
            proximity is not None
            and not pd.isna(proximity)
            and str(proximity).strip()
            and str(proximity) != str(core)
        ):
            return f"{core} (avec proximité {proximity})"
        return str(core)

    if category is not None and not pd.isna(category) and str(category).strip():
        return str(category)

    return "combat"


def _tracked_row(fight_df: pd.DataFrame, analyzed_puuid: str) -> pd.Series | None:
    tracked = fight_df[fight_df["puuid"].astype(str) == str(analyzed_puuid)]
    return None if tracked.empty else tracked.iloc[0]


def _team_damage(fight_df: pd.DataFrame, team) -> float:
    """Somme d'équipe fondée uniquement sur damage_frame_window."""
    team_rows = fight_df[fight_df["team"].astype(str) == str(team)]
    return float(
        pd.to_numeric(team_rows["damage_frame_window"], errors="coerce")
        .fillna(0)
        .clip(lower=0)
        .sum()
    )


def _damage_share(fight_df: pd.DataFrame, player_row: pd.Series) -> float:
    """Part de dégâts fondée uniquement sur damage_frame_window."""
    team_total = _team_damage(fight_df, player_row.get("team"))
    if team_total <= 0:
        return 0.0
    return 100.0 * _damage_value(player_row.get("damage_frame_window")) / team_total


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
    ]


class Teamfight(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @staticmethod
    def _resolve_account(riot_id: str, riot_tag: str | None) -> tuple[str, str]:
        riot_id = riot_id.lower().replace(" ", "")
        if riot_tag is None:
            riot_tag = get_tag(riot_id)
        return riot_id, riot_tag.upper()

    @staticmethod
    def _load_selected_match(riot_id: str, riot_tag: str, numerogame: int) -> dict | None:
        """
        Garde la même logique de numéro de partie que le reste du bot :
        on choisit d'abord la N-ième partie enregistrée, puis on cherche ses teamfights.
        """
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
        """
        Charge le strict nécessaire. Aucune autre colonne de dégâts que
        damage_frame_window n'est lue par ces commandes.
        """
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
                damage_frame_window
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
    ):
        try:
            riot_id, riot_tag = self._resolve_account(riot_id, riot_tag)
        except (ValueError, KeyError, IndexError):
            return None, None, None, (
                "Compte introuvable ou Riot ID ambigu. Merci de préciser le tag."
            )

        match = self._load_selected_match(riot_id, riot_tag, numerogame)
        if match is None:
            return None, None, None, "Cette partie enregistrée est introuvable."

        fights = self._load_teamfights(
            match["match_id"],
            str(match["analyzed_puuid"]),
        )
        if fights.empty:
            return None, None, None, (
                "Cette partie existe, mais aucune donnée de teamfight n'est enregistrée pour elle."
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
        match_id,
        numerogame: int,
    ) -> interactions.Embed:
        embed = interactions.Embed(
            title=title,
            description=f"Partie #{numerogame} · `{match_id}`",
            color=interactions.Color.random(),
        )

        icon_url = _champion_icon_url(champion)
        if icon_url:
            embed.set_thumbnail(url=icon_url)

        embed.set_footer(
            text=f"Version {Version} by Tomlora · dégâts = damage_frame_window"
        )
        return embed

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
    ):
        await ctx.defer(ephemeral=False)

        riot_id, riot_tag, payload, error = await self._load_context(
            riot_id, riot_tag, numerogame
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
                and _same_team(tracked.get("team"), first.get("outnumbered_team"))
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

        tf_line = f"⚔️ **{len(teamfights)}** teamfights — **{wins}** gagnés / **{losses}** perdus"
        if ties:
            tf_line += f" / **{ties}** égalités"

        embed.add_field(
            name="Résumé",
            value="\n".join(
                [
                    f"{champion_emoji} **{champion}**" if champion_emoji else f"**{champion}**",
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
                name="Meilleur teamfight en dégâts",
                value=(
                    f"{result_icon} **Fight #{best_id}** · "
                    f"{_format_timestamp(best_first.get('start_ms'))} → "
                    f"{_format_timestamp(best_first.get('end_ms'))}\n"
                    f"**{_fight_label(best_first)}** · KDA **{_fight_kda(best_player)}**\n"
                    f"🎯 **{_format_damage(best_player.get('damage_frame_window'))} dégâts** "
                    f"· **{_damage_share(best_df, best_player):.1f}%** des dégâts de l'équipe"
                ),
                inline=False,
            )

            lost_teamfights = [
                item for item in teamfights
                if _fight_result(item[2])[1] is False
            ]
            if lost_teamfights:
                lost_id, lost_df, lost_player = max(
                    lost_teamfights,
                    key=lambda item: _damage_value(item[2].get("damage_frame_window")),
                )
                lost_first = lost_df.iloc[0]
                embed.add_field(
                    name="Plus gros teamfight perdu en dégâts",
                    value=(
                        f"🔴 **Fight #{lost_id}** · "
                        f"{_format_timestamp(lost_first.get('start_ms'))} → "
                        f"{_format_timestamp(lost_first.get('end_ms'))}\n"
                        f"**{_fight_label(lost_first)}** · KDA **{_fight_kda(lost_player)}**\n"
                        f"🎯 **{_format_damage(lost_player.get('damage_frame_window'))} dégâts** "
                        f"· **{_damage_share(lost_df, lost_player):.1f}%** des dégâts de l'équipe"
                    ),
                    inline=False,
                )

        await ctx.send(embeds=embed)

    @resume.autocomplete("riot_id")
    async def autocomplete_resume(self, ctx: interactions.AutocompleteContext):
        await ctx.send(
            choices=await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        )

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
    ):
        await ctx.defer(ephemeral=False)

        riot_id, riot_tag, payload, error = await self._load_context(
            riot_id, riot_tag, numerogame
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
            f"Combats — {riot_id.upper()} #{riot_tag} — {champion}",
            champion,
            match["match_id"],
            numerogame,
        )

        lines = []
        for fight_id, fight_df, tracked in player_fights:
            first = fight_df.iloc[0]
            result_icon, _ = _fight_result(tracked)
            flags = []

            if (
                _safe_bool(first.get("won_while_outnumbered"))
                and _same_team(tracked.get("team"), first.get("outnumbered_team"))
            ):
                flags.append("🔥")
            if (
                _safe_bool(tracked.get("is_proximity_participant"))
                and not _safe_bool(tracked.get("is_core_participant"))
            ):
                flags.append("prox.")

            suffix = f" · {' '.join(flags)}" if flags else ""
            champ_icon = f"{champion_emoji} " if champion_emoji else ""

            lines.append(
                f"{result_icon} **#{fight_id}** "
                f"{_format_timestamp(first.get('start_ms'))} · "
                f"**{_fight_label(first)}** · "
                f"{champ_icon}{_fight_kda(tracked)} · "
                f"**{_format_damage(tracked.get('damage_frame_window'))} dmg** · "
                f"{_damage_share(fight_df, tracked):.1f}%{suffix}"
            )

        chunks = []
        current = []
        current_length = 0
        for line in lines:
            if current and current_length + len(line) + 1 > 950:
                chunks.append("\n".join(current))
                current = []
                current_length = 0
            current.append(line)
            current_length += len(line) + 1
        if current:
            chunks.append("\n".join(current))

        for index, chunk in enumerate(chunks):
            embed.add_field(
                name="Chronologie" if index == 0 else "Chronologie (suite)",
                value=chunk,
                inline=False,
            )

        await ctx.send(embeds=embed)

    @combats.autocomplete("riot_id")
    async def autocomplete_combats(self, ctx: interactions.AutocompleteContext):
        await ctx.send(
            choices=await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        )

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
    ):
        await ctx.defer(ephemeral=False)

        riot_id, riot_tag, payload, error = await self._load_context(
            riot_id, riot_tag, numerogame
        )
        if error:
            return await ctx.send(error)

        match, fights = payload
        analyzed_puuid = str(match["analyzed_puuid"])
        selected = fights[fights["fight_id"].astype(str) == str(fight)]

        if selected.empty:
            available = ", ".join(
                str(value)
                for value in sorted(fights["fight_id"].dropna().unique().tolist())
            )
            return await ctx.send(
                f"Fight #{fight} introuvable. Combats disponibles : {available}"
            )

        tracked = _tracked_row(selected, analyzed_puuid)
        if tracked is None:
            return await ctx.send(
                f"Le joueur demandé ne participe pas au fight #{fight}."
            )

        first = selected.iloc[0]
        champion = str(tracked.get("champion") or "?")
        champion_emoji = _champion_emoji(champion)
        result_icon, won = _fight_result(tracked)
        result_text = (
            "Victoire" if won is True
            else "Défaite" if won is False
            else "Égalité"
        )

        embed = self._base_embed(
            f"Fight #{fight} — {riot_id.upper()} #{riot_tag}",
            champion,
            match["match_id"],
            numerogame,
        )
        embed.description = (
            f"{embed.description}\n"
            f"**{_format_timestamp(first.get('start_ms'))} → "
            f"{_format_timestamp(first.get('end_ms'))}** · "
            f"**{_fight_label(first)}** · {result_icon} **{result_text}**"
        )

        winner = first.get("winner")
        teams = sorted(
            selected["team"].dropna().unique().tolist(),
            key=str,
        )

        for team in teams:
            team_df = selected[selected["team"].astype(str) == str(team)].copy()
            team_df["_damage_sort"] = pd.to_numeric(
                team_df["damage_frame_window"],
                errors="coerce",
            ).fillna(0)
            team_df.sort_values(
                ["is_core_participant", "_damage_sort"],
                ascending=[False, False],
                inplace=True,
            )

            team_total = _team_damage(selected, team)
            team_won = (
                winner is not None
                and not pd.isna(winner)
                and not _is_tie(winner)
                and _same_team(team, winner)
            )

            player_lines = []
            for _, player in team_df.iterrows():
                champ = str(player.get("champion") or "?")
                icon = _champion_emoji(champ)
                proximity = (
                    " *(prox.)*"
                    if (
                        _safe_bool(player.get("is_proximity_participant"))
                        and not _safe_bool(player.get("is_core_participant"))
                    )
                    else ""
                )
                player_damage = _damage_value(player.get("damage_frame_window"))
                share = 100.0 * player_damage / team_total if team_total > 0 else 0.0

                player_lines.append(
                    f"{f'{icon} ' if icon else ''}**{champ}** · "
                    f"{_fight_kda(player)} · "
                    f"**{_format_damage(player_damage)} dmg** · {share:.1f}%"
                    f"{proximity}"
                )

            embed.add_field(
                name=f"{'🏆 ' if team_won else ''}{team}",
                value="\n".join(player_lines) or "Aucun joueur",
                inline=False,
            )

        embed.add_field(
            name=f"{f'{champion_emoji} ' if champion_emoji else ''}{champion} — focus",
            value=(
                f"KDA **{_fight_kda(tracked)}** · "
                f"🎯 **{_format_damage(tracked.get('damage_frame_window'))} dégâts** · "
                f"**{_damage_share(selected, tracked):.1f}%** des dégâts de l'équipe · "
                f"Survie {'✅' if _safe_bool(tracked.get('survived')) else '❌'}"
            ),
            inline=False,
        )

        await ctx.send(embeds=embed)

    @detail.autocomplete("riot_id")
    async def autocomplete_detail(self, ctx: interactions.AutocompleteContext):
        await ctx.send(
            choices=await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        )
