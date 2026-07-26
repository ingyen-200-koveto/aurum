from __future__ import annotations

import pandas as pd


class StrategyEngine:
    def detect_trend(self, candles: pd.DataFrame) -> str:
        """
        H1 trend felismerése EMA20 és EMA50 alapján.
        Az utolsó lezárt gyertyát vizsgálja.
        """

        if candles is None or len(candles) < 50:
            return "NOT_ENOUGH_DATA"

        data = candles.copy()

        data["ema20"] = data["close"].ewm(
            span=20,
            adjust=False,
        ).mean()

        data["ema50"] = data["close"].ewm(
            span=50,
            adjust=False,
        ).mean()

        latest_closed = data.iloc[-2]

        close = float(latest_closed["close"])
        ema20 = float(latest_closed["ema20"])
        ema50 = float(latest_closed["ema50"])

        if close > ema20 > ema50:
            return "BULLISH"

        if close < ema20 < ema50:
            return "BEARISH"

        return "SIDEWAYS"

    def find_swings(
        self,
        candles: pd.DataFrame,
        swing_length: int = 3,
    ) -> dict:
        """
        Swing high és swing low pontok keresése.
        A jelenlegi, még nyitott gyertyát nem használja.
        """

        if candles is None or len(candles) < swing_length * 2 + 5:
            return {
                "highs": [],
                "lows": [],
            }

        data = candles.iloc[:-1].copy()

        swing_highs: list[dict] = []
        swing_lows: list[dict] = []

        for index in range(
            swing_length,
            len(data) - swing_length,
        ):
            current = data.iloc[index]

            current_high = float(current["high"])
            current_low = float(current["low"])

            left_highs = data.iloc[
                index - swing_length:index
            ]["high"]

            right_highs = data.iloc[
                index + 1:index + swing_length + 1
            ]["high"]

            left_lows = data.iloc[
                index - swing_length:index
            ]["low"]

            right_lows = data.iloc[
                index + 1:index + swing_length + 1
            ]["low"]

            is_swing_high = (
                current_high > float(left_highs.max())
                and current_high > float(right_highs.max())
            )

            is_swing_low = (
                current_low < float(left_lows.min())
                and current_low < float(right_lows.min())
            )

            if is_swing_high:
                swing_highs.append({
                    "index": index,
                    "time": current["time"],
                    "price": current_high,
                })

            if is_swing_low:
                swing_lows.append({
                    "index": index,
                    "time": current["time"],
                    "price": current_low,
                })

        return {
            "highs": swing_highs,
            "lows": swing_lows,
        }

    def detect_market_structure(
        self,
        candles: pd.DataFrame,
        swing_length: int = 3,
    ) -> dict:
        """
        Az utolsó két swing high és swing low alapján
        meghatározza a piaci struktúrát.
        """

        swings = self.find_swings(
            candles=candles,
            swing_length=swing_length,
        )

        swing_highs = swings["highs"]
        swing_lows = swings["lows"]

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {
                "structure": "NOT_ENOUGH_SWINGS",
                "last_high": None,
                "previous_high": None,
                "last_low": None,
                "previous_low": None,
            }

        previous_high = swing_highs[-2]
        last_high = swing_highs[-1]

        previous_low = swing_lows[-2]
        last_low = swing_lows[-1]

        higher_high = (
            last_high["price"] > previous_high["price"]
        )

        lower_high = (
            last_high["price"] < previous_high["price"]
        )

        higher_low = (
            last_low["price"] > previous_low["price"]
        )

        lower_low = (
            last_low["price"] < previous_low["price"]
        )

        if higher_high and higher_low:
            structure = "BULLISH"

        elif lower_high and lower_low:
            structure = "BEARISH"

        elif higher_high and lower_low:
            structure = "EXPANDING"

        elif lower_high and higher_low:
            structure = "CONSOLIDATION"

        else:
            structure = "MIXED"

        return {
            "structure": structure,
            "last_high": last_high,
            "previous_high": previous_high,
            "last_low": last_low,
            "previous_low": previous_low,
        }

    def detect_bos(
        self,
        candles: pd.DataFrame,
        swing_length: int = 3,
    ) -> dict:
        """
        Break of Structure felismerése.

        Bullish BOS:
        az utolsó lezárt gyertya záróára áttöri
        a legutóbbi korábbi swing high szintjét.

        Bearish BOS:
        az utolsó lezárt gyertya záróára áttöri
        a legutóbbi korábbi swing low szintjét.
        """

        default_result = {
            "bos": False,
            "direction": "NONE",
            "broken_level": None,
            "close": None,
            "time": None,
        }

        if candles is None or len(candles) < 20:
            return default_result

        swings = self.find_swings(
            candles=candles,
            swing_length=swing_length,
        )

        swing_highs = swings["highs"]
        swing_lows = swings["lows"]

        if not swing_highs or not swing_lows:
            return default_result

        latest_closed = candles.iloc[-2]

        latest_close = float(latest_closed["close"])
        latest_time = latest_closed["time"]

        latest_candle_index = len(candles) - 2

        valid_highs = [
            swing
            for swing in swing_highs
            if swing["index"] < latest_candle_index
        ]

        valid_lows = [
            swing
            for swing in swing_lows
            if swing["index"] < latest_candle_index
        ]

        if not valid_highs or not valid_lows:
            return default_result

        last_swing_high = valid_highs[-1]
        last_swing_low = valid_lows[-1]

        bullish_bos = (
            latest_close > last_swing_high["price"]
        )

        bearish_bos = (
            latest_close < last_swing_low["price"]
        )

        if bullish_bos:
            return {
                "bos": True,
                "direction": "BULLISH",
                "broken_level": last_swing_high["price"],
                "close": latest_close,
                "time": latest_time,
            }

        if bearish_bos:
            return {
                "bos": True,
                "direction": "BEARISH",
                "broken_level": last_swing_low["price"],
                "close": latest_close,
                "time": latest_time,
            }

        return {
            "bos": False,
            "direction": "NONE",
            "broken_level": None,
            "close": latest_close,
            "time": latest_time,
        }