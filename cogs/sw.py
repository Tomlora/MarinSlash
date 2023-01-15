import interactions
from interactions import Choice, Option, Extension, CommandContext
import aiohttp
from datetime import datetime
from fonctions.profil_sw import Rune, Artefact, comparaison
import pandas as pd
import dataframe_image as dfi
import os
import io
import json
from fonctions.channels_discord import verif_module
from fonctions.permissions import *

from fonctions.gestion_bdd import (sauvegarde_bdd_sw,
                                   update_info_compte,
                                   get_user,
                                   requete_perso_bdd,
                                   get_data_bdd)


def date_du_jour():
    currentMonth = str(datetime.now().month)
    currentYear = str(datetime.now().year)
    currentDay = str(datetime.now().day)
    return f'{currentDay}/{currentMonth}/{currentYear}'


def get_guildeid_by_name(guilde):

    stats = get_data_bdd('''SELECT * from sw_guilde where guilde = :guilde''',
                 dict_params={'guilde': guilde})

    # on cherche l'id
    stats = stats.mappings().all()[0]

    guilde_id = stats['guilde_id']

    return guilde_id


# Params
category_selected = ['Violent', 'Will', 'Destroy', 'Despair']
category_value = ", ".join(category_selected)

coef_set = {'Violent': 3,
            'Will': 3,
            'Destroy': 2,
            'Despair': 2}

category_selected_spd = ['Violent', 'Will', 'Destroy', 'Despair', 'Swift']
category_value_spd = ", ".join(category_selected)

coef_set_spd = {'Violent': 3,
                'Will': 3,
                'Destroy': 2,
                'Despair': 2,
                'Swift': 3}


class SW(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @interactions.extension_command(name="analyse_sw",
                                    description="Summoners Wars",
                                    options=[
                                        Option(
                                            name='scoring',
                                            description='Quel type de scoring ?',
                                            type=interactions.OptionType.STRING,
                                            required=False,
                                            choices=[
                                                Choice(name='general',
                                                       value='general'),
                                                Choice(name='artefact',
                                                       value='artefact'),
                                                Choice(name='speed',
                                                       value='speed')
                                            ]
                                        ),
                                        Option(
                                            name="id_msg",
                                            description="Quel mode de jeu ?",
                                            type=interactions.OptionType.STRING,  # int pas assez grand pour discord
                                            required=False),
                                        Option(
                                            name='fichier_json',
                                            description='Fichier json',
                                            type=interactions.OptionType.ATTACHMENT,
                                            required=False
                                        )])
    async def analyse_sw(self,
                         ctx: CommandContext,
                         scoring: str = 'general',
                         id_msg: str = None,
                         fichier_json: interactions.Attachment = None):

        if verif_module('summoners_war', int(ctx.guild.id)):

            if id_msg != None:
                session = aiohttp.ClientSession()

                id_msg = int(id_msg)
                await ctx.defer(ephemeral=False)

                message = await interactions.get(self.bot, interactions.Message, object_id=id_msg, parent_id=ctx.channel_id)

                file: interactions.Attachment = message.attachments[0]

                async with session.get(file.url) as sw_json:
                    data_json = await sw_json.json()

                if not file.filename.endswith('.json'):
                    await session.close()
                    return await ctx.send("Ce n'est pas un fichier json")

            if fichier_json != None:
                file = await fichier_json.download()
                data_json = io.TextIOWrapper(file, encoding='utf-8')

                data_json = json.load(data_json)

            # info du compte

            pseudo = data_json['wizard_info']['wizard_name']
            guildeid = data_json['guild']['guild_info']['guild_id']
            guilde = data_json['guild']['guild_info']['name']
            compteid = data_json['wizard_info']['wizard_id']

            data_rune = Rune(data_json)
            await data_rune.prepare_data()

            data_arte = Artefact(data_json)
            await data_arte.prepare_data()

            # --------------------- calcul score rune

            tcd_value, score = await data_rune.scoring_rune(category_selected, coef_set)

            # -------------------------- calcul score spd rune

            tcd_spd, score_spd = await data_rune.scoring_spd(category_selected_spd, coef_set_spd)

            # calcul score arte

            tcd_arte, score_arte = await data_arte.scoring_arte()

            # -------------------------- on enregistre
            try:
                id_joueur, visibility, guilde_id = await get_user(compteid, type='id')
            except IndexError:
                try:
                    id_joueur, visibility, guilde_id = await get_user(pseudo, id_compte=compteid)
                except IndexError:  # le joueur n'existe pas ou est dans l'ancien système
                    requete_perso_bdd('''INSERT INTO sw_user(joueur, visibility, guilde_id, joueur_id) VALUES (:joueur, 0, :guilde_id, :joueur_id);
                                    INSERT INTO sw_guilde(guilde, guilde_id) VALUES (:guilde, :guilde_id)
                                    ON CONFLICT (guilde_id)
                                    DO NOTHING;''',
                                      {'joueur': pseudo,
                                       'guilde': guilde,
                                       'guilde_id': guildeid,
                                       'joueur_id': compteid})

                    id_joueur, visibility, guilde_id = await get_user(pseudo)

            # Enregistrement SQL

            tcd_value['id'] = id_joueur
            tcd_value['date'] = date_du_jour()

            sauvegarde_bdd_sw(tcd_value, 'sw', 'append')

            df_scoring = pd.DataFrame({'id': [id_joueur], 'score_general': [score],
                                       'date': [date_du_jour()], 'score_spd' : [score_spd], 'score_arte' : [score_arte]})
            df_scoring.set_index('id', inplace=True)

            sauvegarde_bdd_sw(df_scoring, 'sw_score', 'append')

            # MAJ guilde

            # on update le compte
            update_info_compte(pseudo, guildeid, compteid)

            # On cherche les infos d'Endless...

            size_general, avg_score_general, max_general, size_guilde, avg_score_guilde, max_guilde, df_max, df_guilde_max = await comparaison(guilde_id)

            result = {
                'general': [tcd_value[[100, 110, 120]], score],
                'artefact': [tcd_arte, score_arte],
                'speed': [tcd_spd, score_spd]
            }
            dfi.export(result[scoring][0], 'image.png', max_cols=-
                       1, max_rows=-1, table_conversion="matplotlib")

            embed = interactions.Embed()
            file = interactions.File(f'image.png')
            # On prépare l'embed

            if scoring == 'general':
                embed.add_field(name=f'Scoring {scoring}', value=f'Joueur : **{pseudo}**\n' +
                                f'Score : **{result[scoring][1]}** (__Moyenne {guilde}__ : **{avg_score_guilde}** )\n' +
                                f'Guilde : **{guilde}**')
            else:
                embed.add_field(name=f'Scoring {scoring}', value=f'Joueur : **{pseudo}**\n' +
                                f'Score : **{result[scoring][1]}**\n' +
                                f'Guilde : **{guilde}**')

            embed.set_image(url=f'attachment://image.png')

            await ctx.send(embeds=embed, files=file)

            os.remove('image.png')

            if id_msg != None:
                await session.close()

        else:
            await ctx.send('Désactivé sur ce serveur')

    @interactions.extension_command(name="sw_gvo",
                                    description="prepare la gvo",
                                    options=[
                                        Option(
                                            name='guilde_rouge',
                                            description="nom de la guilde rouge (pas d'espace !)",
                                            type=interactions.OptionType.STRING,
                                            required=True),
                                        Option(
                                            name='guilde_jaune',
                                            description="nom de la guilde jaune (pas d'espace !)",
                                            type=interactions.OptionType.STRING,
                                            required=True)
                                        ])
    async def test_channel(self,
                           ctx: CommandContext,
                           guilde_rouge: str,
                           guilde_jaune: str):
        if isOwner_or_mod_slash(ctx):
            permission = [
                interactions.Overwrite(
                    id=int(ctx.author.id),
                    type=1,  # user
                    allow=interactions.Permissions.VIEW_CHANNEL | interactions.Permissions.SEND_MESSAGES | interactions.Permissions.ATTACH_FILES),
                interactions.Overwrite(
                    # le rôle everyone a le même id que le serveur
                    id=int(ctx.guild_id),
                    type=0,  # role
                    deny=interactions.Permissions.VIEW_CHANNEL),
                # rôle autorisé à participer au channel
                interactions.Overwrite(
                    id=773517279328993290,
                    type=0,  # role
                    allow=interactions.Permissions.VIEW_CHANNEL | interactions.Permissions.SEND_MESSAGES | interactions.Permissions.ATTACH_FILES)]

            dict_guilde = {guilde_rouge : '🔴',
                            guilde_jaune : '🟨'}

            for guilde, color in dict_guilde.items():

                await ctx.guild.create_channel(name=f"4nat-{color}{guilde}",
                                            type=interactions.ChannelType.GUILD_TEXT,
                                            # Catégorie où le channel est crée
                                            parent_id=450771619648897034,
                                            # Permission
                                            permission_overwrites=permission)
                await ctx.guild.create_channel(name=f"5nat-{color}{guilde}",
                                            type=interactions.ChannelType.GUILD_TEXT,
                                            # Catégorie où le channel est crée
                                            parent_id=450771619648897034,
                                            # Permission
                                            permission_overwrites=permission)

            # await new_chan.send('nouveau channel')
        else:
            await ctx.send("Tu n'as pas les droits")

    @interactions.extension_command(name="score_guilde",
                                    description="Moyenne de la guilde",
                                    options=[
                                        Option(
                                            name='guilde',
                                            description='Nom de la guilde',
                                            type=interactions.OptionType.STRING,
                                            required=True,
                                        ),
                                        Option(
                                            name="methode",
                                            description="Methode de calcul",
                                            type=interactions.OptionType.STRING,  # int pas assez grand pour discord
                                            required=False,
                                            choices=[
                                                Choice(name='moyenne',
                                                       value='avg')
                                            ]),
                                        Option(name='calcul',
                                               description='quel scoring ?',
                                               type=interactions.OptionType.STRING,
                                               required=False,
                                               choices=[
                                                   Choice(name='general', value='score_general'),
                                                   Choice(name='artefact', value='scoring_arte'),
                                                   Choice(name='speed', value='score_spd')
                                               ])
                                    ])
    async def score_guilde(self,
                           ctx: CommandContext,
                           guilde: str,
                           methode: str='avg',
                           calcul='score_general'):

        await ctx.defer(ephemeral=False)

        if isOwner_slash(ctx):

            guilde_id = get_guildeid_by_name(guilde)

            size_general, avg_score_general, max_general, size_guilde, avg_score_guilde, max_guilde, df_max, df_guilde_max = await comparaison(guilde_id, calcul)

            await ctx.send(f'Moyenne de {guilde} : **{avg_score_guilde}** | ({size_guilde}) joueurs')

        else:
            await ctx.send("Tu n'es pas autorisé à utiliser cette commande.")


def setup(bot):
    SW(bot)
