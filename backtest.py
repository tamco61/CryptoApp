from datetime import datetime, timedelta
import yfinance as yf


import requests
import pandas as pd
from datetime import datetime, timedelta

COINGECKO_IDS = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "SOL-USD": "solana",
    "DOGE-USD": "dogecoin"
}


class ExchangeSimulator:
    def __init__(self, symbol="BTC-USD", timeframe="1d", start_balance=10000):
        self.symbol = symbol
        self.timeframe = timeframe
        self.balance = start_balance
        self.position = 0
        self.entry_price = 0
        self.fee = 0.001
        self.data = None
        self.current_idx = 0
        self.history = []

    def load_data(self, start_date=None, end_date=None):
        coin_id = COINGECKO_IDS.get(self.symbol)
        if not coin_id:
            raise Exception(f"CoinGecko ID not found for symbol: {self.symbol}")

        # CoinGecko поддерживает до 90 дней minute/hourly данных, иначе — daily
        if self.timeframe != "1d":
            raise Exception("CoinGecko API supports only '1d' (daily) data for backtests.")

        # Определим количество дней
        if start_date is None or end_date is None:
            days = 90
        else:
            delta = end_date - start_date
            days = delta.days + 1

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {
            "vs_currency": "usd",
            "days": days,
            "interval": "daily"
        }

        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch data from CoinGecko: {response.status_code}")

        prices = response.json().get("prices", [])
        if not prices:
            raise Exception("No price data available.")

        df = pd.DataFrame(prices, columns=["timestamp", "close"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"] = df["close"]
        df["volume"] = 0.0  # Объёмы CoinGecko здесь не возвращает

        # Фильтрация по датам
        if start_date and end_date:
            df = df[(df["timestamp"] >= pd.to_datetime(start_date)) & (df["timestamp"] <= pd.to_datetime(end_date))]

        self.data = df[["timestamp", "open", "high", "low", "close", "volume"]].reset_index(drop=True)

    def get_current_price(self):
        return self.data.iloc[self.current_idx]["close"]

    def buy(self):
        if self.position == 0:
            price = self.get_current_price()
            self.position = self.balance * (1 - self.fee) / price
            self.balance = 0
            self.entry_price = price
            self.history.append((self.data.iloc[self.current_idx]['timestamp'], 'BUY', price))

    def sell(self):
        if self.position > 0:
            price = self.get_current_price()
            self.balance = self.position * price * (1 - self.fee)
            self.position = 0
            self.entry_price = 0
            self.history.append((self.data.iloc[self.current_idx]['timestamp'], 'SELL', price))

    def next_step(self):
        self.current_idx += 1

    def get_equity(self):
        if self.position > 0:
            return self.balance + self.position * self.get_current_price()
        else:
            return self.balance


class BacktestManager:
    def __init__(self, exchange, bot):
        self.exchange = exchange
        self.bot = bot
        self.equity_curve = []
        self.timestamps = []

    def run(self):
        while self.exchange.current_idx < len(self.exchange.data) - 1:
            self.bot.tick()
            self.equity_curve.append(self.exchange.get_equity())
            self.timestamps.append(self.exchange.data.iloc[self.exchange.current_idx]['timestamp'])
            self.exchange.next_step()