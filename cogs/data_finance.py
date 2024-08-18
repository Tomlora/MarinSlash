from fonctions.finance import askFinance
import interactions
from interactions import SlashCommandOption, Extension, SlashContext, SlashCommandChoice, slash_command
import os
import dataframe_image as dfi
import yfinance as yf
import numpy as np
import plotly_express as px
from fonctions.channels_discord import get_embed
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta
import plotly.graph_objects as go

# Activity au lancement du bot

async def export_as_image(df, ctx : SlashContext, content=None):
    dfi.export(df, 'image.png', max_cols=-1,
                       max_rows=-1, table_conversion="matplotlib")

    if content == None:
        await ctx.send(files=interactions.File('image.png'))
    
    else:
        await ctx.send(content=content, files=interactions.File('image.png'))
    

    os.remove('image.png')

class data_finance(Extension):
    def __init__(self, bot: interactions.Client):
        self.bot = bot

    @slash_command(name='finance', description='Données financières')
    async def finance(self, ctx: SlashContext):
        pass    

    @finance.subcommand("info_generale",
                            sub_cmd_description="Info générale sur une entreprise",
                            options=[
                                SlashCommandOption(name="ticker",
                                                    description="Ticker de l'entreprise",
                                                    type=interactions.OptionType.STRING,
                                                    required=True),
                                SlashCommandOption(name="vue",
                                          description="parametres",
                                          type=interactions.OptionType.STRING,
                                          required=True,
                                          choices=[
                                              SlashCommandChoice(
                                                  name='General', value='general'),
                                              SlashCommandChoice(
                                                  name='Balance commerciale', value='balanced'),
                                              SlashCommandChoice(
                                                  name='Cashflow', value='cashflow'),
                                              SlashCommandChoice(
                                                  name='Revenus', value='revenu'),
                                               SlashCommandChoice(name='Dividende', value='dividende')])])
    async def info_generale(self,
                        ctx: SlashContext,
                        ticker,
                        vue):
        
        await ctx.defer(ephemeral=False)

        entreprise = askFinance(ticker)

        await entreprise.initialisation()

        if entreprise.type == 'ETF':
            df = await entreprise.info_generale()
            content = '** Note ** : Seul le général est disponible pour les ETF.'
        else:
            content = None
            match vue:
                case 'general':
                    df = await entreprise.info_generale()
                case 'balanced': 
                    df = entreprise.balance_sheet_final / 1000
                case 'cashflow':
                    df = entreprise.cashflow_final / 1000
                case 'revenu':
                    df = entreprise.income / 1000
                case 'dividende':
                    df = entreprise.dividendes


        await export_as_image(df, ctx, content)

    @finance.subcommand("evolution",
                            sub_cmd_description="Evolution prix d'une entreprise",
                            options=[
                                SlashCommandOption(name="ticker",
                                                    description="Ticker de l'entreprise",
                                                    type=interactions.OptionType.STRING,
                                                    required=True),
                                SlashCommandOption(name="periode",
                                          description="Periode",
                                          type=interactions.OptionType.STRING,
                                          required=True,
                                          choices=[
                                                SlashCommandChoice(
                                                  name='3 jours', value='3d'),
                                                SlashCommandChoice(
                                                  name='1 semaine', value='7d'),
                                                SlashCommandChoice(
                                                  name='2 semaines', value='14d'),
                                              SlashCommandChoice(
                                                  name='1 mois', value='1mo'),
                                              SlashCommandChoice(
                                                  name='6 mois', value='6mo'),
                                              SlashCommandChoice(
                                                  name='1 an', value='1y'),
                                              SlashCommandChoice(
                                                  name='3 ans', value='3y'),
                                            SlashCommandChoice(name='5 ans', value='5y'),
                                            SlashCommandChoice(name='10 ans', value='10y')])])
    async def evolution(self,
                        ctx: SlashContext,
                        ticker,
                        periode):
        
        await ctx.defer(ephemeral=False)

        entreprise = askFinance(ticker)

        await entreprise.initialisation()

        embed, file = await entreprise.history(periode)
        await ctx.send(embeds=embed, files=file)

    @finance.subcommand("valorisation",
                            sub_cmd_description="Info générale sur une entreprise",
                            options=[
                                SlashCommandOption(name="ticker",
                                                    description="Ticker de l'entreprise",
                                                    type=interactions.OptionType.STRING,
                                                    required=True)])
    async def valorisation(self,
                        ctx: SlashContext,
                        ticker):
        
        await ctx.defer(ephemeral=False)

        entreprise = askFinance(ticker)

        await entreprise.initialisation()

        if entreprise.type != 'ETF':

            df_valorisation, prix_moyen, difference = await entreprise.valorisation()

            prix_actuel = entreprise.current_price


            await export_as_image(df_valorisation, ctx, f'Prix actuel : {prix_actuel} | Prix moyen : **{prix_moyen}** | (Différence de **{difference}**)')

        else:
            ctx.send("Cette méthode n'est pas adaptée aux ETF")


    @finance.subcommand("correlation",
                            sub_cmd_description="Corrélation entre entreprise",
                            options=[
                                SlashCommandOption(name="ticker",
                                                    description="Tickers des entreprises avec un espace entre chaque : TTE.PA STLAP.PA",
                                                    type=interactions.OptionType.STRING,
                                                    required=True),
                                SlashCommandOption(name="periode",
                                          description="Periode",
                                          type=interactions.OptionType.STRING,
                                          required=False,
                                          choices=[
                                                SlashCommandChoice(
                                                  name='3 jours', value='3d'),
                                                SlashCommandChoice(
                                                  name='1 semaine', value='7d'),
                                                SlashCommandChoice(
                                                  name='2 semaines', value='14d'),
                                              SlashCommandChoice(
                                                  name='1 mois', value='1mo'),
                                              SlashCommandChoice(
                                                  name='6 mois', value='6mo'),
                                              SlashCommandChoice(
                                                  name='1 an', value='1y'),
                                              SlashCommandChoice(
                                                  name='3 ans', value='3y'),
                                            SlashCommandChoice(name='5 ans', value='5y'),
                                            SlashCommandChoice(name='10 ans', value='10y')])])
    
    async def correlation(self,
                        ctx: SlashContext,
                        ticker : str,
                        periode='max'):  

      
        liste_ticker = ticker.split(' ')  

        await ctx.defer(ephemeral=False)

        data = yf.download(list(liste_ticker), period=periode)

        data = data['Adj Close']

        fig = px.imshow(np.round(data.corr(),2), text_auto=True, aspect="auto")

        del data

        embed, file = get_embed(fig, name='correlation')

        await ctx.send(embeds=embed, files=file)

    @finance.subcommand("evolutions",
                            sub_cmd_description="Corrélation entre entreprise",
                            options=[
                                SlashCommandOption(name="ticker",
                                                    description="Tickers des entreprises avec un espace entre chaque : TTE.PA STLAP.PA",
                                                    type=interactions.OptionType.STRING,
                                                    required=True),
                                SlashCommandOption(name="periode",
                                          description="Periode",
                                          type=interactions.OptionType.STRING,
                                          required=False,
                                          choices=[
                                                SlashCommandChoice(
                                                  name='3 jours', value='3d'),
                                                SlashCommandChoice(
                                                  name='1 semaine', value='7d'),
                                                SlashCommandChoice(
                                                  name='2 semaines', value='14d'),
                                              SlashCommandChoice(
                                                  name='1 mois', value='1mo'),
                                              SlashCommandChoice(
                                                  name='6 mois', value='6mo'),
                                              SlashCommandChoice(
                                                  name='1 an', value='1y'),
                                              SlashCommandChoice(
                                                  name='3 ans', value='3y'),
                                            SlashCommandChoice(name='5 ans', value='5y'),
                                            SlashCommandChoice(name='10 ans', value='10y')])])
    async def evolutions(self,
                        ctx: SlashContext,
                        ticker : str,
                        periode='max'):  

      
        liste_ticker = ticker.split(' ')  

        await ctx.defer(ephemeral=False)

        data = yf.download(list(liste_ticker), period=periode)

        data = data['Adj Close']

        data_melt = data.melt(ignore_index=False)

        fig = px.line(data_melt, x=data_melt.index, y='value', color='Ticker')

        embed, file = get_embed(fig, name='evolution')

        del data, data_melt

        await ctx.send(embeds=embed, files=file)


    @finance.subcommand("analyse_graphique",
                            sub_cmd_description="Analyse d'une entreprise",
                            options=[
                                SlashCommandOption(name="ticker",
                                                    description="Ticker",
                                                    type=interactions.OptionType.STRING,
                                                    required=True),
                                SlashCommandOption(name='linear',
                                                   description='Afficher uniquement le prix à la fermeture',
                                                   type=interactions.OptionType.BOOLEAN,
                                                   required=False),
                                SlashCommandOption(name="periode",
                                          description="Periode",
                                          type=interactions.OptionType.STRING,
                                          required=False,
                                          choices=[
                                                SlashCommandChoice(
                                                  name='3 jours', value='3d'),
                                                SlashCommandChoice(
                                                  name='1 semaine', value='7d'),
                                                SlashCommandChoice(
                                                  name='2 semaines', value='14d'),
                                              SlashCommandChoice(
                                                  name='1 mois', value='1mo'),
                                              SlashCommandChoice(
                                                  name='6 mois', value='6mo'),
                                              SlashCommandChoice(
                                                  name='1 an', value='1y')]),
                                SlashCommandOption(name='tendance',
                                                   description='Afficher la tendance',
                                                   type=interactions.OptionType.BOOLEAN,
                                                   required=False),
                                SlashCommandOption(name='bollinger',
                                                   description='Afficher les bandes de bollinger',
                                                   type=interactions.OptionType.BOOLEAN,
                                                   required=False)])
    async def analysegraphique(self,
                        ctx: SlashContext,
                        ticker : str,
                        linear = False,
                        periode='150d',
                        tendance=False,
                        bollinger=False):  

       
        data = yf.Ticker(ticker)


        await ctx.defer(ephemeral=False)

        hist = data.history(period=periode)

        hist.reset_index(inplace=True)

        hist['average_rolling12j'] = hist.rolling(12, on='Date', min_periods=12)['Close'].mean()
        hist['average_rolling2j'] = hist.rolling(2, on='Date', min_periods=2)['Close'].mean()

        # Bollinger 
        # Calculate the 20-period Simple Moving Average (SMA)
        hist['SMA'] = hist['Close'].rolling(window=20).mean()

        # Calculate the 20-period Standard Deviation (SD)
        hist['SD'] = hist['Close'].rolling(window=20).std()

        # Calculate the Upper Bollinger Band (UB) and Lower Bollinger Band (LB)
        hist['UB'] = hist['SMA'] + 2 * hist['SD']
        hist['LB'] = hist['SMA'] - 2 * hist['SD']

        fig = go.Figure()

        if linear:

            fig.add_trace(go.Scatter(x=hist['Date'],
                                    y=hist['Close'],
                                    name='Close',
                                    mode='lines'))
        
        else:
            fig = go.Figure(data=[go.Candlestick(x=hist['Date'],
                            open=hist['Open'],
                            high=hist['High'],
                            low=hist['Low'],
                            close=hist['Close'])])

        X = np.array(hist.index.astype('int64')).reshape(-1,1)
        lr = LinearRegression().fit(X=X,
                                    y=hist['Close'])
        
        if tendance:

            fig.add_trace(go.Scatter(x=hist['Date'],
                                    y=lr.predict(X),
                                    name='trend',
                                    mode='lines'))
            
        if bollinger:
            # Add the Upper Bollinger Band (UB) and shade the area
            fig.add_trace(go.Scatter(x=hist['Date'], y=hist['UB'], mode='lines', name='Upper Bollinger Band', line=dict(color='red')))
            fig.add_trace(go.Scatter(x=hist['Date'], y=hist['LB'], fill='tonexty', mode='lines', name='Lower Bollinger Band', line=dict(color='cyan')))

        fig.add_trace(go.Scatter(x=hist['Date'],
                                y=hist['average_rolling12j'],
                                name='Moyenne mobile 12j',
                                mode='lines'))

        fig.add_trace(go.Scatter(x=hist['Date'],
                                y=hist['average_rolling2j'],
                                name='Moyenne mobile 2j',
                                mode='lines'))

        fig.update_layout(
            autosize=False,
            width=2000,
            height=1500,
            title=f'Analyse Graphique {ticker}'
            )
        

        fig.update_yaxes(dtick=1)

        fig.update_xaxes(range=[hist['Date'].min(), hist['Date'].max() + timedelta(days=90)])

        embed, file = get_embed(fig, name='Analyse Graphique')

        await ctx.send(embeds=embed, files=file)




def setup(bot):
    data_finance(bot)