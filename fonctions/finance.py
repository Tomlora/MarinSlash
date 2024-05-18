import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np
import math
from aiohttp import ClientSession, CookieJar
import urllib
from fonctions.channels_discord import get_embed
from interactions import SlashContext


class YFinance:
    user_agent_key = "User-Agent"
    user_agent_value = ("Mozilla/5.0 (Windows NT 6.1; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/58.0.3029.110 Safari/537.36")
    

    def __init__(self, ticker, session : ClientSession):
        self.yahoo_ticker = ticker
        self.session = session

    def __str__(self):
        return self.yahoo_ticker

    async def _get_yahoo_cookie(self):
        cookie = None
        session = ClientSession(cookie_jar=CookieJar())

        headers = {self.user_agent_key: self.user_agent_value}
        response = await session.get("https://fc.yahoo.com",
                                headers=headers,
                                allow_redirects=True)

        if not response.cookies:
            raise Exception("Failed to obtain Yahoo auth cookie.")

        cookie = response.cookies

        cookie_key = list(cookie.keys())[0]
        
        for key, cookie in cookie.items():
            if key == cookie_key:
                cookie_value = cookie.value

        dict_cookie = {'name' : cookie_key, 'value' : cookie_value}

        # s.cookie_jar._cookies

        await session.close()

        return dict_cookie

    async def _get_yahoo_crumb(self, cookie):
        crumb = None
        headers = {self.user_agent_key: self.user_agent_value}

        crumb_response = await self.session.get(
            "https://query1.finance.yahoo.com/v1/test/getcrumb",
            headers=headers,
            cookies={cookie['name']: cookie['value']},
            allow_redirects=True,
        )
        crumb = await crumb_response.text()



        if crumb is None:
            raise Exception("Failed to retrieve Yahoo crumb.")


        return crumb

    @property
    async def info(self):
        # Yahoo modules doc informations :
        # https://cryptocointracker.com/yahoo-finance/yahoo-finance-api
        cookie = await self._get_yahoo_cookie()
        crumb = await self._get_yahoo_crumb(cookie)

        info = {}
        ret = {}

        headers = {self.user_agent_key: self.user_agent_value}

        yahoo_modules = ("financialData,"
                         "quoteType,"
                         "defaultKeyStatistics,"
                         "assetProfile,"
                         "summaryDetail")
        


        url = ("https://query1.finance.yahoo.com/v10/finance/"
               f"quoteSummary/{self.yahoo_ticker}"
               f"?modules={urllib.parse.quote_plus(yahoo_modules)}"
               f"&ssl=true&crumb={urllib.parse.quote_plus(crumb)}")

        info_response = await self.session.get(url,
                                     headers=headers,
                                     cookies={cookie['name']: cookie['value']},
                                     allow_redirects=True)

        info = await info_response.json()
        info = info['quoteSummary']['result'][0]

        for mainKeys in info.keys():
            for key in info[mainKeys].keys():
                if isinstance(info[mainKeys][key], dict):
                    try:
                        ret[key] = info[mainKeys][key]['raw']
                    except (KeyError, TypeError):
                        pass
                else:
                    ret[key] = info[mainKeys][key]

        await self.session.close()
        return ret
    

class askFinance:

    def __init__(self, ticker):
        self.ticker = ticker

    async def filtrer_index(self, df, liste_to_keep):
        liste_to_keep_final = []
        for element in liste_to_keep:
            if element in df.index:
                liste_to_keep_final.append(element)
        
        return liste_to_keep_final
    
    
    async def ROE(self, benefice_net, capitaux_propres):
        return (benefice_net / capitaux_propres) * 100


    async def dette_nette_sur_cashflow(self, dette_nette, free_cashflow):
            return dette_nette / free_cashflow
    

    async def marge_cashflow(self, net_income, revenue):
        return (net_income / revenue) * 100


    async def marge_gross(self, margin, revenue):
        return (margin / revenue) * 100    


    async def marge_operating(self, margin, revenue):
        return (margin / revenue) * 100
    
    async def initialisation(self):
        session = ClientSession()
        self.data_info = YFinance(self.ticker, session)
        self.data_info = await self.data_info.info
        self.data = yf.Ticker(self.ticker)
        self.current_price = self.data_info['currentPrice']
        self.balance_sheet = self.data.get_balance_sheet() / 1000
        self.cashflow = self.data.cashflow / 1000
        self.income = self.data.income_stmt / 1000
        self.df = pd.concat([self.balance_sheet, self.cashflow, self.income])
        self.capitaux_propres = self.df.loc[['StockholdersEquity']]
        self.dividendes : pd.DataFrame = self.data.dividends

        self.secteur = self.data_info['sector']
        self.business = self.data_info['longBusinessSummary']


        try:
            self.dette_nette = self.df.loc[['NetDebt']]
        except:
            self.dette_nette = self.df.loc[['TotalDebt']]

        self.nb_actions = self.df.loc[['Diluted Average Shares']]

        self.balance_sheet_to_keep = await self.filtrer_index(self.df, ['Total Revenue',
                 'Cost Of Revenue',
                 'Gross Profit',
                 'Gross Margin',
                 'Research And Development',
                 'General and Administrative Expenses',
                'Selling and Marketing',
                'Selling General And Administration',
                'Operating Income',
                'Operating Margin',
                'Other Non Operating Income Expenses', # Other expenses
                 'Total Expenses', # Cost and Expenses
                 'Interest Income',
                 'Interest Expense',
                 'Normalized EBITDA',
                 'Other Income Expense', # A verifier
                 'Pretax Income',
                 'Tax Provision',
                 'Net Income'
                 ])
        
        self.balance_sheet_final = self.df.loc[self.balance_sheet_to_keep]

        self.cf_to_keep = await self.filtrer_index(self.df, [
        'Net Income',
        'Depreciation And Amortization',
        'Deferred Income Tax',
        'Stock Based Compensation',
        'Change In Working Capital',
        'Changes In Account Receivables',
        'Change In Inventory',
        'Change In Account Payable',
        'Change In Other Working Capital', # introuvable
        'Other Non Cash Items',
        'Cash Flow From Continuing Operating Activities',
        'Net PPE Purchase And Sale', # Investments Property Plant and Equipment
        'Net Business Purchase And Sale',  # acquisitions net
        'Purchase Of Investment',
        'Sale Of Investment',
        'Other Investing Activities'
        'Cash Flow From Continuing Investing Activities',
        'Repayment Of Debt',
        'Net Common Stock Issuance', # à verifier. PreferredStock ?
        'Common Stock Payments',
        'Common Stock Dividend Paid',
        'Other Financing Activities',
        'Cash Flow From Continuing Financing Activities',
        'Forex', 
        'Changes In Cash',
        'End Cash Position',
        'Beginning Cash Position',
        'Operating Cash Flow',
        'Free Cash Flow'])
        
        self.cashflow_final = self.df.loc[self.cf_to_keep]

        self.croissance_ca = self.balance_sheet_final.loc['Total Revenue'].pct_change().mean()
        self.croissance_cashflow = self.cashflow_final.loc['Free Cash Flow'].pct_change().mean()
        self.croissance_nb_actions = self.nb_actions.iloc[0].pct_change().mean() * 100 

        self.roe = await self.ROE(self.cashflow_final.loc['Net Income'], self.capitaux_propres)

        self.croissance_roe = self.roe.iloc[0].mean()  

        # Pour la dette ratio, plutot par trimestre et on va prendre le total sur 1 an

        self.balance_sheet_quarter = self.data.get_balance_sheet(freq='quarterly').iloc[:,:4]
        self.cashflow_quarter = self.data.get_cashflow(freq='quarterly').iloc[:,:4]   

        try:
            self.dette_nette = self.balance_sheet_quarter.loc['NetDebt'].mean()
        except:
            self.dette_nette = self.balance_sheet_quarter.loc['TotalDebt'].mean()
            
        try:    
            self.cashflow_net = self.cashflow_quarter.loc['FreeCashFlow'].mean()
        except:
            self.cashflow_net = 0


        self.dette_ratio = await self.dette_nette_sur_cashflow(self.dette_nette, self.cashflow_net)

        self.profit_margin = await self.marge_cashflow(self.balance_sheet_final.loc['Net Income'], self.balance_sheet_final.loc['Total Revenue'])

        self.profit_margin_mean =  self.profit_margin.mean()

        # ----


        self.profit_gross = await self.marge_gross(self.balance_sheet_final.loc['Gross Profit'], self.balance_sheet_final.loc['Total Revenue'])

        self.profit_gross_mean = self.profit_gross.mean()

        # ----

        self.profit_operating = await self.marge_operating(self.balance_sheet_final.loc['Operating Income'],self.balance_sheet_final.loc['Total Revenue'])

        self.profit_operating_mean = self.profit_operating.mean()  

        self.benef_par_action = self.data_info['trailingEps']
        self.PE_ratio = self.data_info['trailingPE']  #current_price / benef_par_action

        self.cash = self.data_info['totalCash']

        await session.close()

    async def history(self):
        hist = self.data.history(period='1mo')
        fig = px.line(hist, hist.index, 'Close')

        embed, fig = get_embed(fig)


        return embed, fig
    
    async def info_generale(self):

        df = pd.DataFrame(columns=['Stat', 'Valeur'])

        df.set_index('Stat', inplace=True)

        df.loc['Prix'] = np.round(self.current_price,2)
        df.loc['Secteur'] = self.secteur
        df.loc['Capitaux Propres'] = self.capitaux_propres.iloc[:, 0].values[0]
        df.loc['Business'] = self.business
        df.loc['Croissance CA par an'] = np.round(self.croissance_ca,2)
        df.loc['Croissance CF par an'] = np.round(self.croissance_cashflow,2)
        df.loc['Croissance ROE'] = np.round(self.croissance_roe,2)
        df.loc['Ratio Dette'] = np.round(self.dette_ratio,2)
        df.loc['Croissance NB action'] = np.round(self.croissance_nb_actions,2)
        df.loc['Profit marge moyenne'] = np.round(self.profit_margin_mean,2)
        df.loc['BPA'] = np.round(self.benef_par_action,2)
        df.loc['PE_ratio'] = np.round(self.PE_ratio,2)

        return df


    async def analyse_financiere(self):

        self.free_cashflow_par_action = self.cashflow_final.loc['Free Cash Flow'] / self.nb_actions
        self.benefice_par_action = self.balance_sheet_final.loc['Net Income'] / self.nb_actions

    async def valorisation(self):
        self.eps = self.benef_par_action

        temps = 5 # ans

        # evolution du per historique (zonebourse -> finance)
        dict_per = {'per_pessimiste' : 14,
        'per_neutre' : 20,
        'per_realiste' : 30,
        'per_optimiste' : 40}

        # yahoofinance
        dict_croissance = {
        'croissance_pessimiste' : 6.6,
        'croissance_neutre' : 9.9,
        'croissance_realiste' : 14,
        'croissance_optimiste' : 20}

        self.df_prix_cible = pd.DataFrame(columns=dict_per.keys(), index=dict_croissance.keys())

        for (cle_per, per_selected) in dict_per.items():
            
            for (cle_croissance, croissance_selected) in dict_croissance.items():

                valeur_future = round(self.eps * (math.pow((1+croissance_selected/100),temps))*per_selected,2)
                resultat = round(valeur_future/math.pow(1+0.095, temps),2)
                resultat_avec_securite = round(resultat * 0.8,2)
                
                self.df_prix_cible.loc[cle_croissance, cle_per] = resultat_avec_securite

        
        self.moyenne = (self.df_prix_cible.loc['croissance_realiste', 'per_neutre'] +
                        self.df_prix_cible.loc['croissance_realiste', 'per_realiste'] + 
                        self.df_prix_cible.loc['croissance_neutre', 'per_realiste']) / 3 
        
        self.difference = self.current_price - self.moyenne

        return self.df_prix_cible; self.moyenne, self.difference