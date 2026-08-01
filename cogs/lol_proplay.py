import asyncio
import logging
from datetime import datetime

import interactions
import pandas as pd
from aiohttp import ClientSession
from dateutil import tz
from interactions import (
    Extension,
    IntervalTrigger,
    SlashCommandChoice,
    SlashCommandOption,
    SlashContext,
    Task,
    listen,
    slash_command,
)

from fonctions.gestion_bdd import lire_bdd_perso, sauvegarde_bdd
from fonctions.leaguepedia_pro import fetch_leaguepedia_players
from fonctions.lolpros import merge_account_sources
from fonctions.lolpros_profiles import fetch_lolpros_accounts_for_players
from fonctions.proplay_backup import create_proplay_backup, restore_proplay_backup
from fonctions.proplay_lolpros_override import (
    LolprosManualRefreshError,
    apply_manual_profile_overrides,
    fetch_exact_lolpros_profile,
    merge_profile_cache_preserving_manual,
    set_manual_lolpros_url,
)
from fonctions.proplay_lolpros_targeted import apply_targeted_lolpros_refresh
from fonctions.proplay_manual import (
    ROLE_VALUES,
    AccountConflictError,
    ManualProplayError,
    PlayerAlreadyExistsError,
    PlayerNotFoundError,
    add_manual_account,
    add_manual_player,
    get_player_names,
)
from fonctions.proplay_sources import (
    DEFAULT_PRO_LEAGUES,
    fetch_trackingthepros_accounts,
    fetch_trackingthepros_players,
    merge_proplayer_sources,
)
from fonctions.word import suggestion_word


LOGGER = logging.getLogger(__name__)
ROLE_CHOICES = [SlashCommandChoice(name=role, value=role) for role in ROLE_VALUES]


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

        batch_duration = state.get("last_batch_duration_seconds")
        if batch_duration is None:
            batch_duration_text = "-"
        else:
            total_seconds = max(int(round(float(batch_duration))), 0)
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours:
                batch_duration_text = f"{hours} h {minutes:02d} min {seconds:02d} s"
            elif minutes:
                batch_duration_text = f"{minutes} min {seconds:02d} s"
            else:
                batch_duration_text = f"{seconds} s"

        last_edit = datetime.now(tz.gettz("Europe/Paris")).strftime("%H:%M:%S")

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
            f"**Retries HTTP 429 :** {retry_events}\n"
            f"**Durée du dernier lot :** {batch_duration_text}\n"
            f"**Dernière mise à jour :** {last_edit}"
        )

    @staticmethod
    def _player_suggestion(requested_player: str) -> str | None:
        try:
            players = get_player_names()
            if not players:
                return None
            return suggestion_word(requested_player, players)
        except Exception:
            LOGGER.exception("Impossible de calculer une suggestion de joueur")
            return None

    def _save_lolpros_profile_cache(
        self,
        resolved_profiles: pd.DataFrame,
        updated_at: datetime,
    ) -> None:
        if resolved_profiles is None or resolved_profiles.empty:
            return

        existing_cache = self._read_optional_table("data_proplayer_lolpros_profiles")
        cache = merge_profile_cache_preserving_manual(
            existing_cache,
            resolved_profiles,
            verified_at=updated_at,
        )
        if cache.empty:
            return

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
                effective_lolpros_profiles = apply_manual_profile_overrides(
                    df_leaguepedia,
                    profile_cache,
                )

                df_lolpros_accounts, resolved_profiles = await fetch_lolpros_accounts_for_players(
                    session,
                    target_players,
                    leaguepedia_profiles=effective_lolpros_profiles,
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
        await ctx.defer(ephemeral=True)

        progress_message = None
        try:
            channel = await self.bot.fetch_channel(ctx.channel_id)
            progress_message = await channel.send(
                "⏳ Force update proplay initialisé — préparation du backup et des sources..."
            )
            await ctx.send("Force update lancé. La progression est affichée dans le salon.")
        except Exception:
            LOGGER.exception("Impossible de créer le message Discord de progression")
            await ctx.send(
                "Force update lancé, mais le message de progression n'a pas pu être créé. "
                "Le traitement continue et reste visible dans les logs."
            )

        async def discord_progress(state: dict[str, object]) -> None:
            if progress_message is None:
                return
            try:
                await progress_message.edit(content=self._format_force_progress(state))
            except Exception:
                LOGGER.exception("Progression Discord non mise à jour")

        message = await self._run_pro_database_update(
            trigger="manuel",
            progress_callback=discord_progress,
        )

        if progress_message is not None:
            try:
                await progress_message.edit(content=f"✅ **{message}**")
            except Exception:
                LOGGER.exception("Message final Discord non mis à jour")

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

    @lol_pro.subcommand(
        "set_lolpros_url",
        sub_cmd_description="Définir l'URL LoLPros protégée d'un joueur et le rafraîchir",
        options=[
            SlashCommandOption(
                name="joueur",
                description="Pseudo du joueur déjà présent dans data_proplayers",
                type=interactions.OptionType.STRING,
                required=True,
            ),
            SlashCommandOption(
                name="url",
                description="Fiche complète, par exemple https://lolpros.gg/player/paduck",
                type=interactions.OptionType.STRING,
                required=True,
            ),
        ],
    )
    async def set_lolpros_url(
        self,
        ctx: SlashContext,
        joueur: str,
        url: str,
    ):
        await ctx.defer(ephemeral=True)

        if self._pro_update_lock.locked():
            await ctx.send(
                "⛔ Modification impossible : une mise à jour proplay ou un rollback est en cours."
            )
            return

        url_result = None
        refresh_result = None
        refresh_error: str | None = None
        no_profile_data = False

        try:
            async with self._pro_update_lock:
                url_result = set_manual_lolpros_url(joueur, url)

                try:
                    async with ClientSession() as session:
                        accounts, profile = await fetch_exact_lolpros_profile(
                            session,
                            url_result.player,
                            url_result.url,
                        )
                except LolprosManualRefreshError as exc:
                    refresh_error = str(exc)
                else:
                    if profile is None:
                        no_profile_data = True
                    else:
                        refresh_result = apply_targeted_lolpros_refresh(
                            url_result.player,
                            accounts,
                            profile,
                            verified_at=datetime.now(tz.gettz("Europe/Paris")),
                        )
        except PlayerNotFoundError:
            suggestion = self._player_suggestion(joueur.strip())
            message = f"❌ Joueur introuvable : `{joueur.strip()}`."
            if suggestion:
                message += f"\nSouhaitais-tu dire **{suggestion}** ?"
            await ctx.send(message)
            return
        except ManualProplayError as exc:
            await ctx.send(f"❌ {exc}")
            return
        except Exception:
            LOGGER.exception(
                "Erreur lors de la définition de l'URL LoLPros pour %s",
                joueur,
            )
            if url_result is None:
                await ctx.send(
                    "❌ Une erreur BDD inattendue est survenue. L'override manuel n'a pas été enregistré."
                )
            else:
                await ctx.send(
                    "⚠️ L'URL manuelle a été enregistrée et protégée, mais le "
                    "rafraîchissement ciblé a échoué. Consulte les logs du bot."
                )
            return

        previous_url = url_result.previous_url or "Aucune"
        change_label = "modifiée" if url_result.changed and url_result.previous_url else "ajoutée"
        if not url_result.changed:
            change_label = "confirmée"

        header = (
            f"✅ **URL LoLPros manuelle {change_label}**\n"
            f"**Joueur :** `{url_result.player}`\n"
            f"**Ancienne URL :** `{previous_url}`\n"
            f"**URL protégée :** `{url_result.url}`\n"
            "**Priorité :** override manuel — les mises à jour automatiques ne peuvent pas la remplacer."
        )

        if refresh_error:
            await ctx.send(
                f"{header}\n\n"
                "⚠️ **Rafraîchissement ciblé non appliqué**\n"
                f"{refresh_error}\n"
                "L'URL reste néanmoins enregistrée avec sa protection manuelle."
            )
            return

        if no_profile_data:
            await ctx.send(
                f"{header}\n\n"
                "⚠️ **Aucune donnée exploitable trouvée sur cette fiche**\n"
                "Aucun compte, rôle, pays ou équipe n'a été modifié."
            )
            return

        team = refresh_result.team or "Non renseignée"
        role = refresh_result.role or "Non renseigné"
        country = refresh_result.country or "Non renseigné"
        await ctx.send(
            f"{header}\n\n"
            "🔄 **Rafraîchissement ciblé terminé**\n"
            f"**Riot IDs trouvés sur la fiche :** {refresh_result.discovered_accounts}\n"
            f"**Nouveaux comptes insérés :** {refresh_result.inserted_accounts}\n"
            f"**Comptes totaux du joueur :** {refresh_result.total_accounts}\n"
            f"**Équipe :** `{team}`\n"
            f"**Rôle :** `{role}`\n"
            f"**Pays :** `{country}`\n"
            "Seul ce joueur a été rafraîchi."
        )

    @lol_pro.subcommand(
        "add_compte",
        sub_cmd_description="Ajouter manuellement un Riot ID à un joueur existant",
        options=[
            SlashCommandOption(
                name="joueur",
                description="Pseudo du joueur pro déjà présent dans la base",
                type=interactions.OptionType.STRING,
                required=True,
            ),
            SlashCommandOption(
                name="riot_id",
                description="Riot ID complet au format Nom#TAG, par exemple Kiki#mates",
                type=interactions.OptionType.STRING,
                required=True,
            ),
            SlashCommandOption(
                name="region",
                description="Serveur du compte : EUW, KR, NA... EUW par défaut",
                type=interactions.OptionType.STRING,
                required=False,
            ),
        ],
    )
    async def add_compte(
        self,
        ctx: SlashContext,
        joueur: str,
        riot_id: str,
        region: str = "EUW",
    ):
        await ctx.defer(ephemeral=True)

        if self._pro_update_lock.locked():
            await ctx.send(
                "⛔ Ajout impossible : une mise à jour proplay ou un rollback est en cours."
            )
            return

        try:
            async with self._pro_update_lock:
                result = add_manual_account(joueur, riot_id, region)
        except PlayerNotFoundError:
            suggestion = self._player_suggestion(joueur.strip())
            message = f"❌ Joueur introuvable : `{joueur.strip()}`."
            if suggestion:
                message += f"\nSouhaitais-tu dire **{suggestion}** ?"
            await ctx.send(message)
            return
        except AccountConflictError as exc:
            owners = ", ".join(f"`{owner}`" for owner in exc.owners)
            await ctx.send(
                "⚠️ **Ajout refusé**\n"
                f"Le Riot ID `{exc.riot_id}` en région `{exc.region}` est déjà "
                f"associé à {owners}."
            )
            return
        except ManualProplayError as exc:
            await ctx.send(f"❌ {exc}")
            return
        except Exception:
            LOGGER.exception(
                "Erreur lors de l'ajout manuel du compte %s pour %s",
                riot_id,
                joueur,
            )
            await ctx.send(
                "❌ Une erreur BDD inattendue est survenue. Aucune modification partielle "
                "n'a été conservée. Consulte les logs du bot."
            )
            return

        if result.created:
            title = "✅ **Compte ajouté**"
            detail = "Le compteur de comptes du joueur a également été recalculé."
        else:
            title = "ℹ️ **Compte déjà présent**"
            detail = "Aucune nouvelle ligne n'a été créée."

        await ctx.send(
            f"{title}\n"
            f"**Joueur :** `{result.player}`\n"
            f"**Riot ID :** `{result.riot_id}`\n"
            f"**Région :** `{result.region}`\n"
            f"**Comptes enregistrés :** {result.account_count}\n"
            f"**Index BDD :** {result.row_index}\n"
            f"{detail}"
        )

    @lol_pro.subcommand(
        "add_joueur",
        sub_cmd_description="Créer manuellement un joueur pro, avec un compte facultatif",
        options=[
            SlashCommandOption(
                name="joueur",
                description="Pseudo exact du joueur pro",
                type=interactions.OptionType.STRING,
                required=True,
            ),
            SlashCommandOption(
                name="role",
                description="Rôle principal du joueur",
                type=interactions.OptionType.STRING,
                required=True,
                choices=ROLE_CHOICES,
            ),
            SlashCommandOption(
                name="equipe",
                description="Équipe actuelle ; laisse vide pour un joueur sans équipe connue",
                type=interactions.OptionType.STRING,
                required=False,
            ),
            SlashCommandOption(
                name="riot_id",
                description="Riot ID complet facultatif au format Nom#TAG",
                type=interactions.OptionType.STRING,
                required=False,
            ),
            SlashCommandOption(
                name="region",
                description="Serveur du Riot ID, par exemple EUW ou KR ; EUW par défaut",
                type=interactions.OptionType.STRING,
                required=False,
            ),
            SlashCommandOption(
                name="pays",
                description="Pays du joueur, facultatif",
                type=interactions.OptionType.STRING,
                required=False,
            ),
        ],
    )
    async def add_joueur(
        self,
        ctx: SlashContext,
        joueur: str,
        role: str,
        equipe: str | None = None,
        riot_id: str | None = None,
        region: str = "EUW",
        pays: str | None = None,
    ):
        await ctx.defer(ephemeral=True)

        if self._pro_update_lock.locked():
            await ctx.send(
                "⛔ Ajout impossible : une mise à jour proplay ou un rollback est en cours."
            )
            return

        try:
            async with self._pro_update_lock:
                result = add_manual_player(
                    joueur,
                    role,
                    team=equipe,
                    riot_id=riot_id,
                    region=region,
                    country=pays,
                )
        except PlayerAlreadyExistsError as exc:
            await ctx.send(
                f"ℹ️ Le joueur `{exc.player}` existe déjà. "
                "Utilise `/lol_pro add_compte` pour lui ajouter un Riot ID."
            )
            return
        except AccountConflictError as exc:
            owners = ", ".join(f"`{owner}`" for owner in exc.owners)
            await ctx.send(
                "⚠️ **Création refusée**\n"
                f"Le Riot ID `{exc.riot_id}` en région `{exc.region}` est déjà "
                f"associé à {owners}."
            )
            return
        except ManualProplayError as exc:
            await ctx.send(f"❌ {exc}")
            return
        except Exception:
            LOGGER.exception("Erreur lors de l'ajout manuel du joueur %s", joueur)
            await ctx.send(
                "❌ Une erreur BDD inattendue est survenue. La transaction a été annulée : "
                "ni le joueur ni son compte n'ont été partiellement ajoutés."
            )
            return

        team_text = result.team or "Non renseignée"
        country_text = result.country or "Non renseigné"
        if result.riot_id:
            account_text = (
                f"`{result.riot_id}` (`{result.region}`), index {result.account_index}"
            )
        else:
            account_text = "Aucun compte ajouté"

        await ctx.send(
            "✅ **Joueur ajouté**\n"
            f"**Joueur :** `{result.player}`\n"
            f"**Rôle :** `{result.role}`\n"
            f"**Équipe :** `{team_text}`\n"
            f"**Pays :** `{country_text}`\n"
            f"**Compte :** {account_text}\n"
            f"**Index joueur :** {result.player_index}"
        )

    @lol_pro.subcommand(
        "search",
        sub_cmd_description="Chercher un joueur",
        options=[
            SlashCommandOption(
                name="joueur",
                description="Joueur",
                type=interactions.OptionType.STRING,
                required=True,
            )
        ],
    )
    async def search_joueur(self, ctx: SlashContext, joueur):
        await ctx.defer(ephemeral=False)
        df_joueur = lire_bdd_perso(
            f"SELECT team_plug, plug, role from public.data_proplayers where plug like '%{joueur}%'",
            index_col=None,
        ).T
        df_compte = lire_bdd_perso(
            f"SELECT compte from public.data_acc_proplayers where region = 'EUW' and joueur like '%{joueur}%'",
            index_col=None,
        ).T.drop_duplicates()

        if df_joueur.empty:
            await ctx.send("Joueur introuvable")
            return

        txt = "Joueurs trouvés : \n"
        for _, data in df_joueur.iterrows():
            txt += f'{data["plug"]} ({data["team_plug"]}) : {data["role"]}  \n'

        txt += "\nComptes trouvés : \n"
        for index, data in df_compte.iterrows():
            if index % 5 == 0:
                txt += "\n"
            txt += f' {data["compte"]} |'

        await ctx.send(txt)


def setup(bot):
    LoLProplay(bot)
