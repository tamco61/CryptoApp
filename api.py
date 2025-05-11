from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from models import BacktestResult, PriceData
from datetime import datetime
from backtest import ExchangeSimulator, BacktestManager
import yfinance as yf
from bs import compute_rsi
from bots import SimpleBot


app = FastAPI()

# Разрешаем доступ с фронтенда
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
        "AAPL", "MSFT", "GOOGL", "TSLA", "AMZN",
        "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"
    ]



@app.get("/history", response_model=PriceData)
def get_price_data(
    ticker: str = Query(...),
    period: str = Query("1mo"),
    interval: str = Query("1d"),
    show_sma: bool = Query(True),
    show_ema: bool = Query(False),
    show_rsi: bool = Query(False)
):
    try:
        data = yf.download(ticker, period=period, interval=interval)

        if data.empty:
            return {"dates": [], "prices": [], "sma": [], "ema": [], "rsi": [], "recommendation": "no data"}

        # Упрощаем мультииндексированные колонки, если они есть
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]

        data = data.reset_index()

        data['SMA'] = data['Close'].rolling(window=5).mean() if show_sma else None
        data['EMA'] = data['Close'].ewm(span=5, adjust=False).mean() if show_ema else None
        data['RSI'] = compute_rsi(data['Close']) if show_rsi else None

        indicators = []
        if show_sma:
            indicators.append('SMA')
        if show_ema:
            indicators.append('EMA')
        if show_rsi:
            indicators.append('RSI')

        # Удаляем строки с NaN в выбранных индикаторах
        data = data.dropna(subset=indicators)

        if data.empty:
            return {"dates": [], "prices": [], "sma": [], "ema": [], "rsi": [], "recommendation": "not enough data for indicators"}

        last_price = data['Close'].iloc[-1]
        last_sma = data['SMA'].iloc[-1] if show_sma else last_price

        if last_price > last_sma:
            rec = "buy"
        elif last_price < last_sma:
            rec = "sell"
        else:
            rec = "hold"

        return PriceData(
            dates=data['Date'].dt.strftime("%Y-%m-%d %H:%M").tolist() if interval in ["1m", "2m", "5m", "15m", "30m", "60m", "90m"] else data['Date'].dt.strftime("%Y-%m-%d").tolist(),
            prices=data['Close'].tolist(),
            sma=data['SMA'].tolist() if show_sma else [],
            ema=data['EMA'].tolist() if show_ema else [],
            rsi=data['RSI'].tolist() if show_rsi else [],
            recommendation=rec
        )
    except Exception as e:
        print(f"ERROR: {e}")
        return {"dates": [], "prices": [], "sma": [], "ema": [], "rsi": [], "recommendation": f"error: {str(e)}"}

