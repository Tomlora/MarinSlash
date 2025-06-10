import sys
import aiohttp
import pandas as pd
import warnings
import interactions
from interactions import SlashCommandOption, Extension, SlashContext, slash_command
from fonctions.params import saison
from fonctions.channels_discord import verif_module
from fonctions.permissions import isOwner_slash
import traceback
import psycopg2.errors
from fonctions.gestion_bdd import requete_perso_bdd, lire_bdd_perso, get_tag
from fonctions.autocomplete import autocomplete_riotid
from fonctions.match import getId_with_puuid, get_summonerinfo_by_puuid, get_summoner_by_riot_id




warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None  # default='warn'


async def parametrer_objectif(ctx, riot_id, riot_tag, objectif_id, valeur=None, supprimer=False):

        if supprimer:
                requete_perso_bdd("""
                    DELETE FROM objectifs_lol_suivi
                    WHERE id_compte = (select id_compte from tracker where tracker.riot_id = :riot_id and tracker.riot_tagline = :riot_tag)
                    AND match_id IS NULL
                    AND objectif_id = :objectif_id
                """, {'riot_id': riot_id, 'riot_tag' : riot_tag, 'objectif_id': objectif_id})
                await ctx.send("✅ Ton objectif cs/min a été supprimé : tu n'as plus d'objectif actif.")
                return

        if valeur is None:
                await ctx.send("Merci de préciser une valeur ou de cocher l’option supprimer.", ephemeral=True)
                return

            # Supprime l'ancien objectif s'il existe, puis ajoute le nouveau
        requete_perso_bdd("""
                DELETE FROM objectifs_lol_suivi
                WHERE id_compte = (select id_compte from tracker where tracker.riot_id = :riot_id and tracker.riot_tagline = :riot_tag)
                AND match_id IS NULL
                AND objectif_id = :objectif_id
            """, {'riot_id': riot_id, 'riot_tag' : riot_tag, 'objectif_id': objectif_id})

        requete_perso_bdd("""
                INSERT INTO objectifs_lol_suivi (id_compte, objectif_id, valeur_attendue, match_id)
                VALUES ((select id_compte from tracker where tracker.riot_id = :riot_id and tracker.riot_tagline = :riot_tag), :objectif_id, :valeur_attendue, NULL)
            """, {'riot_id': riot_id, 'riot_tag' : riot_tag, 'objectif_id': objectif_id, 'valeur_attendue': valeur})

class LoLObjectifs(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot



    @slash_command(name='lol_objectifs', description='Gère tes objectifs League of Legends')
    async def lol_objectifs(self, ctx: SlashContext):
        pass

    



    @lol_objectifs.subcommand('cs_min',
                           sub_cmd_description='Activation/Désactivation du tracker',
                           options=[
                               SlashCommandOption(name='riot_id',
                                                  description="nom ingame",
                                                  type=interactions.OptionType.STRING,
                                                  required=True,
                                                  autocomplete=True),
                               SlashCommandOption(name='riot_tag',
                                                  description="tag",
                                                  type=interactions.OptionType.STRING,
                                                  required=False),
                                SlashCommandOption(
                                    name="valeur",
                                    description="Valeur cible de CS/min (laisse vide pour supprimer l'objectif)",
                                    type=interactions.OptionType.NUMBER,
                                    required=False
                                ),
                                SlashCommandOption(
                                    name="supprimer",
                                    description="Coche pour supprimer l'objectif cs/min",
                                    type=interactions.OptionType.BOOLEAN,
                                    required=False
                                ),
                                                  ])
    async def objectif_cs_min(self,
                             ctx: SlashContext,
                             riot_id: str,
                             riot_tag: str = None,
                             valeur = None,
                             supprimer: bool = False):
        

        if riot_tag is None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')

        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()
        objectif_id = 1  # CS/min

        await ctx.defer(ephemeral=False)

        # Appelle la logique métier
        await parametrer_objectif(ctx, riot_id, riot_tag, objectif_id, valeur, supprimer)

        # Seulement si on ne supprime pas et qu'il y a une valeur (pour éviter le double message)
        if not supprimer and valeur is not None:
            await ctx.send(f"🎯 Ton objectif de **{valeur} cs/min** est enregistré pour toutes tes parties !")


    @objectif_cs_min.autocomplete("riot_id")
    async def autocomplete_trackerconfig(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)

        await ctx.send(choices=liste_choix)


    @lol_objectifs.subcommand('kp',
        sub_cmd_description='Fixe ou supprime ton objectif % KP',
        options=[
            SlashCommandOption(name='riot_id', description="nom ingame", type=interactions.OptionType.STRING, required=True, autocomplete=True),
            SlashCommandOption(name='riot_tag', description="tag", type=interactions.OptionType.STRING, required=False),
            SlashCommandOption(name="valeur", description="Pourcentage cible de Kill Participation (ex: 60)", type=interactions.OptionType.NUMBER, required=False),
            SlashCommandOption(name="supprimer", description="Coche pour supprimer l'objectif KP", type=interactions.OptionType.BOOLEAN, required=False),
        ])
    async def objectif_kp(self, ctx: SlashContext, riot_id: str, riot_tag: str = None, valeur=None, supprimer: bool = False):
        if riot_tag is None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')

        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()
        objectif_id = 2  # KP

        await ctx.defer(ephemeral=False)
        await parametrer_objectif(ctx, riot_id, riot_tag, objectif_id, valeur, supprimer)
        if not supprimer and valeur is not None:
            await ctx.send(f"🎯 Ton objectif de **{valeur}% KP** est enregistré pour toutes tes parties !")


    @objectif_kp.autocomplete("riot_id")
    async def autocomplete_trackerconfig(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)

        await ctx.send(choices=liste_choix)    



    @lol_objectifs.subcommand('kda',
        sub_cmd_description='Fixe ou supprime ton objectif KDA',
        options=[
            SlashCommandOption(name='riot_id', description="nom ingame", type=interactions.OptionType.STRING, required=True, autocomplete=True),
            SlashCommandOption(name='riot_tag', description="tag", type=interactions.OptionType.STRING, required=False),
            SlashCommandOption(name="valeur", description="Valeur cible de KDA", type=interactions.OptionType.NUMBER, required=False),
            SlashCommandOption(name="supprimer", description="Coche pour supprimer l'objectif KDA", type=interactions.OptionType.BOOLEAN, required=False),
        ])
    async def objectif_kda(self, ctx: SlashContext, riot_id: str, riot_tag: str = None, valeur=None, supprimer: bool = False):
        if riot_tag is None:
            try:
                riot_tag = get_tag(riot_id)
            except ValueError:
                return await ctx.send('Plusieurs comptes avec ce riot_id, merci de préciser le tag')

        riot_id = riot_id.lower().replace(' ', '')
        riot_tag = riot_tag.upper()
        objectif_id = 3  # KDA

        await ctx.defer(ephemeral=False)
        await parametrer_objectif(ctx, riot_id, riot_tag, objectif_id, valeur, supprimer)
        if not supprimer and valeur is not None:
            await ctx.send(f"🎯 Ton objectif de **{valeur} KDA** est enregistré pour toutes tes parties !")



    @objectif_kda.autocomplete("riot_id")
    async def autocomplete_trackerconfig(self, ctx: interactions.AutocompleteContext):

        liste_choix = await autocomplete_riotid(int(ctx.guild.id), ctx.input_text)

        await ctx.send(choices=liste_choix)    


def setup(bot):
    LoLObjectifs(bot)