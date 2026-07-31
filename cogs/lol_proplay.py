import asyncio
from datetime import datetime

import interactions
import pandas as pd
from aiohttp import ClientSession
from dateutil import tz
from interactions import Extension, listen, Task, IntervalTrigger, slash_command, SlashContext, SlashCommandOption

from fonctions.gestion_bdd import sauvegarde_bdd, lire_bdd_perso, requete_perso_bdd
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

    @staticmethod
    def _lolpros_roster_frame(resolved_profiles: pd.DataFrame) -> pd.DataFrame:
        """Convertit les metadata LoLPros dans le format attendu par la fusion roster."""
        columns = ["plug", "Rôle", "Pays", "team_plug"]
        if resolved_profiles is None or resolved_profiles.empty:
            return pd.DataFrame(columns=columns)

        frame = resolved_profiles.rename(
            columns={"joueur": "plug", "role": "Rôle"}
        ).copy()
        for column in columns:
            if column not in frame.columns:
                frame[column] = None

        frame = frame[columns]
        metadata_columns = ["Rôle", "Pays", "team_plug"]
        has_metadata = frame[metadata_columns].apply(
            lambda row: any(pd.notna(value) and str(value).strip() for value in row),
            axis=1,
        )
        return frame[has_metadata].reset_index(drop=True)

    @staticmethod
    def _format_force_progress(state: dict[str, object]) -> str:
        total = int(state.get("total_players") or 0)
        processed = int(state.get("processed") or 0)
        success = int(state.get("success") or 0)
        to_retry = int(state.get("to_retry") or 0)
        riot_ids = int(state.get("riot_ids") or 0)
        retry_events = int(state.get("retry_events") or 0)
        batch_number = int(state.get("batch_number") or 0)
        total_batches = int(state.get("total_batches") or 0)
        player = state.get("current_player") or "-"
        event = str(state.get("event") or "progress")
        percent = (processed / total * 100) if total else 0.0

        if event == "start":
            title = "⏳ Force update proplay démarré"
        elif event == "rate_limit":
            cooldown = float(state.get("cooldown_seconds") or 0)
            title = f"⏸️ LoLPros rate-limité — pause {cooldown:.0f}s"
        elif event == "done":
            title = "🔄 Collecte LoLPros terminée, écriture BDD en cours"
        else:
            title = f"🔄 Lot LoLPros {batch_number}/{total_batches} terminé"

        return (
            f"{title}\n"
            f"**Progression :** {processed}/{total} ({percent:.1f} %)\n"
            f"**Joueur courant / dernier :** {player}\n"
            f"**Profils résolus :** {success}\n"
            f"**Sans résultat / à retenter :** {to_retry}\n"
            f"**Riot IDs récupérés :** {riot_ids}\n"
            f"**Retries HTTP 429 :** {retry_events}"
        )

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

    async def _run_pro_database_update(
        self,
        *,
        trigger: str,
        progress_callback=None,
    ) -> str:
        if self._pro_update_lock.locked():
            return "Une mise à jour proplay est déjà en cours."

        async with self._pro_update_lock:
            timezone = tz.gettz("Europe/Paris")
            updated_at = datetime.now(timezone)
            print(f"Update Database Proplayers ({trigger})...")

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
                df_leaguepedia = await fetch_leaguepedia_players(
                    session,
                    DEFAULT_PRO_LEAGUES,
                )

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
                    progress_callback=progress_callback,
                )
                self._save_lolpros_profile_cache(resolved_profiles, updated_at)

                df_lolpros_roster = self._lolpros_roster_frame(resolved_profiles)
                if not df_lolpros_roster.empty:
                    df_pro = merge_proplayer_sources(
                        df_pro,
                        pd.DataFrame(),
                        df_lolpros_roster,
                        updated_at=updated_at,
                    )
                    if not df_leaguepedia.empty:
                        df_pro = merge_proplayer_sources(
                            df_pro,
                            pd.DataFrame(),
                            df_leaguepedia,
                            updated_at=updated_at,
                        )

                    sauvegarde_bdd(df_pro, "data_proplayers")
                    lolpros_teams = df_lolpros_roster["team_plug"].notna().sum()
                    print(
                        f"Roster LoLPros appliqué : {len(df_lolpros_roster)} profils, "
                        f"{lolpros_teams} équipes renseignées."
                    )

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
                        f"data_acc_proplayers mise à jour : {len(df_accounts)} comptes "
                        f"({len(df_lolpros_accounts)} LoLPros, {len(df_ttp_accounts)} TrackingThePros)."
                    )
                else:
                    print(
                        "LoLPros et TrackingThePros comptes indisponibles : "
                        "data_acc_proplayers conservée."
                    )

            message = (
                f"Update proplay terminée : {len(df_pro)} joueurs, "
                f"{len(df_lolpros_accounts)} comptes LoLPros, "
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
        # Le token d'une interaction Discord expire bien avant les ~2 h du refresh.
        # On acquitte donc immédiatement la slash-command, puis on utilise un message
        # normal du bot dont l'édition ne dépend pas du token de l'interaction.
        await ctx.defer(ephemeral=True)

        progress_message = None
        try:
            channel = await self.bot.fetch_channel(ctx.channel_id)
            progress_message = await channel.send(
                "⏳ Force update proplay initialisé — préparation du backup et des sources..."
            )
            await ctx.send("Force update lancé. La progression est affichée dans le salon.")
        except Exception as exc:
            print(f"Impossible de créer le message Discord de progression : {exc}")
            await ctx.send(
                "Force update lancé, mais le message de progression n'a pas pu être créé. "
                "Le traitement continue et reste visible dans les logs."
            )

        async def discord_progress(state: dict[str, object]) -> None:
            if progress_message is None:
                return
            try:
                await progress_message.edit(content=self._format_force_progress(state))
            except Exception as exc:
                # Une panne d'édition Discord ne doit jamais interrompre la collecte.
                print(f"Progression Discord non mise à jour : {exc}")

        message = await self._run_pro_database_update(
            trigger="manuel",
            progress_callback=discord_progress,
        )

        if progress_message is not None:
            try:
                await progress_message.edit(content=f"✅ **{message}**")
            except Exception as exc:
                print(f"Message final Discord non mis à jour : {exc}")

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
    #
    #     nb_row = requete_perso_bdd(f'''UPDATE public.data_proplayers SET team_plug = '{equipe}' where plug = '{joueur}' ''', get_row_affected=True)
    #
    #     if nb_row > 0:
    #         await ctx.send(f'Database modifiée. {joueur} rejoint {equipe}')
    #     else:
    #         liste_joueur = lire_bdd_perso( '''SELECT plug from public.data_proplayers ''', index_col=None ).T['plug'].to_list()
    #         suggestion = suggestion_word(joueur, liste_joueur)
    #         await ctx.send(f'Joueur introuvable. Souhaitais-tu dire : **{suggestion}**')

    @lol_pro.subcommand("add_compte",
                           sub_cmd_description="Ajouter un compte d'un joueur",
                           options=[
                               SlashCommandOption(name="compte",
                                                  description="Compte du joueur sans tag",
                                                  type=interactions.OptionType.STRING,
                                                  required=True),
                                SlashCommandOption(name="joueur",
                                                  description="Nouvel equipe",
                                                  type=interactions.OptionType.STRING,
                                                  required=True)])
    async def add_compte(self,
                     ctx: SlashContext,
                     compte,
                     joueur):

        await ctx.defer(ephemeral=False)

        df = lire_bdd_perso( '''SELECT plug from public.data_proplayers ''', index_col=None ).T
        df_index = lire_bdd_perso( '''SELECT index from public.data_acc_proplayers ''', index_col=None ).T
        index = df_index['index'].max()
        liste_joueur = df['plug'].to_list()

        if joueur in liste_joueur:
            requete_perso_bdd('''INSERT INTO public.data_acc_proplayers(
                                index, joueur, compte, region)
                                VALUES (:index, :joueur, :compte, 'EUW') ''',
                                dict_params={'index' : index + 1,
                                             'joueur' : joueur,
                                             'compte' : compte})

            await ctx.send('Ajouté')

        else:
            suggestion = suggestion_word(joueur, liste_joueur)
            await ctx.send(f'Joueur introuvable. Souhaitais-tu dire : **{suggestion}**')

    @lol_pro.subcommand("add_joueur",
                           sub_cmd_description="Ajouter un nouveau joueur",
                           options=[
                               SlashCommandOption(name="joueur",
                                                  description="Joueur",
                                                  type=interactions.OptionType.STRING,
                                                  required=True),
                                SlashCommandOption(name="team",
                                                  description="Son equipe",
                                                  type=interactions.OptionType.STRING,
                                                  required=True),
                                SlashCommandOption(name="compte",
                                                  description="Son compte",
                                                  type=interactions.OptionType.STRING,
                                                  required=True),
                                SlashCommandOption(name="role",
                                                  description="Son role",
                                                  type=interactions.OptionType.STRING,
                                                  required=True)])
    async def add_joueur(self,
                     ctx: SlashContext,
                     joueur,
                     team,
                     compte,
                     role):

        await ctx.defer(ephemeral=False)
        df = lire_bdd_perso( '''SELECT index, plug from public.data_proplayers ''', index_col=None ).T
        index = df['index'].max()
        liste_joueur = df['plug'].to_list()

        if joueur in liste_joueur:
            await ctx.send('Joueur déjà présent')

        else:
            requete_perso_bdd('''INSERT INTO public.data_proplayers(
                                index, current, home, role, accounts, team_plug, plug, "rankHigh", "rankHighNum", "rankHighLP", "rankHighLPNum")
                                VALUES (:index, 'None', 'None', :role, 1, :team, :joueur, 'Challenger', 999999, 999999, 999999); ''',
                                dict_params={'index' : index + 1,
                                             'role' : role,
                                             'joueur' : joueur,
                                             'team' : team})

            requete_perso_bdd('''INSERT INTO public.data_acc_proplayers(
                                index, joueur, compte, region)
                                VALUES (:index, :joueur, :compte, 'EUW') ''',
                                dict_params={'index' : index + 1,
                                             'joueur' : joueur,
                                             'compte' : compte})

            await ctx.send('Ajouté')

    @lol_pro.subcommand("search",
                           sub_cmd_description="Chercher un joueur",
                           options=[
                               SlashCommandOption(name="joueur",
                                                  description="Joueur",
                                                  type=interactions.OptionType.STRING,
                                                  required=True)])
    async def search_joueur(self,
                     ctx: SlashContext,
                     joueur):

        await ctx.defer(ephemeral=False)
        df_joueur = lire_bdd_perso( f'''SELECT team_plug, plug, role from public.data_proplayers where plug like '%{joueur}%' ''', index_col=None ).T
        df_compte = lire_bdd_perso( f'''SELECT compte from public.data_acc_proplayers where region = 'EUW' and joueur like '%{joueur}%' ''', index_col=None ).T.drop_duplicates()

        if df_joueur.empty:
            await ctx.send('Joueur introuvable')

        else:
            txt = 'Joueurs trouvés : \n'

            for index, data in df_joueur.iterrows():
                txt += f'{data["plug"]} ({data["team_plug"]}) : {data["role"]}  \n'

            txt += '\nComptes trouvés : \n'

            for index, data in df_compte.iterrows():
                if index % 5 == 0:
                    txt += '\n'
                txt += f' {data["compte"]} |'

            await ctx.send(txt)


def setup(bot):
    LoLProplay(bot)
