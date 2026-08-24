import re

import pandas as pd
import interactions
from interactions import Extension, SlashCommandOption, SlashContext, slash_command

from fonctions.autocomplete import autocomplete_riotid
from fonctions.gestion_bdd import get_tag, lire_bdd_perso
from utils.emoji import emote_champ_discord
from utils.params import Version


def _normalize_champion_name(champion: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(champion or "").lower())


_CHAMPION_EMOJI_BY_NORMALIZED_NAME = {
    _normalize_champion_name(name): emoji
    for name, emoji in emote_champ_discord.items()
}


def _champion_emoji(champion: str) -> str:
    """Retourne l'emoji-image Discord déjà utilisé par les autres commandes."""
    return _CHAMPION_EMOJI_BY_NORMALIZED_NAME.get(
        _normalize_champion_name(champion),
        "",
    )


def _champion_icon_url(champion: str) -> str | None:
    """Transforme l'emoji Discord du champion en URL utilisable comme thumbnail."""
    emoji = _champion_emoji(champion)
    match = re.search(r"<a?:[^:]+:(\d+)>", emoji)
    if match is None:
        return None
    return f"https://cdn.discordapp.com/emojis/{match.group(1)}.png?size=128&quality=lossless"


def _format_damage(value) -> str:
    try:
        damage = int(round(float(value or 0)))
    except (TypeError, ValueError):
        damage = 0
    return f"{damage:,}".replace(",", " ")


def _format_timestamp(timestamp_ms) -> str:
    try:
        seconds = max(0, int(float(timestamp_ms)) // 1000)
    except (TypeError, ValueError):
        seconds = 0
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _safe_int(value) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_bool(value) -> bool:
    if isinstance(value, str):
        return value.lower() in {"true", "t", "1", "yes"}
    if pd.isna(value):
        return False
    return bool(value)


def _same_team(team_a, team_b) -> bool:
    if pd.isna(team_a) or pd.isna(team_b):
        return False
    return str(team_a) == str(team_b)


def _team_label(team) -> str:
    team_str = str(team)
    if team_str == "100":
        return "BLUE"
    if team_str == "200":
        return "RED"
    return team_str


def _fight_label(row: pd.Series) -> str:
    for column in ("fight_type_with_proximity", "fight_type", "fight_category"):
        value = row.get(column)
        if value is not None and not pd.isna(value) and str(value).strip():
            return str(value)
    return "combat"


def _tracked_row(fight_df: pd.DataFrame, analyzed_puuid: str) -> pd.Series | None:
    tracked = fight_df[fight_df["puuid"].astype(str) == str(analyzed_puuid)]
    if tracked.empty:
        return None
    return tracked.iloc[0]


def _team_damage(fight_df: pd.DataFrame, team) -> float:
    """Somme exclusivement damage_frame_window pour l'équipe demandée."""
    team_rows = fight_df[fight_df["team"].astype(str) == str(team)]
    return float(
        pd.to_numeric(
            team_rows["damage_frame_window"],
            errors="coerce",
        ).fillna(0).clip(lower=0).sum()
    )


def _damage_share(fight_df: pd.DataFrame, player_row: pd.Series) -> float:
    """Part des dégâts calculée exclusivement à partir de damage_frame_window."""
    team_total = _team_damage(fight_df, player_row.get("team"))
    if team_total <= 0:
        return 0.0

    try:
        player_damage = max(0.0, float(player_row.get("damage_frame_window") or 0))
    except (TypeError, ValueError):
        player_damage = 0.0

    return 100.0 * player_damage / team_total


def _fight_kda(row: pd.Series) -> str:
    return (
        f"{_safe_int(row.get('fight_kills'))}/"
        f"{_safe_int(row.get('fight_deaths'))}/"
        f"{_safe_int(row.get('fight_assists'))}"
    )


def _fight_result(row: pd.Series) -> tuple[str, bool | None]:
    winner = row.get("winner")
    if winner is None or pd.isna(winner):
        return "⚪", None

    won = _same_team(row.get("team"), winner)
    return ("🟢" if won else "🔴"), won


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
            min_value=0,
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
        normalized_riot_id = riot_id.lower().replace(" ", "")

        if riot_tag is None:
            riot_tag = get_tag(normalized_riot_id)

        return normalized_riot_id, riot_tag.upper()

    @staticmethod
    def _load_selected_match(
        riot_id: str,
        riot_tag: str,
        numerogame: int,
    ) -> dict | None:
        """
        Sélectionne une partie déjà enregistrée possédant des données teamfight.
        numerogame=0 correspond à la plus récente.
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
              AND EXISTS (
                    SELECT 1
                    FROM match_teamfight_damage AS tf
                    WHERE tf.match_id = matchs.match_id
                      AND tf.analyzed_puuid = tracker.puuid
              )
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

        if df.empty:
            return None

        return df.iloc[0].to_dict()

    @staticmethod
    def _load_teamfights(match_id, analyzed_puuid: str) -> pd.DataFrame:
        """
        Charge toutes les lignes de la partie.
        Les seules valeurs de dégâts consommées par ce Cog sont damage_frame_window.
        """
        df = lire_bdd_perso(
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
                participation_source,
                start_ms,
                end_ms,
                winner,
                participants_allies,
                participants_enemies,
                fight_type,
                fight_type_with_proximity,
                fight_category,
                is_teamfight,
                is_outnumbered,
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

        return df

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
                "Plusieurs comptes utilisent ce Riot ID, ou le compte est introuvable. "
                "Merci de préciser le tag."
            )

        match = self._load_selected_match(riot_id, riot_tag, numerogame)
        if match is None:
            return None, None, None, (
                "Aucune partie enregistrée avec des données de teamfight "
                "pour ce joueur à ce numéro."
            )

        fights = self._load_teamfights(
            match["match_id"],
            str(match["analyzed_puuid"]),
        )
        if fights.empty:
            return None, None, None, "Aucune donnée de combat trouvée pour cette partie."

        return riot_id, riot_tag, (match, fights), None

    @staticmethod
    def _player_fights(
        fights: pd.DataFrame,
        analyzed_puuid: str,
    ) -> list[tuple[object, pd.DataFrame, pd.Series]]:
        result = []

        for fight_id, fight_df in fights.groupby("fight_id", sort=True):
            tracked = _tracked_row(fight_df, analyzed_puuid)
            if tracked is None:
                continue
            result.append((fight_id, fight_df, tracked))

        return result

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
        embed.set_footer(text=f"Version {Version} by Tomlora · dégâts = damage_frame_window")
        return embed

    @slash_command(
        name="teamfight",
        description="Analyse détaillée des combats d'une partie League of Legends",
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
            riot_id,
            riot_tag,
            numerogame,
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
        title = f"Teamfights — {riot_id.upper()} #{riot_tag} — {champion}"

        embed = self._base_embed(
            title,
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
                if _same_team(tracked.get("team"), first.get("winner")):
                    duels_won += 1

            if (
                _safe_bool(first.get("won_while_outnumbered"))
                and _same_team(tracked.get("team"), first.get("outnumbered_team"))
            ):
                outnumbered_wins += 1

        tf_wins = 0
        tf_losses = 0
        for _, fight_df, tracked in teamfights:
            winner = fight_df.iloc[0].get("winner")
            if winner is None or pd.isna(winner):
                continue
            if _same_team(tracked.get("team"), winner):
                tf_wins += 1
            else:
                tf_losses += 1

        summary_lines = [
            f"{champion_emoji} **{champion}**" if champion_emoji else f"**{champion}**",
            f"⚔️ **{len(teamfights)}** teamfights — **{tf_wins}** gagnés / **{tf_losses}** perdus",
            f"🤺 **{skirmishes}** skirmishes",
            f"🥊 **{duels}** duels — **{duels_won}** gagnés",
            f"🔥 **{outnumbered_wins}** combats gagnés en infériorité",
        ]
        embed.add_field(
            name="Résumé",
            value="\n".join(summary_lines),
            inline=False,
        )

        if teamfights:
            best = max(
                teamfights,
                key=lambda item: float(item[2].get("damage_frame_window") or 0),
            )
            best_id, best_df, best_player = best
            best_first = best_df.iloc[0]
            share = _damage_share(best_df, best_player)
            result_icon, _ = _fight_result(best_player)

            embed.add_field(
                name="Meilleur teamfight en dégâts",
                value=(
                    f"{result_icon} **Fight #{best_id}** · "
                    f"{_format_timestamp(best_first.get('start_ms'))} → "
                    f"{_format_timestamp(best_first.get('end_ms'))}\n"
                    f"**{_fight_label(best_first)}** · KDA **{_fight_kda(best_player)}**\n"
                    f"🎯 **{_format_damage(best_player.get('damage_frame_window'))} dégâts** "
                    f"· **{share:.1f}%** des dégâts de l'équipe"
                ),
                inline=False,
            )

            lost_teamfights = [
                item
                for item in teamfights
                if item[1].iloc[0].get("winner") is not None
                and not pd.isna(item[1].iloc[0].get("winner"))
                and not _same_team(
                    item[2].get("team"),
                    item[1].iloc[0].get("winner"),
                )
            ]
            if lost_teamfights:
                worst = max(
                    lost_teamfights,
                    key=lambda item: float(item[2].get("damage_frame_window") or 0),
                )
                lost_id, lost_df, lost_player = worst
                lost_first = lost_df.iloc[0]
                lost_share = _damage_share(lost_df, lost_player)
                embed.add_field(
                    name="Plus gros teamfight perdu en dégâts",
                    value=(
                        f"🔴 **Fight #{lost_id}** · "
                        f"{_format_timestamp(lost_first.get('start_ms'))} → "
                        f"{_format_timestamp(lost_first.get('end_ms'))}\n"
                        f"**{_fight_label(lost_first)}** · KDA **{_fight_kda(lost_player)}**\n"
                        f"🎯 **{_format_damage(lost_player.get('damage_frame_window'))} dégâts** "
                        f"· **{lost_share:.1f}%** des dégâts de l'équipe"
                    ),
                    inline=False,
                )

        await ctx.send(embeds=embed)

    @resume.autocomplete("riot_id")
    async def autocomplete_resume(self, ctx: interactions.AutocompleteContext):
        choices = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        await ctx.send(choices=choices)

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
            riot_id,
            riot_tag,
            numerogame,
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
            share = _damage_share(fight_df, tracked)
            champ_icon = champion_emoji + " " if champion_emoji else ""

            flags = []
            if _safe_bool(first.get("won_while_outnumbered")) and _same_team(
                tracked.get("team"),
                first.get("outnumbered_team"),
            ):
                flags.append("🔥")
            if _safe_bool(tracked.get("is_proximity_participant")) and not _safe_bool(
                tracked.get("is_core_participant")
            ):
                flags.append("prox.")

            suffix = f" · {' '.join(flags)}" if flags else ""

            lines.append(
                f"{result_icon} **#{fight_id}** "
                f"{_format_timestamp(first.get('start_ms'))} · "
                f"**{_fight_label(first)}** · "
                f"{champ_icon}{_fight_kda(tracked)} · "
                f"**{_format_damage(tracked.get('damage_frame_window'))} dmg** · "
                f"{share:.1f}%{suffix}"
            )

        current_lines = []
        current_length = 0
        chunks = []

        for line in lines:
            if current_lines and current_length + len(line) + 1 > 950:
                chunks.append("\n".join(current_lines))
                current_lines = []
                current_length = 0
            current_lines.append(line)
            current_length += len(line) + 1

        if current_lines:
            chunks.append("\n".join(current_lines))

        for index, chunk in enumerate(chunks):
            embed.add_field(
                name="Chronologie" if index == 0 else "Chronologie (suite)",
                value=chunk,
                inline=False,
            )

        await ctx.send(embeds=embed)

    @combats.autocomplete("riot_id")
    async def autocomplete_combats(self, ctx: interactions.AutocompleteContext):
        choices = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        await ctx.send(choices=choices)

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
            riot_id,
            riot_tag,
            numerogame,
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

        embed = self._base_embed(
            f"Fight #{fight} — {riot_id.upper()} #{riot_tag}",
            champion,
            match["match_id"],
            numerogame,
        )

        result_text = (
            "Victoire" if won is True
            else "Défaite" if won is False
            else "Résultat inconnu"
        )
        embed.description = (
            f"{embed.description}\n"
            f"**{_format_timestamp(first.get('start_ms'))} → "
            f"{_format_timestamp(first.get('end_ms'))}** · "
            f"**{_fight_label(first)}** · {result_icon} **{result_text}**"
        )

        teams = []
        for team in selected["team"].dropna().unique().tolist():
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
            teams.append((team, team_df))

        teams.sort(key=lambda item: str(item[0]))

        winner = first.get("winner")
        for team, team_df in teams:
            team_total = _team_damage(selected, team)
            team_won = winner is not None and not pd.isna(winner) and _same_team(team, winner)
            team_title = f"{'🏆 ' if team_won else ''}{_team_label(team)}"

            player_lines = []
            for _, player in team_df.iterrows():
                champ = str(player.get("champion") or "?")
                champ_icon = _champion_emoji(champ)
                icon_prefix = f"{champ_icon} " if champ_icon else ""
                proximity = (
                    " *(prox.)*"
                    if _safe_bool(player.get("is_proximity_participant"))
                    and not _safe_bool(player.get("is_core_participant"))
                    else ""
                )

                try:
                    player_damage = max(
                        0.0,
                        float(player.get("damage_frame_window") or 0),
                    )
                except (TypeError, ValueError):
                    player_damage = 0.0

                share = 100.0 * player_damage / team_total if team_total > 0 else 0.0

                player_lines.append(
                    f"{icon_prefix}**{champ}** · {_fight_kda(player)} · "
                    f"**{_format_damage(player_damage)} dmg** · {share:.1f}%"
                    f"{proximity}"
                )

            embed.add_field(
                name=team_title,
                value="\n".join(player_lines) or "Aucun joueur",
                inline=False,
            )

        tracked_share = _damage_share(selected, tracked)
        tracked_survived = "✅" if _safe_bool(tracked.get("survived")) else "❌"
        tracked_prefix = f"{champion_emoji} " if champion_emoji else ""

        embed.add_field(
            name=f"{tracked_prefix}{champion} — focus",
            value=(
                f"KDA **{_fight_kda(tracked)}** · "
                f"🎯 **{_format_damage(tracked.get('damage_frame_window'))} dégâts** · "
                f"**{tracked_share:.1f}%** des dégâts de l'équipe · "
                f"Survie {tracked_survived}"
            ),
            inline=False,
        )

        await ctx.send(embeds=embed)

    @detail.autocomplete("riot_id")
    async def autocomplete_detail(self, ctx: interactions.AutocompleteContext):
        choices = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)
        await ctx.send(choices=choices)
