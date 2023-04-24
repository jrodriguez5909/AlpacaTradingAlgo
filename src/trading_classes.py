import os
import pandas as pd
import yfinance as yf
import alpaca_py as tradeapi
import configparser
import pytz
import locale
import pandas_market_calendars as mcal

from alpaca_py.rest import APIError
from ta.volatility import BollingerBands
from ta.momentum import RSIIndicator
from ta.trend import sma_indicator
from tqdm import tqdm
from requests_html import HTMLSession
from datetime import datetime


class TradingOpportunities:
    def __init__(self, n_stocks=25, n_crypto=25):
        """
        Description:
        Grabs top stock losers and highest valued crypto assets from YahooFinance! to determine trading opportunities using simple technical trading indicators
        such as Bollinger Bands and RSI.

        Arguments:
            •  n_stocks: number of top losing stocks that'll be pulled from YahooFinance! and considered in the algo
            •  n_crypto: number of top traded and most valuable crypto assets that'll be pulled from YahooFinance! and considered in the algo

        Methods:
            • raw_get_daily_info(): Grabs a provided site and transforms HTML to a pandas df
            • get_trading_opportunities(): Grabs df from raw_get_daily_info() and provides just the top "n" losers declared by user in n_stocks and "n" amount of top of most popular crypto assets to examine
            • get_asset_info(): a df can be provided to specify which assets you'd like info for since this method is used in the Alpaca class. If no df argument is passed then tickers from get_trading_opportunities() method are used.
        """

        self.n_stocks = n_stocks
        self.n_crypto = n_crypto

    def raw_get_daily_info(self, site):
        """
        Description:
        Grabs a provided site and transforms HTML to a pandas df

        Argument(s):
            • site: YahooFinance! top losers website provided in the get_day_losers() function below

        Other Notes:
        Commented out the conversion of market cap and volume from string to float since this threw an error.
        Can grab this from the yfinance API if needed or come back to this function and fix later.
        """

        session = HTMLSession()
        response = session.get(site)

        tables = pd.read_html(response.html.raw_html)
        df = tables[0].copy()
        df.columns = tables[0].columns

        session.close()
        return df

    def get_trading_opportunities(self, n_stocks=None, n_crypto=None):
        """
        Description:
        Grabs df from raw_get_daily_info() and provides just the top "n" losers declared by user in n_stocks and "n" amount of top of most popular crypto assets to examine

        Argument(s):
            • n_stocks: Number of top losers to analyze per YahooFinance! top losers site.
            • n_crypto: Number of most popular crypto assets to grab historical price info from.
        """

        #####################
        #####################
        # Crypto part
        df_crypto = []
        i = 0
        while True:
            try:
                df_crypto.append(
                    self.raw_get_daily_info(
                        "https://finance.yahoo.com/crypto?offset={}&count=100".format(i)
                    )
                )
                i += 100
                print("processing " + i)
            except:
                break

        df_crypto = pd.concat(df_crypto)
        df_crypto["asset_type"] = "crypto"

        df_crypto = df_crypto.head(self.n_crypto)

        #####################
        #####################
        # Stock part
        df_stock = self.raw_get_daily_info(
            "https://finance.yahoo.com/losers?offset=0&count=100"
        )
        df_stock["asset_type"] = "stock"

        df_stock = df_stock.head(self.n_stocks)

        #####################
        #####################
        # Merge df's and return as one
        dfs = [df_crypto, df_stock]
        df_opportunities = pd.concat(dfs, axis=0).reset_index(drop=True)

        # Create a list of all tickers scraped
        self.all_tickers = list(df_opportunities["Symbol"])

        return df_opportunities

    def get_asset_info(self, df=None):
        """
        Description:
        Grabs historical prices for assets, calculates RSI and Bollinger Bands tech signals, and returns a df with all this data for the assets meeting the buy criteria.

        Argument(s):
            • df: a df can be provided to specify which assets you'd like info for since this method is used in the Alpaca class. If no df argument is passed then tickers from get_trading_opportunities() method are used.
        """

        # Grab technical stock info:
        if df is None:
            all_tickers = self.all_tickers
        else:
            all_tickers = list(df["yf_ticker"])

        df_tech = []
        for i, symbol in tqdm(
            enumerate(all_tickers),
            desc="• Grabbing technical metrics for "
            + str(len(all_tickers))
            + " assets",
        ):
            try:
                Ticker = yf.Ticker(symbol)
                Hist = Ticker.history(period="1y", interval="1d")

                for n in [14, 30, 50, 200]:
                    # Initialize MA Indicator
                    Hist["ma" + str(n)] = sma_indicator(
                        close=Hist["Close"], window=n, fillna=False
                    )
                    # Initialize RSI Indicator
                    Hist["rsi" + str(n)] = RSIIndicator(
                        close=Hist["Close"], window=n
                    ).rsi()
                    # Initialize Hi BB Indicator
                    Hist["bbhi" + str(n)] = BollingerBands(
                        close=Hist["Close"], window=n, window_dev=2
                    ).bollinger_hband_indicator()
                    # Initialize Lo BB Indicator
                    Hist["bblo" + str(n)] = BollingerBands(
                        close=Hist["Close"], window=n, window_dev=2
                    ).bollinger_lband_indicator()

                df_tech_temp = Hist.iloc[-1:, -16:].reset_index(drop=True)
                df_tech_temp.insert(0, "Symbol", Ticker.ticker)
                df_tech.append(df_tech_temp)
            except:
                KeyError
            pass

        df_tech = [x for x in df_tech if not x.empty]
        df_tech = pd.concat(df_tech)

        # Define the buy criteria
        buy_criteria = (
            (df_tech[["bblo14", "bblo30", "bblo50", "bblo200"]] == 1).any(axis=1)
        ) | ((df_tech[["rsi14", "rsi30", "rsi50", "rsi200"]] <= 30).any(axis=1))

        # Filter the DataFrame
        buy_filtered_df = df_tech[buy_criteria]

        # Create a list of tickers to trade
        self.buy_tickers = list(buy_filtered_df["Symbol"])

        return buy_filtered_df


class Alpaca:
    def __init__(self, api):
        """
        Description: Object providing Alpaca balance details and executes buy/sell trades

        Arguments:
        • api: this object should be created before instantiating the class and it should contain your Alpaca keys
        •

        Methods:
        • get_current_positions(): shows current balance of Alpaca account
        """

        config = configparser.ConfigParser()
        config.read('creds.cfg')

        self.api = tradeapi.REST(
            key_id=os.environ['KEY_ID'],
            secret_key=os.environ['SECRET_KEY'],
            base_url=config['alpaca']['BASE_URL']
        )

    def get_current_positions(self):
        """
        Description: Returns a df with current positions in account

        Argument(s):
        • api: this is the instantiated session you'll need to kick-off define before doing any analysis.
        """

        investments = pd.DataFrame({
            'asset': [x.symbol for x in self.api.list_positions()],
            'current_price': [x.current_price for x in self.api.list_positions()],
            'qty': [x.qty for x in self.api.list_positions()],
            'market_value': [x.market_value for x in self.api.list_positions()],
            'profit_dol': [x.unrealized_pl for x in self.api.list_positions()],
            'profit_pct': [x.unrealized_plpc for x in self.api.list_positions()]
        })

        cash = pd.DataFrame({
            'asset': 'Cash',
            'current_price': self.api.get_account().cash,
            'qty': self.api.get_account().cash,
            'market_value': self.api.get_account().cash,
            'profit_dol': 0,
            'profit_pct': 0
        }, index=[0])  # Need to set index=[0] since passing scalars in df

        assets = pd.concat([investments, cash], ignore_index=True)

        float_fmt = ['current_price', 'qty', 'market_value', 'profit_dol', 'profit_pct']
        str_fmt = ['asset']

        for col in float_fmt:
            assets[col] = assets[col].astype(float)

        for col in str_fmt:
            assets[col] = assets[col].astype(str)

        rounding_2 = ['market_value', 'profit_dol']
        rounding_4 = ['profit_pct']

        assets[rounding_2] = assets[rounding_2].apply(lambda x: pd.Series.round(x, 2))
        assets[rounding_4] = assets[rounding_4].apply(lambda x: pd.Series.round(x, 4))

        asset_sum = assets['market_value'].sum()
        assets['portfolio_pct'] = assets['market_value'] / asset_sum

        # Add yf_ticker column so look up of Yahoo Finance! prices is easier
        assets['yf_ticker'] = assets['asset'].apply(lambda x: x[:3] + '-' + x[3:] if len(x) == 6 else x)

        return assets

    @staticmethod
    def is_market_open():
        nyse = pytz.timezone('America/New_York')
        current_time = datetime.now(nyse)

        nyse_calendar = mcal.get_calendar('NYSE')
        market_schedule = nyse_calendar.schedule(start_date=current_time.date(), end_date=current_time.date())

        if not market_schedule.empty:
            market_open = market_schedule.iloc[0]['market_open'].to_pydatetime().replace(tzinfo=None)
            market_close = market_schedule.iloc[0]['market_close'].to_pydatetime().replace(tzinfo=None)
            current_time_no_tz = current_time.replace(tzinfo=None)

            if market_open <= current_time_no_tz <= market_close:
                return True

        return False

    def sell_orders(self):
        """
        Description:
        Liquidates positions of assets currently held based on technical signals or to free up cash for purchases.

        Argument(s):
        • self.df_current_positions: Needed to inform how much of each position should be sold.
        """

        # Get the current time in Eastern Time
        et_tz = pytz.timezone('US/Eastern')
        current_time = datetime.now(et_tz)

        # Define the sell criteria
        TradeOpps = TradingOpportunities()
        df_current_positions = self.get_current_positions()
        df_current_positions_hist = TradeOpps.get_asset_info(
            df=df_current_positions[df_current_positions['yf_ticker'] != 'Cash'])

        # Sales based on technical indicator
        sell_criteria = ((df_current_positions_hist[['bbhi14', 'bbhi30', 'bbhi50', 'bbhi200']] == 1).any(axis=1)) | \
                        ((df_current_positions_hist[['rsi14', 'rsi30', 'rsi50', 'rsi200']] >= 70).any(axis=1))

        # Filter the DataFrame
        sell_filtered_df = df_current_positions_hist[sell_criteria]
        sell_filtered_df['alpaca_symbol'] = sell_filtered_df['Symbol'].str.replace('-', '')
        symbols = list(sell_filtered_df['alpaca_symbol'])

        # Determine whether to trade all symbols or only those with "-USD" in their name
        if self.is_market_open():
            eligible_symbols = symbols
        else:
            eligible_symbols = [symbol for symbol in symbols if "-USD" in symbol]

            # Submit sell orders for eligible symbols
        executed_sales = []
        for symbol in eligible_symbols:
            try:
                if symbol in symbols:  # Check if the symbol is in the sell_filtered_df
                    print("• selling " + str(symbol))
                    qty = df_current_positions[df_current_positions['asset'] == symbol]['qty'].values[0]
                    self.api.submit_order(
                        symbol=symbol,
                        time_in_force='gtc',
                        qty=qty,
                        side="sell"
                    )
                    executed_sales.append([symbol, round(qty)])
            except Exception as e:
                continue

        executed_sales_df = pd.DataFrame(executed_sales, columns=['ticker', 'quantity'])

        if len(eligible_symbols) == 0:
            self.sold_message = "• liquidated no positions based on the sell criteria"
        else:
            self.sold_message = f"• executed sell orders for {''.join([symbol + ', ' if i < len(eligible_symbols) - 1 else 'and ' + symbol for i, symbol in enumerate(eligible_symbols)])}based on the sell criteria"

        print(self.sold_message)

        # Check if the Cash row in df_current_positions is at least 10% of total holdings
        cash_row = df_current_positions[df_current_positions['asset'] == 'Cash']
        total_holdings = df_current_positions['market_value'].sum()

        if cash_row['market_value'].values[0] / total_holdings < 0.1:
            # Sort the df_current_positions by profit_pct descending
            df_current_positions = df_current_positions.sort_values(by=['profit_pct'], ascending=False)

            # Sell the top 25% of performing assets evenly to make Cash 10% of the total portfolio
            top_half = df_current_positions.iloc[:len(df_current_positions) // 4]
            top_half_market_value = top_half['market_value'].sum()
            cash_needed = total_holdings * 0.1 - cash_row['market_value'].values[0]

            for index, row in top_half.iterrows():
                print("• selling " + str(row['asset']) + " for 10% portfolio cash requirement")
                amount_to_sell = int((row['market_value'] / top_half_market_value) * cash_needed)

                # If the amount_to_sell is zero or an APIError occurs, continue to the next iteration
                if amount_to_sell == 0:
                    continue

                try:
                    self.api.submit_order(
                        symbol=row['asset'],
                        time_in_force="day",
                        type="market",
                        notional=amount_to_sell,
                        side="sell"
                    )
                    executed_sales.append([row['asset'], amount_to_sell])
                except APIError:
                    continue

            # Set the locale to the US
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

            # Convert cash_needed to a string with dollar sign and commas
            cash_needed_str = locale.currency(cash_needed, grouping=True)

            print("• Sold " + cash_needed_str + " of top 25% of performing assets to reach 10% cash position")

        return executed_sales_df

    def buy_orders(self, tickers):
        """
        Description:
        Buys assets per buying opportunities uncovered in the get_asset_info() function.

        Argument(s):
        • df_current_positions: Needed to understand available cash for purchases.
        • symbols: Assets to be purchased.
        """

        # Get the current positions and available cash
        df_current_positions = self.get_current_positions()
        available_cash = df_current_positions[df_current_positions['asset'] == 'Cash']['market_value'].values[0]

        # Get the current time in Eastern Time
        et_tz = pytz.timezone('US/Eastern')
        current_time = datetime.now(et_tz)

        # Determine whether to trade all symbols or only those with "-USD" in their name
        if self.is_market_open():
            eligible_symbols = tickers
        else:
            eligible_symbols = [symbol for symbol in tickers if "-USD" in symbol]

            # Submit buy orders for eligible symbols
        for symbol in eligible_symbols:
            try:
                if len(symbol) >= 6:
                    self.api.submit_order(
                        symbol=symbol,
                        time_in_force='gtc',
                        notional=available_cash / len(eligible_symbols),
                        side="buy"
                    )
                else:
                    self.api.submit_order(
                        symbol=symbol,
                        type='market',
                        notional=available_cash / len(eligible_symbols),
                        side="buy"
                    )

            except Exception as e:
                continue

        if len(eligible_symbols) == 0:
            self.bought_message = "• executed no buy orders based on the buy criteria"
        else:
            self.bought_message = f"• executed buy orders for {''.join([symbol + ', ' if i < len(eligible_symbols) - 1 else 'and ' + symbol for i, symbol in enumerate(eligible_symbols)])}based on the buy criteria"

        print(self.bought_message)

        self.tickers_bought = eligible_symbols
