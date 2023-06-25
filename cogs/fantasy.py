import asyncio
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, slash_command
import interactions
from fonctions.gestion_bdd import requete_perso_bdd, lire_bdd_perso
from fonctions.permissions import isOwner_slash
from fonctions.channels_discord import mention

liste_competition_choice = [SlashCommandChoice(name='LEC', value='LEC'),
                            SlashCommandChoice(name='LCS', value='LCS'),
                            SlashCommandChoice(name='LFL', value='LFL')]


class Fantasy(Extension):
    def __init__(self, bot):
        self.bot: interactions.Client = bot

    @slash_command(name='fantasy_add',
                   description='participer')
    async def fantasy_add(self, ctx: SlashContext):

        await ctx.defer(ephemeral=True)

        author_id = int(ctx.author.id)
        pseudo = ctx.author.name

        requete_perso_bdd(f'''INSERT INTO fantasy_players (id_discord, pseudo) VALUES (:author_id, :pseudo)''',
                          dict_params={'author_id': author_id,
                                       'pseudo': pseudo})

        await ctx.send('Ajouté')

    @slash_command(name='fantasy_bet',
                   description="test",
                   options=[
                       SlashCommandOption(name='competition',
                                          description='Quel compétition ?',
                                          required=True,
                                          type=interactions.OptionType.STRING,
                                          choices=liste_competition_choice)]
                   )
    async def fantasy_bet(self, ctx: SlashContext, competition: str):
        embed1 = interactions.Embed(title='test', description='test1')

        await ctx.defer(ephemeral=True)

        semaine = 1

        author_id = int(ctx.author.id)

        # on vérifie qu'il n'y a pas déjà eu de paris faits sur ces matchs
        df_bet_joueur = lire_bdd_perso(f'''SELECT * FROM fantasy_bet
                           WHERE id_discord = {author_id}
                           AND semaine = {semaine}
                           AND competition = '{competition}' ''', index_col='id_discord').transpose()

        if not df_bet_joueur.empty:
            return await ctx.send('Tu as déjà parié sur ces matchs')

        def componants_equipe_vs_equipe(equipe1: str, equipe2: str, numero_button: int):

            numero_button += 1  # pour éviter le 0. Le match commence à 1

            button1 = interactions.Button(
                custom_id=f'button_{numero_button}',
                style=interactions.ButtonStyle.BLUE,
                label=equipe1,
            )

            button2 = interactions.Button(
                custom_id=f'button_{numero_button+100}',
                style=interactions.ButtonStyle.RED,
                label=equipe2
            )

            return interactions.ActionRow(components=[button1, button2])

        # possibilité de faire deux listes avec les équipes bleus + red, et faire -> for equipe_bleu, equipe_red in zip(liste_bleu, liste_red)

        liste_bleu = ['FNC', 'SK']
        liste_rouge = ['G2', 'MAD']

        liste_components = [componants_equipe_vs_equipe(equipe_bleu, equipe_red, n) for n, (
            equipe_bleu, equipe_red) in enumerate(zip(liste_bleu, liste_rouge))]

        msg = await ctx.send(embeds=embed1, components=liste_components)

        async def check(button_ctx):
            if int(button_ctx.author.user.id) == int(ctx.author.user.id):
                return True
            await ctx.send("I wasn't asking you!", ephemeral=True)
            return False

        while True:
            try:
                button_ctx: interactions.ComponentContext = await self.bot.wait_for_component(
                    components=liste_components, check=check, timeout=300
                )

                df_bet = lire_bdd_perso(f'''SELECT * FROM fantasy_bet
                                WHERE id_discord = {author_id}
                                AND semaine = {semaine}
                                AND nb_match = '{button_ctx.custom_id[-1]}' ''', index_col='id_discord').transpose()

                if df_bet.empty:
                    requete_perso_bdd('''INSERT INTO fantasy_bet (id_discord, semaine, nb_match, vainqueur, competition)
                                        VALUES (:author_id, :semaine, :nb_match, :vainqueur, :competition) ''',
                                      dict_params={'author_id': author_id,
                                                   'semaine': semaine,
                                                   'nb_match': button_ctx.custom_id[-1],
                                                   'vainqueur': button_ctx.ctx.label,
                                                   'competition': competition})
                    await ctx.send(f'Enregistré pour {button_ctx.ctx.label}', ephemeral=True)
                else:
                    await ctx.send('Tu as déjà parié sur ce match', ephemeral=True)

            except asyncio.TimeoutError:
                # When it times out, edit the original message and remove the button(s)
                return await ctx.edit(components=[])

    @slash_command(name='fantasy_result',
                   description='resultat',
                   options=[
                       SlashCommandOption(name='semaine',
                                          description='week number',
                                          required=True,
                                          type=interactions.OptionType.INTEGER),
                       SlashCommandOption(name='nb_match',
                                          description='Jour 1 : 1 a 5, Jour 2 : 6 à 10, Jour 3 : 11 à 15',
                                          required=True,
                                          type=interactions.OptionType.INTEGER),
                       SlashCommandOption(name='competition',
                                          description='competition',
                                          required=True,
                                          type=interactions.OptionType.STRING,
                                          choices=liste_competition_choice),
                       SlashCommandOption(name='vainqueur1',
                                          description='vainqueur du premier match',
                                          required=True,
                                          type=interactions.OptionType.STRING),
                       SlashCommandOption(name='vainqueur2',
                                          description='vainqueur du match 2',
                                          required=True,
                                          type=interactions.OptionType.STRING),
                       SlashCommandOption(name='vainqueur3',
                                          description='vainqueur du match 3',
                                          required=True,
                                          type=interactions.OptionType.STRING),
                       SlashCommandOption(name='vainqueur4',
                                          description='vainqueur du match 4',
                                          required=True,
                                          type=interactions.OptionType.STRING),
                       SlashCommandOption(name='vainqueur5',
                                          description='vainqueur du match 5',
                                          required=True,
                                          type=interactions.OptionType.STRING),
                   ])
    async def fantasy_result(self,
                             ctx: SlashContext,
                             semaine: int,
                             nb_match: int,
                             competition: str,
                             vainqueur1: str,
                             vainqueur2: str,
                             vainqueur3: str,
                             vainqueur4: str,
                             vainqueur5: str):

        await ctx.defer(ephemeral=False)

        liste_vainqueur = [vainqueur1, vainqueur2,
                           vainqueur3, vainqueur4, vainqueur5]
        if isOwner_slash(ctx):

            df_joueurs = lire_bdd_perso(
                'SELECT * FROM fantasy_players', index_col='id_discord').transpose()

            df_bet = lire_bdd_perso(
                'SELECT * FROM fantasy_bet', index_col='id').transpose()

            msg = f'**{competition}** : \n'

            def gestion_result(semaine: int, nb_match: int, vainqueur: str, competition: str):
                new_msg = ''
                requete_perso_bdd('''UPDATE fantasy_players as fp
                                    SET points = fp.points + 1
                                    FROM fantasy_bet as fb
                                    WHERE fp.id_discord = fb.id_discord
                                    AND semaine = :semaine
                                    AND nb_match = :nb_match
                                    AND competition = :competition
                                    AND vainqueur = :vainqueur_reel''',
                                  dict_params={'semaine': semaine,
                                               'nb_match': nb_match,
                                               'vainqueur_reel': vainqueur,
                                               'competition': competition})

                df_vainqueur = df_bet[(df_bet['semaine'] == semaine) & (df_bet['nb_match'] == nb_match) & (
                    df_bet['competition'] == competition) & (df_bet['vainqueur'] == vainqueur)]

                for id_vainqueur in df_vainqueur['id_discord'].to_list():
                    new_msg += new_msg + \
                        f'**{df_joueurs.loc[id_vainqueur]["pseudo"]}** a gagné 1 point en misant pour {vainqueur} \n'

                return new_msg

            for i, vainqueur in enumerate(liste_vainqueur):
                msg += gestion_result(semaine, nb_match + i,
                                      vainqueur, competition)

            await ctx.send(msg)

        else:
            await ctx.send('Vous n\'avez pas les droits pour faire cette commande')


def setup(bot):
    Fantasy(bot)
