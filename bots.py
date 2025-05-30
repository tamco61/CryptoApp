from bs import compute_rsi, compute_macd


class SmartBot:
    def __init__(self, exchange, rsi_window=14, macd_short_window=12, macd_long_window=26, macd_signal_window=9):
        self.exchange = exchange
        self.rsi_window = rsi_window
        self.macd_short_window = macd_short_window
        self.macd_long_window = macd_long_window
        self.macd_signal_window = macd_signal_window

    def tick(self):
        if self.exchange.current_idx < max(self.rsi_window, self.macd_long_window):
            return

        recent_data = self.exchange.data.iloc[self.exchange.current_idx - max(self.rsi_window, self.macd_long_window):self.exchange.current_idx]
        rsi = compute_rsi(recent_data['close'], self.rsi_window).iloc[-1]
        macd, macd_signal = compute_macd(recent_data['close'], self.macd_short_window, self.macd_long_window, self.macd_signal_window)

        if rsi < 30 and self.exchange.position == 0: 
            print(f"RSI: {rsi:.2f} - Покупка!")
            self.exchange.buy()

        elif rsi > 70 and self.exchange.position > 0: 
            print(f"RSI: {rsi:.2f} - Продажа!")
            self.exchange.sell()

        if macd.iloc[-1] > macd_signal.iloc[-1] and self.exchange.position == 0: 
            print(f"MACD: Покупка!")
            self.exchange.buy()

        elif macd.iloc[-1] < macd_signal.iloc[-1] and self.exchange.position > 0: 
            print(f"MACD: Продажа!")
            self.exchange.sell()


class SimpleBot:
    def __init__(self, exchange, ma_short=5, ma_long=20):
        self.exchange = exchange
        self.ma_short = ma_short
        self.ma_long = ma_long

    def tick(self):
        if self.exchange.current_idx < self.ma_long:
            return
        recent_data = self.exchange.data.iloc[self.exchange.current_idx - self.ma_long:self.exchange.current_idx]
        short_ma = recent_data['close'].tail(self.ma_short).mean()
        long_ma = recent_data['close'].mean()
        if short_ma > long_ma and self.exchange.position == 0:
            self.exchange.buy()
        elif short_ma < long_ma and self.exchange.position > 0:
            self.exchange.sell()


class ModernRSIVolumeBot:
    def __init__(self, exchange, rsi_period=14, rsi_buy=30, rsi_sell=70, volume_multiplier=1.5):
        self.exchange = exchange
        self.rsi_period = rsi_period
        self.rsi_buy = rsi_buy
        self.rsi_sell = rsi_sell
        self.volume_multiplier = volume_multiplier

    def compute_rsi(self, close_prices):
        delta = close_prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=self.rsi_period, min_periods=1).mean()
        avg_loss = loss.rolling(window=self.rsi_period, min_periods=1).mean()

        rs = avg_gain / (avg_loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def tick(self):
        if self.exchange.current_idx < self.rsi_period + 1:
            return

        data = self.exchange.data.iloc[:self.exchange.current_idx]
        close = data['close']
        volume = data['volume']

        rsi = self.compute_rsi(close).iloc[-1]
        recent_volume = volume.iloc[-1]
        average_volume = volume.tail(20).mean()

        volume_spike = recent_volume > average_volume * self.volume_multiplier

        if rsi < self.rsi_buy and volume_spike and self.exchange.position == 0:
            self.exchange.buy()

        elif rsi > self.rsi_sell and self.exchange.position > 0:
            self.exchange.sell()