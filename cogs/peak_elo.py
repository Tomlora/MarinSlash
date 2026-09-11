import interactions
from interactions import Extension, SlashContext, SlashCommandOption, slash_command
from interactions.ext.paginators import Paginator

from fonctions.gestion_bdd import lire_bdd_perso
from utils.emoji import emote_rank_discord
from utils.params import saison


HIGH_ELO_TIERS = {"MASTER", "GRANDMASTER", "CHALLENGER"}
PLAYERS_PER_PAGE = 10

TIER_ORDER_SQL = """
CASE UPPER(peak_tier)
    WHEN 'IRON' THEN 1
    WHEN 'BRONZE' THEN 2
    WHEN 'SILVER' THEN 3
    WHEN 'GOLD' THEN 4
    WHEN 'PLATINUM' THEN 5
    WHEN 'EMERALD' THEN 6
    WHEN 'DIAMOND' THEN 7
    WHEN 'MASTER' THEN 8
    WHEN 'GRANDMASTER' THEN 9
    WHEN 'CHALLENGER' THEN 10
    ELSE 0
END
"""

DIVISION_ORDER_SQL = """
CASE
    WHEN UPPER(peak_tier) IN ('MASTER', 'GRANDMASTER', 'CHALLENGER') THEN 0
    ELSE CASE UPPER(peak_rank)
        WHEN 'IV' THEN 1
        WHEN 'III' THEN 2
        WHEN 'II' THEN 3
        WHEN 'I' THEN 4
        ELSE 0
    END
END
"""


class PeakElo(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @slash_command(
        name="lol_peak_elo",
        description="Affiche les meilleurs Elo SoloQ atteints par les comptes suivis",
    )
    async def lol_peak_elo(self, ctx: SlashContext):
        pass

    @lol_peak_elo.subcommand(
        "global",
        sub_cmd_description="Classement des meilleurs Elo historiques atteints",
    )
    async def peak_elo_global(self, ctx: SlashContext):
        await ctx.defer(ephemeral=False)

        if ctx.guild_id is None:
            return await ctx.send(":x: Cette commande doit être utilisée sur un serveur Discord.")

        df = lire_bdd_perso(
            f"""
            SELECT
                riot_id,
                riot_tagline,
                peak_tier,
                peak_rank,
                peak_lp,
                peak_season AS season,
                peak_datetime
            FROM public.v_peak_elo
            WHERE server_id = :server_id
              AND peak_tier IS NOT NULL
            ORDER BY
                {TIER_ORDER_SQL} DESC,
                {DIVISION_ORDER_SQL} DESC,
                peak_lp DESC,
                riot_id ASC
            """,
            params={"server_id": int(ctx.guild_id)},
            index_col=None,
        ).T

        await self._send_leaderboard(
            ctx=ctx,
            df=df,
            title="Peak Elo SoloQ - Historique",
            description="Meilleur rang SoloQ atteint par chaque compte suivi sur l'ensemble des saisons.",
            show_season=True,
        )

    @lol_peak_elo.subcommand(
        "saison",
        sub_cmd_description="Classement des meilleurs Elo atteints sur une saison",
        options=[
            SlashCommandOption(
                name="saison",
                description="Saison LoL (saison actuelle par défaut)",
                type=interactions.OptionType.INTEGER,
                required=False,
            )
        ],
    )
    async def peak_elo_season(
        self,
        ctx: SlashContext,
        saison: int = saison,
    ):
        await ctx.defer(ephemeral=False)

        if ctx.guild_id is None:
            return await ctx.send(":x: Cette commande doit être utilisée sur un serveur Discord.")

        df = lire_bdd_perso(
            f"""
            SELECT
                riot_id,
                riot_tagline,
                peak_tier,
                peak_rank,
                peak_lp,
                season,
                peak_datetime
            FROM public.v_peak_elo_season
            WHERE server_id = :server_id
              AND season = :season
              AND peak_tier IS NOT NULL
            ORDER BY
                {TIER_ORDER_SQL} DESC,
                {DIVISION_ORDER_SQL} DESC,
                peak_lp DESC,
                riot_id ASC
            """,
            params={
                "server_id": int(ctx.guild_id),
                "season": int(saison),
            },
            index_col=None,
        ).T

        await self._send_leaderboard(
            ctx=ctx,
            df=df,
            title=f"Peak Elo SoloQ - Saison {saison}",
            description=f"Meilleur rang SoloQ atteint par chaque compte suivi durant la saison {saison}.",
            show_season=False,
        )

    async def _send_leaderboard(
        self,
        ctx: SlashContext,
        df,
        title: str,
        description: str,
        show_season: bool,
    ) -> None:
        if df.empty:
            return await ctx.send(":x: Aucun peak Elo trouvé pour ce serveur avec ces critères.")

        embeds = []
        total_players = len(df)
        total_pages = (total_players + PLAYERS_PER_PAGE - 1) // PLAYERS_PER_PAGE
        podium = {1: ":first_place:", 2: ":second_place:", 3: ":third_place:"}

        for page_index, start in enumerate(range(0, total_players, PLAYERS_PER_PAGE)):
            page = df.iloc[start:start + PLAYERS_PER_PAGE]
            lines = []

            for offset, (_, row) in enumerate(page.iterrows()):
                position = start + offset + 1
                position_display = podium.get(position, f"`{position}.`")

                tier = str(row["peak_tier"]).upper()
                rank = "" if row["peak_rank"] is None else str(row["peak_rank"]).upper()
                lp = int(row["peak_lp"])
                emote = emote_rank_discord.get(tier, "")

                riot_id = str(row["riot_id"])
                tagline = row["riot_tagline"]
                riot_name = riot_id if tagline is None else f"{riot_id}#{tagline}"

                if tier in HIGH_ELO_TIERS:
                    elo = f"{tier} - {lp} LP"
                else:
                    elo = f"{tier} {rank} - {lp} LP"

                season_suffix = ""
                if show_season and row["season"] is not None:
                    season_suffix = f" | S{int(row['season'])}"

                lines.append(
                    f"{position_display} **{riot_name}**\n"
                    f"   {emote} **{elo}**{season_suffix}"
                )

            embed = interactions.Embed(
                title=title,
                description=description,
                color=interactions.Color.random(),
            )
            embed.add_field(
                name=f"Classement ({total_players} comptes)",
                value="\n".join(lines),
                inline=False,
            )
            embed.set_footer(text=f"Page {page_index + 1}/{total_pages}")
            embeds.append(embed)

        if len(embeds) == 1:
            await ctx.send(embeds=embeds[0])
            return

        paginator = Paginator.create_from_embeds(self.bot, *embeds)
        paginator.show_select_menu = True
        await paginator.send(ctx)
