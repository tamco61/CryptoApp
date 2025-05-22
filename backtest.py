import requests
import pandas as pd
import time


class ExchangeSimulator:
    def __init__(self, symbol="BTCUSDT", timeframe="1d", start_balance=10000):
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
        interval_map = {
            "1m": "1",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "1d": "D"
        }

        if self.timeframe not in interval_map:
            raise Exception(f"Unsupported timeframe: {self.timeframe}")

        interval = interval_map[self.timeframe]

        start_ts = int(pd.Timestamp(start_date).timestamp() * 1000)
        end_ts = int(pd.Timestamp(end_date).timestamp() * 1000)
        all_data = []

        while start_ts < end_ts:
            url = "https://api.bybit.com/v5/market/kline"
            params = {
                "category": "linear",
                "symbol": self.symbol,
                "interval": interval,
                "start": start_ts,
                "limit": 200
            }

            res = requests.get(url, params=params)
            if res.status_code != 200:
                raise Exception(f"Bybit API error: {res.status_code} {res.text}")

            data = res.json().get("result", {}).get("list", [])
            if not data:
                break

            data.reverse()

            df = pd.DataFrame(data, columns=[
                "timestamp", "open", "high", "low", "close", "volume","turnover"
            ])
            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
            df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
            all_data.append(df[["timestamp", "open", "high", "low", "close", "volume"]])

            # Обновляем стартовый таймштамп для следующей итерации
            last_ts = int(data[-1][0])
            if last_ts == start_ts:
                break  # защита от бесконечного цикла, если API возвращает одинаковые данные
            start_ts = last_ts + 1

            # Пауза для соблюдения лимитов
            time.sleep(5)

        if not all_data:
            raise Exception("No data fetched from Bybit.")

        self.data = pd.concat(all_data).reset_index(drop=True)
        self.data = self.data[self.data["timestamp"] <= pd.to_datetime(end_date)]

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
