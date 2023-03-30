import os
import configparser
import alpaca_trade_api as tradeapi

from datetime import datetime

# These are paper trading config details
config = configparser.ConfigParser()
config.read("creds.cfg")

os.environ["KEY_ID"] = config["alpaca"]["KEY_ID"]
os.environ["SECRET_KEY"] = config["alpaca"]["SECRET_KEY"]

BASE_URL = "https://paper-api.alpaca.markets"

api = tradeapi.REST(
    key_id=os.environ["KEY_ID"], secret_key=os.environ["SECRET_KEY"], base_url=BASE_URL
)


def slack_app_notification(days_hist=1):
    """
    Description: creates a formatted string detailing

    Arguments:
        • days_hist: examines how many days back you want the bot to gather trading info for
    """
    # Initialize variables for total sales and purchases
    total_sales = 0
    total_purchases = 0

    # Initialize dictionaries to store asset details
    crypto_sales = {}
    crypto_purchases = {}
    stock_sales = {}
    stock_purchases = {}

    # Get the current timestamp in seconds
    current_time = int(datetime.now().timestamp())

    # Calculate the start time for the trade history query (86.4k seconds = last 24hrs)
    start_time = datetime.utcfromtimestamp(current_time - days_hist * 864000).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    # Get the trade history for the last 24 hours
    trades = api.get_activities(
        activity_types="FILL", direction="desc", after=start_time
    )

    # Parse the trade information
    for trade in trades:
        symbol = trade.symbol
        amount = round(float(trade.qty) * float(trade.price), 2)
        if trade.side == "sell":
            total_sales += amount
            if "USD" in symbol:
                crypto_sales[symbol] = crypto_sales.get(symbol, 0) + amount
            else:
                stock_sales[symbol] = stock_sales.get(symbol, 0) + amount
        else:
            total_purchases += amount
            if "USD" in symbol:
                crypto_purchases[symbol] = crypto_purchases.get(symbol, 0) + amount
            else:
                stock_purchases[symbol] = stock_purchases.get(symbol, 0) + amount

    # Format the results
    results = []

    total_sales_str = f"*`Total Sales: ${total_sales:,.2f}`*"
    total_purchases_str = f"*`Total Purchases: ${total_purchases:,.2f}`*"

    if crypto_sales:
        crypto_sales_sorted = sorted(
            crypto_sales.items(), key=lambda x: x[1], reverse=True
        )
        crypto_sales_formatted = [
            "  _*Crypto: $" + f"{sum(crypto_sales.values()):,.2f}*_"
        ]
        for symbol, amount in crypto_sales_sorted:
            crypto_sales_formatted.append(f"    {symbol} | Amount: ${amount:,.2f}")
        results.append(total_sales_str)
        results += crypto_sales_formatted
        results.append("")

    if stock_sales:
        stock_sales_sorted = sorted(
            stock_sales.items(), key=lambda x: x[1], reverse=True
        )
        stock_sales_formatted = [
            "  _*Stocks: $" + f"{sum(stock_sales.values()):,.2f}*_"
        ]
        for symbol, amount in stock_sales_sorted:
            stock_sales_formatted.append(f"    {symbol} | Amount: ${amount:,.2f}")
        if not crypto_sales:
            results.append(total_sales_str)
        results += stock_sales_formatted
        results.append("")

    if crypto_purchases:
        crypto_purchases_sorted = sorted(
            crypto_purchases.items(), key=lambda x: x[1], reverse=True
        )
        crypto_purchases_formatted = [
            "  _*Crypto: $" + f"{sum(crypto_purchases.values()):,.2f}*_"
        ]
        for symbol, amount in crypto_purchases_sorted:
            crypto_purchases_formatted.append(f"    {symbol} | Amount: ${amount:,.2f}")
        results.append(total_purchases_str)
        results += crypto_purchases_formatted
        results.append("")

    if stock_purchases:
        stock_purchases_sorted = sorted(
            stock_purchases.items(), key=lambda x: x[1], reverse=True
        )
        stock_purchases_formatted = [
            "  _*Stocks: $" + f"{sum(stock_purchases.values()):,.2f}*_"
        ]
        for symbol, amount in stock_purchases_sorted:
            stock_purchases_formatted.append(f"    {symbol} | Amount: ${amount:,.2f}")
        if not crypto_purchases:
            results.append(total_purchases_str)
        results += stock_purchases_formatted

    # Combine the results into a formatted string
    formatted_results = "\n".join(results)

    # Return the formatted results
    return formatted_results
