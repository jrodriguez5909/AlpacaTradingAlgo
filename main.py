import datetime

from src.trading_classes import *
from src.slack_app_notification import *
from slack import WebClient
from slack.errors import SlackApiError


def main(days_hist=1, st_hr_for_message=6, end_hr_for_message=9, n_stocks=30, n_crypto=30):
    """
    Description: Uses your Alpaca API credentials (including whether you're paper trading or live trading based on BASE_URL) and
    sells overbought assets in portfolio then buys oversold assets in the market per YahooFinance! opportunities.

    Arguments:
        • st_hr_for_message: starting hour for interval for considering when Slack notification will be sent
        • end_hr_for_message: ending hour for interval for considering when Slack notification will be sent
        • n_stocks: number of top losing stocks from YahooFinance! to be considered for trades
        • n_crypto: number of top traded/valued crypto assets from YahooFinance! to be considered for trades
    """
    config = configparser.ConfigParser()
    config.read("creds.cfg")

    os.environ["KEY_ID"] = config["alpaca"]["KEY_ID"]
    os.environ["SECRET_KEY"] = config["alpaca"]["SECRET_KEY"]
    os.environ["client"] = config["slack"]["client"]
    BASE_URL = config["alpaca"]["BASE_URL"]

    api = tradeapi.REST(
        key_id=os.environ["KEY_ID"],
        secret_key=os.environ["SECRET_KEY"],
        base_url=BASE_URL,
    )

    ##############################
    ##############################
    ### Run TradingOpps class

    # Instantiate TradingOpportunities class
    trades = TradingOpportunities(n_stocks=n_stocks, n_crypto=n_crypto)

    # Shows all scraped opportunities; defaults to 25 top losing stocks and 25 of the most popular crypto assets
    trades.get_trading_opportunities()

    # The all_tickers attribute is a list of all tickers in the get_trading_opportunities() method. Passing this list through the get_asset_info() method shows just the tickers that meet buying criteria
    trades.get_asset_info()

    ##############################
    ##############################
    ### Run Alpaca class

    # Instantiate Alpaca class
    Alpaca_instance = Alpaca(api=api)

    # Liquidates currently held assets that meet sell criteria and stores sales in a df
    Alpaca_instance.sell_orders()

    # Execute buy_orders using trades.buy_tickers and stores buys in a tickers_bought list
    Alpaca_instance.buy_orders(tickers=trades.buy_tickers)
    Alpaca_instance.tickers_bought

    ##############################
    ##############################
    ### Slack notification

    def part_of_day():
        current_time = datetime.now(pytz.timezone("CET"))
        if current_time.hour < 12:
            return "️💰☕️ *Good morning* ☕️💰"
        else:
            return "💰🌅 *Good afternoon* 🌅💰"

    current_time = datetime.now(pytz.timezone("CET"))
    hour = current_time.hour

    if st_hr_for_message <= hour < end_hr_for_message:
        print("• Sending message")

        # Authenticate to the Slack API via the generated token
        client = WebClient(os.environ["client"])

        message = (
            f"{part_of_day()}\n\n"
            "The trading bot has made the following trades over the past 24hrs:\n\n"
            f"{slack_app_notification(days_hist=days_hist)}\n\n"
            "Happy trading!\n"
            "June's Trading Bot 🤖"
        )

        try:
            response = client.chat_postMessage(
                channel="ENTER_CHANNEL_ID_HERE",
                text=message,
                mrkdwn=True,  # Enable Markdown formatting
            )
            print("Message sent successfully")
        except SlackApiError as e:
            print(f"Error sending message: {e}")
    else:
        print("Not sending message since it's not between 6 AM and 9 AM in CET.")


if __name__ == "__main__":
    main()
