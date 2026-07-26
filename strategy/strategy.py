from __future__ import annotations

import pandas as pd


class StrategyEngine:
    def detect_trend(self, candles: pd.DataFrame) -> str:
        """
        Egyszerű trendfelismerés EMA20 és EMA50 alapján.
        """

        if candles is None or len(candles) < 50:
            return "NOT_ENOUGH_DATA"

        data = candles.copy()

        data["ema20"] = data["close"].ewm(span=20, adjust=False).mean()
        data["ema50"] = data["close"].ewm(span=50, adjust=False).mean()

        latest = data.iloc[-2]

        ema20 = latest["ema20"]
        ema50 = latest["ema50"]
        close = latest["close"]

        if close > ema20 > ema50:
            return "BULLISH"

        if close < ema20 < ema50:
            return "BEARISH"

        return "SIDEWAYS"