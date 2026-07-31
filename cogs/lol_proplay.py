import asyncio
from datetime import datetime

import interactions
import pandas as pd
from aiohttp import ClientSession
from dateutil import tz
from interactions import Extension, IntervalTrigger, SlashContext, Task, listen, slash_command

from fonctions.gestion_bdd import lire_bdd_perso, requete_perso_bdd, sauvegarde_bdd
from fonctions.leaguepedia_pro import fetch_leaguepedia_players
from fonctions.lolpros import merge_account_sources
from fonctions.lolpros_profiles import fetch_lolpros_accounts_for_players
from fonctions.proplay_backup import create_proplay_backup, restore_proplay_backup
from fonctions.proplay_sources import (
    DEFAULT_PRO_LEAGUES,
    fetch_trackingthepros_accounts,
    fetch_trackingthepros_players,
    merge_proplayer_sources,
)
from fonctions.word import suggestion_word


class LoLProplay(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot
        self._pro_update_lock = asyncio.Lock()

    @listen()
    async def on_startup(self):
        self.update_pro_database.start()

    @Task.create(IntervalTrigger(hours=12))
    async def update_pro_database(self):
        if datetime.now().weekday() != 0:  # Que le lundi
            return
        await self._run_pro_database_update(trigger="hebdo")

    @staticmethod
    def _read_optional_table(table_name: str) -> pd.DataFrame:
        try:
            return lire_bdd_perso(
                f'SELECT * FROM public."{table_name}"',
                index_col=None,
            ).T
        except Exception:
            return pd.DataFrame()

    @staticmethod
    def _player_list(*frames: pd.DataFrame) -> list[str]:
        players: list[str] = []
        for frame in frames:
            if frame is None or frame.empty:
                continue
            if "plug" in frame.columns:
                values = frame["plug"].dropna().astype(str).tolist()
            elif frame.index.name == "plug":
                values = frame.index.dropna().astype(str).tolist()
            else:
                continue
            for player in values:
                player = player.strip()
                if player and player not in players:
                    players.append(player)
        return players

    def _save_lolpros_profile_cache(
        self,
        resolved_profiles: pd.DataFrame,
        updated_at: datetime,
    ) -> None:
        if resolved_profiles is None or resolved_profiles.empty:
            return

        cache = self._read_optional_table("data_proplayer_lolpros_profiles")
        new_profiles = resolved_profiles.copy()
        new_profiles["last_verified"] = updated_at

        if not cache.empty and "joueur" in cache.columns:
            cache = cache[~cache["joueur"].isin(new_profiles["joueur"])]
            cache = pd.concat([cache, new_profiles], ignore_index=True)
        else:
            cache = new_profiles

        cache = cache.drop_duplicates(subset="joueur", keep="last")
        sauvegarde_bdd(
            cache.drop(columns="index", errors="ignore"),
            "data_proplayer_lolpros_profiles",
            index=False,
        )

    async def _run_pro_database_update(self, *, trigger: str) -> str:
        if self._pro_update_lock.locked():
            return "Une mise à jour proplay est déjà en cours."

        async with self._pro_update_lock:
            timezone = tz.gettz("Europe/Paris")
            updated_at = datetime.now(timezone)
            print(f"Update Database Proplayers ({trigger})...")

            # Snapshot persistant avant toute écriture. Un /lol_pro rollback_update
            # peut restaurer ces deux tables si le run produit un résultat anormal.
            try:
                backup_at = create_proplay_backup()
                print(f"Backup proplay créé : {backup_at}")
            except Exception as exc:
                message = f"Update annulée : création du backup impossible ({exc})."
                print(message)
                return message

            df_pro_origin = lire_bdd_perso(
                "SELECT * from data_proplayers",
                index_col="plug",
            ).T

            async with ClientSession() as session:
                # Leaguepedia reste utile pour découvrir les joueurs/équipes et fournit
                # souvent l'URL LoLPros, mais n'est plus requis pour rafraîchir les comptes.
                df_leaguepedia = await fetch_leaguepedia_players(
                    session,
                    DEFAULT_PRO_LEAGUES,
                )

                # TrackingThePros est une source additive uniquement.
                df_tracking = await fetch_trackingthepros_players(session)

                df_pro = merge_proplayer_sources(
                    df_pro_origin,
                    df_tracking,
                    df_leaguepedia,
                    updated_at=updated_at,
                )

                if df_pro.empty:
                    message = "Update annulée : aucune donnée pro existante ou récupérée."
                    print(message)
                    return message

                # Même si Leaguepedia ET TTP sont KO, la BDD existante permet de
                # continuer la mise à jour des comptes via LoLPros.
                if not df_leaguepedia.empty or not df_tracking.empty:
                    sauvegarde_bdd(df_pro, "data_proplayers")
                    print(
                        f"data_proplayers mise à jour : {len(df_pro)} joueurs "
                        f"({len(df_leaguepedia)} Leaguepedia, {len(df_tracking)} TrackingThePros)."
                    )
                else:
                    print(
                        "Leaguepedia et TrackingThePros indisponibles : roster conservé, "
                        "rafraîchissement LoLPros poursuivi depuis la BDD."
                    )

                target_players = self._player_list(
                    df_pro_origin,
                    df_pro,
                    df_leaguepedia,
                    df_tracking,
                )
                profile_cache = self._read_optional_table("data_proplayer_lolpros_profiles")

                df_lolpros_accounts, resolved_profiles = await fetch_lolpros_accounts_for_players(
                    session,
                    target_players,
                    leaguepedia_profiles=df_leaguepedia,
                    cached_profiles=profile_cache,
                )
                self._save_lolpros_profile_cache(resolved_profiles, updated_at)

                if not df_tracking.empty:
                    df_ttp_accounts = await fetch_trackingthepros_accounts(
                        session,
                        df_tracking["plug"].tolist(),
                    )
                else:
                    df_ttp_accounts = pd.DataFrame(columns=["joueur", "compte", "region"])

                df_accounts = merge_account_sources(
                    df_lolpros_accounts,
                    df_ttp_accounts,
                )

                if not df_accounts.empty:
                    df_accounts_origin = lire_bdd_perso(
                        "SELECT * from data_acc_proplayers",
                        index_col=["joueur", "compte"],
                    ).T

                    df_accounts.set_index(["joueur", "compte"], inplace=True)
                    df_accounts_origin = pd.concat([
                        df_accounts_origin[~df_accounts_origin.index.isin(df_accounts.index)],
                        df_accounts,
                    ])

                    df_accounts_origin.reset_index(inplace=True)
                    df_accounts_origin.drop_duplicates(
                        subset=["joueur", "compte", "region"],
                        inplace=True,
                    )

                    sauvegarde_bdd(
                        df_accounts_origin.drop(columns="index", errors="ignore"),
                        "data_acc_proplayers",
                    )
                    print(
                        f"data_acc_proplayers mise à jour : {len(df_accounts)} Riot IDs "
                        f"({len(df_lolpros_accounts)} LoLPros, {len(df_ttp_accounts)} TrackingThePros)."
                    )
                else:
                    print(
                        "LoLPros et TrackingThePros indisponibles : "
                        "data_acc_proplayers conservée."
                    )

            message = (
                f"Update proplay terminée : {len(df_pro)} joueurs, "
                f"{len(df_lolpros_accounts)} Riot IDs LoLPros, "
                f"{len(df_ttp_accounts)} comptes TTP."
            )
            print(message)
            return message

    @slash_command(name="lol_pro", description="Pro League of Legends")
    async def lol_pro(self, ctx: SlashContext):
        pass

    @lol_pro.subcommand(
        "force_update",
        sub_cmd_description="Forcer immédiatement la mise à jour joueurs + comptes SoloQ",
    )
    async def force_update(self, ctx: SlashContext):
        await ctx.defer(ephemeral=True)
        message = await self._run_pro_database_update(trigger="manuel")
        await ctx.send(message)

    @lol_pro.subcommand(
        "rollback_update",
        sub_cmd_description="Restaurer le snapshot créé avant la dernière mise à jour proplay",
    )
    async def rollback_update(self, ctx: SlashContext):
        await ctx.defer(ephemeral=True)

        if self._pro_update_lock.locked():
            await ctx.send("Impossible de rollback pendant une mise à jour en cours.")
            return

        async with self._pro_update_lock:
            try:
                backup_at = restore_proplay_backup()
            except Exception as exc:
                await ctx.send(f"Rollback impossible : {exc}")
                return

        if backup_at is None:
            await ctx.send("Rollback effectué depuis le dernier snapshot disponible.")
        else:
            await ctx.send(f"Rollback effectué vers le snapshot du {backup_at}.")

    # @lol_pro.subcommand("update_joueur",
    #                        sub_cmd_description="Mettre à jour son equipe",
    #                        options=[
    #                            SlashCommandOption(name="joueur",
    #                                               description="Nom du joueur",
    #                                               type=interactions.OptionType.STRING,
    #                                               required=True),
    #                             SlashCommandOption(name="equipe",
    #                                               description="Nouvel equipe",
    #                                               type=interactions.OptionType.STRING,
    #                                               required=True)])
    # async def update_joueur(self,
    #                  ctx: SlashContext,
    #                  joueur,
    #                  equipe):
    #
    #     await ctx.defer(ephemeral=False)
    #     nb_row = requete_perso_bdd(f'''UPDATE public.data_proplayers SET team_plug = '{equipe}' where plug = '{joueur}' ''', get_row_affected=True)
    #     if nb_row > 0:
    #         await ctx.send(f'Database modifiée. {joueur} rejoint {equipe}')
    #     else:
    #         liste_joueur = lire_bdd_perso( '''SELECT plug from public.data_proplayers ''', index_col=None ).T['plug'].to_list()
    #         suggestion = suggestion_word(joueur, liste_joueur)
    #         await ctx.send(f'Joueur introuvable. Souhaitais-tu dire : **{suggestion}**')

    @lol_pro.subcommand("add_compte", sub_cmd_description="Ajouter un compte d'un joueur")
    async def add_compte(self, ctx: SlashContext, compte: str, joueur: str):
        await ctx.defer(ephemeral=False)

        df = lire_bdd_perso('''SELECT plug from public.data_proplayers ''', index_col=None).T
        df_index = lire_bdd_perso('''SELECT index from public.data_acc_proplayers ''', index_col=None).T
        index = df_index['index'].max()
        liste_joueur = df['plug'].to_list()

        if joueur in liste_joueur:
            requete_perso_bdd(
                '''INSERT INTO public.data_acc_proplayers(
                    index, joueur, compte, region)
                    VALUES (:index, :joueur, :compte, 'EUW') ''',
                dict_params={'index': index + 1, 'joueur': joueur, 'compte': compte},
            )
            await ctx.send('Ajouté')
        else:
            suggestion = suggestion_word(joueur, liste_joueur)
            await ctx.send(f'Joueur introuvable. Souhaitais-tu dire : **{suggestion}**')

    @lol_pro.subcommand("add_joueur", sub_cmd_description="Ajouter un nouveau joueur")
    async def add_joueur(self, ctx: SlashContext, joueur: str, team: str, compte: str, role: str):
        await ctx.defer(ephemeral=False)
        df = lire_bdd_perso('''SELECT index, plug from public.data_proplayers ''', index_col=None).T
        index = df['index'].max()
        liste_joueur = df['plug'].to_list()

        if joueur in liste_joueur:
            await ctx.send('Joueur déjà présent')
        else:
            requete_perso_bdd(
                '''INSERT INTO public.data_proplayers(
                    index, current, home, role, accounts, team_plug, plug, "rankHigh", "rankHighNum", "rankHighLP", "rankHighLPNum")
                    VALUES (:index, 'None', 'None', :role, 1, :team, :joueur, 'Challenger', 999999, 999999, 999999); ''',
                dict_params={'index': index + 1, 'role': role, 'joueur': joueur, 'team': team},
            )
            requete_perso_bdd(
                '''INSERT INTO public.data_acc_proplayers(
                    index, joueur, compte, region)
                    VALUES (:index, :joueur, :compte, 'EUW') ''',
                dict_params={'index': index + 1, 'joueur': joueur, 'compte': compte},
            )
            await ctx.send('Ajouté')

    @lol_pro.subcommand("search", sub_cmd_description="Chercher un joueur")
    async def search_joueur(self, ctx: SlashContext, joueur: str):
        await ctx.defer(ephemeral=False)
        df_joueur = lire_bdd_perso(
            f'''SELECT team_plug, plug, role from public.data_proplayers where plug like '%{joueur}%' ''',
            index_col=None,
        ).T
        df_compte = lire_bdd_perso(
            f'''SELECT compte from public.data_acc_proplayers where region = 'EUW' and joueur like '%{joueur}%' ''',
            index_col=None,
        ).T.drop_duplicates()

        if df_joueur.empty:
            await ctx.send('Joueur introuvable')
            return

        txt = 'Joueurs trouvés : \n'
        for _, data in df_joueur.iterrows():
            txt += f'{data["plug"]} ({data["team_plug"]}) : {data["role"]}  \n'

        txt += '\nComptes trouvés : \n'
        for index, data in df_compte.iterrows():
            if index % 5 == 0:
                txt += '\n'
            txt += f' {data["compte"]} |'

        await ctx.send(txt)


def setup(bot):
    LoLProplay(bot)
