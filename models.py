from pydantic import BaseModel
from typing import List


class BacktestResult(BaseModel):
    timestamps: List[str]
    equity_curve: List[float]
    trade_history: List[dict]
    final_balance: float


class PriceData(BaseModel):
    dates: List[str]
    prices: List[float]
    sma: List[float]
    ema: List[float]
    rsi: List[float]
    recommendation: str
