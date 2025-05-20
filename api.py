from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from models import BacktestResult, PriceData
from datetime import datetime, timedelta
from backtest import ExchangeSimulator, BacktestManager
from bs import compute_rsi
from bots import SimpleBot
import requests
from models import PriceData



def get_unix_time_range(period: str):
    now = datetime.now()
    if period.endswith("d"):
        days = int(period[:-1])
        start = now - timedelta(days=days)
    elif period.endswith("mo"):
        months = int(period[:-2])
        start = now - timedelta(days=30 * months)
    elif period.endswith("y"):
        years = int(period[:-1])
        start = now - timedelta(days=365 * years)
    else:
        raise ValueError("Invalid period format")
    return int(start.timestamp()), int(now.timestamp())



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





@app.get("/backtest", response_model=BacktestResult)
def run_backtest(
    ticker: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    timeframe: str = Query("1h")
):
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        exchange = ExchangeSimulator(symbol=ticker, timeframe=timeframe)
        exchange.load_data(start_date=start, end_date=end)

        bot = SimpleBot(exchange)
        manager = BacktestManager(exchange, bot)
        manager.run()

        return BacktestResult(
            timestamps=[ts.strftime("%Y-%m-%d %H:%M") for ts in manager.timestamps],
            equity_curve=manager.equity_curve,
            trade_history=[
                {"time": t.strftime("%Y-%m-%d %H:%M"), "type": act, "price": price}
                for t, act, price in exchange.history
            ],
            final_balance=exchange.get_equity()
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@app.get("/tickers")
def get_available_tickers():
    return [
        "BTCUSDT",  # Bitcoin
        "ETHUSDT",  # Ethereum
        "SOLUSDT",  # Solana
        "DOGEUSDT", # Dogecoin
        "BNBUSDT",  # Binance Coin
        "XRPUSDT",  # Ripple
        "ADAUSDT",  # Cardano
        "DOTUSDT",  # Polkadot
        "LTCUSDT",  # Litecoin
        "LINKUSDT"  # Chainlink
    ]



@app.get("/history", response_model=PriceData)
def get_price_data(
    ticker: str = Query(...),  # Например: BTCUSDT
    interval: str = Query("60"),  # Bybit: "1", "3", "5", ..., "D", "W"
    limit: int = Query(100),
    show_sma: bool = Query(True),
    show_ema: bool = Query(False),
    show_rsi: bool = Query(False)
):
    try:
        url = "https://api.bybit.com/v5/market/kline"
        params = {
            "category": "spot",
            "symbol": ticker,
            "interval": interval,
            "limit": limit
        }
        response = requests.get(url, params=params)
        result = response.json()

        if result["retCode"] != 0 or not result["result"]["list"]:
            return {"dates": [], "prices": [], "sma": [], "ema": [], "rsi": [], "recommendation": "no data"}

        raw = result["result"]["list"]
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume", "_", "_"])
        df["Date"] = pd.to_datetime(df["timestamp"].astype(float), unit='ms')
        df["Close"] = df["close"].astype(float)

        # Индикаторы
        df["SMA"] = df["Close"].rolling(window=5).mean() if show_sma else None
        df["EMA"] = df["Close"].ewm(span=5, adjust=False).mean() if show_ema else None
        df["RSI"] = compute_rsi(df["Close"]) if show_rsi else None

        indicators = []
        if show_sma:
            indicators.append('SMA')
        if show_ema:
            indicators.append('EMA')
        if show_rsi:
            indicators.append('RSI')

        df = df.dropna(subset=indicators)

        if df.empty:
            return {"dates": [], "prices": [], "sma": [], "ema": [], "rsi": [], "recommendation": "not enough data for indicators"}

        last_price = df["Close"].iloc[-1]
        last_sma = df["SMA"].iloc[-1] if show_sma else last_price

        if last_price > last_sma:
            rec = "buy"
        elif last_price < last_sma:
            rec = "sell"
        else:
            rec = "hold"

        date_fmt = "%Y-%m-%d %H:%M" if interval.isdigit() else "%Y-%m-%d"
        return PriceData(
            dates=df["Date"].dt.strftime(date_fmt).tolist(),
            prices=df["Close"].tolist(),
            sma=df["SMA"].tolist() if show_sma else [],
            ema=df["EMA"].tolist() if show_ema else [],
            rsi=df["RSI"].tolist() if show_rsi else [],
            recommendation=rec
        )

    except Exception as e:
        print(f"ERROR: {e}")
        return {
            "dates": [], "prices": [], "sma": [], "ema": [], "rsi": [],
            "recommendation": f"error: {str(e)}"
        }