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
        A jelenlegi nyitott gyertyát nem használja.
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

        if latest_close > last_swing_high["price"]:
            return {
                "bos": True,
                "direction": "BULLISH",
                "broken_level": last_swing_high["price"],
                "close": latest_close,
                "time": latest_time,
            }

        if latest_close < last_swing_low["price"]:
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

    def detect_choch(
        self,
        candles: pd.DataFrame,
        swing_length: int = 3,
    ) -> dict:
        """
        Change of Character felismerése.
        """

        default_result = {
            "choch": False,
            "direction": "NONE",
            "previous_structure": "UNKNOWN",
            "broken_level": None,
            "close": None,
            "time": None,
        }

        if candles is None or len(candles) < 30:
            return default_result

        structure_result = self.detect_market_structure(
            candles=candles,
            swing_length=swing_length,
        )

        previous_structure = structure_result["structure"]
        default_result["previous_structure"] = previous_structure

        if previous_structure not in {"BULLISH", "BEARISH"}:
            return default_result

        last_high = structure_result["last_high"]
        last_low = structure_result["last_low"]

        if last_high is None or last_low is None:
            return default_result

        latest_closed = candles.iloc[-2]

        latest_close = float(latest_closed["close"])
        latest_time = latest_closed["time"]

        if (
            previous_structure == "BEARISH"
            and latest_close > last_high["price"]
        ):
            return {
                "choch": True,
                "direction": "BULLISH",
                "previous_structure": previous_structure,
                "broken_level": last_high["price"],
                "close": latest_close,
                "time": latest_time,
            }

        if (
            previous_structure == "BULLISH"
            and latest_close < last_low["price"]
        ):
            return {
                "choch": True,
                "direction": "BEARISH",
                "previous_structure": previous_structure,
                "broken_level": last_low["price"],
                "close": latest_close,
                "time": latest_time,
            }

        return {
            "choch": False,
            "direction": "NONE",
            "previous_structure": previous_structure,
            "broken_level": None,
            "close": latest_close,
            "time": latest_time,
        }

    def detect_liquidity_sweep(
        self,
        candles: pd.DataFrame,
        swing_length: int = 3,
    ) -> dict:
        """
        Liquidity sweep felismerése az utolsó lezárt gyertyán.
        """

        default_result = {
            "sweep": False,
            "direction": "NONE",
            "swept_level": None,
            "wick_price": None,
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

        latest_high = float(latest_closed["high"])
        latest_low = float(latest_closed["low"])
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

        bullish_sweep = (
            latest_low < last_swing_low["price"]
            and latest_close > last_swing_low["price"]
        )

        bearish_sweep = (
            latest_high > last_swing_high["price"]
            and latest_close < last_swing_high["price"]
        )

        if bullish_sweep:
            return {
                "sweep": True,
                "direction": "BULLISH",
                "swept_level": last_swing_low["price"],
                "wick_price": latest_low,
                "close": latest_close,
                "time": latest_time,
            }

        if bearish_sweep:
            return {
                "sweep": True,
                "direction": "BEARISH",
                "swept_level": last_swing_high["price"],
                "wick_price": latest_high,
                "close": latest_close,
                "time": latest_time,
            }

        return {
            "sweep": False,
            "direction": "NONE",
            "swept_level": None,
            "wick_price": None,
            "close": latest_close,
            "time": latest_time,
        }

    def detect_fvg(
        self,
        candles: pd.DataFrame,
        lookback: int = 30,
    ) -> dict:
        """
        Fair Value Gap felismerése három lezárt gyertyából.
        """

        default_result = {
            "fvg": False,
            "direction": "NONE",
            "zone_low": None,
            "zone_high": None,
            "gap_size": None,
            "time": None,
            "active": False,
        }

        if candles is None or len(candles) < 5:
            return default_result

        data = candles.iloc[:-1].copy().reset_index(drop=True)

        start_index = max(2, len(data) - lookback)
        detected_gaps: list[dict] = []

        for index in range(start_index, len(data)):
            first_candle = data.iloc[index - 2]
            third_candle = data.iloc[index]

            first_high = float(first_candle["high"])
            first_low = float(first_candle["low"])
            third_high = float(third_candle["high"])
            third_low = float(third_candle["low"])

            if third_low > first_high:
                detected_gaps.append({
                    "direction": "BULLISH",
                    "zone_low": first_high,
                    "zone_high": third_low,
                    "gap_size": third_low - first_high,
                    "time": third_candle["time"],
                    "index": index,
                })

            if third_high < first_low:
                detected_gaps.append({
                    "direction": "BEARISH",
                    "zone_low": third_high,
                    "zone_high": first_low,
                    "gap_size": first_low - third_high,
                    "time": third_candle["time"],
                    "index": index,
                })

        if not detected_gaps:
            return default_result

        latest_fvg = detected_gaps[-1]

        later_candles = data.iloc[
            latest_fvg["index"] + 1:
        ]

        active = True

        if latest_fvg["direction"] == "BULLISH":
            if not later_candles.empty:
                lowest_price = float(
                    later_candles["low"].min()
                )

                if lowest_price <= latest_fvg["zone_low"]:
                    active = False

        elif latest_fvg["direction"] == "BEARISH":
            if not later_candles.empty:
                highest_price = float(
                    later_candles["high"].max()
                )

                if highest_price >= latest_fvg["zone_high"]:
                    active = False

        return {
            "fvg": True,
            "direction": latest_fvg["direction"],
            "zone_low": latest_fvg["zone_low"],
            "zone_high": latest_fvg["zone_high"],
            "gap_size": latest_fvg["gap_size"],
            "time": latest_fvg["time"],
            "active": active,
        }

    def detect_order_block(
        self,
        candles: pd.DataFrame,
        lookback: int = 40,
        impulse_candles: int = 3,
        minimum_impulse_ratio: float = 1.5,
    ) -> dict:
        """
        Order Block felismerése.

        Bullish Order Block:
        - az utolsó bearish gyertya
        - amely után erős bullish elmozdulás következett

        Bearish Order Block:
        - az utolsó bullish gyertya
        - amely után erős bearish elmozdulás következett

        A zónát a teljes gyertya high-low tartománya adja.
        """

        default_result = {
            "order_block": False,
            "direction": "NONE",
            "zone_low": None,
            "zone_high": None,
            "open": None,
            "close": None,
            "time": None,
            "active": False,
            "mitigated": False,
            "impulse_size": None,
        }

        if candles is None or len(candles) < impulse_candles + 5:
            return default_result

        data = candles.iloc[:-1].copy().reset_index(drop=True)

        start_index = max(
            0,
            len(data) - lookback,
        )

        detected_blocks: list[dict] = []

        for index in range(
            start_index,
            len(data) - impulse_candles,
        ):
            order_candle = data.iloc[index]

            candle_open = float(order_candle["open"])
            candle_close = float(order_candle["close"])
            candle_high = float(order_candle["high"])
            candle_low = float(order_candle["low"])

            candle_body = abs(candle_close - candle_open)

            if candle_body <= 0:
                continue

            future_candles = data.iloc[
                index + 1:index + 1 + impulse_candles
            ]

            future_high = float(future_candles["high"].max())
            future_low = float(future_candles["low"].min())
            future_close = float(future_candles.iloc[-1]["close"])

            is_bearish_candle = candle_close < candle_open
            is_bullish_candle = candle_close > candle_open

            bullish_impulse = future_high - candle_high
            bearish_impulse = candle_low - future_low

            bullish_order_block = (
                is_bearish_candle
                and future_close > candle_high
                and bullish_impulse >= candle_body * minimum_impulse_ratio
            )

            bearish_order_block = (
                is_bullish_candle
                and future_close < candle_low
                and bearish_impulse >= candle_body * minimum_impulse_ratio
            )

            if bullish_order_block:
                detected_blocks.append({
                    "direction": "BULLISH",
                    "zone_low": candle_low,
                    "zone_high": candle_high,
                    "open": candle_open,
                    "close": candle_close,
                    "time": order_candle["time"],
                    "index": index,
                    "impulse_size": bullish_impulse,
                })

            if bearish_order_block:
                detected_blocks.append({
                    "direction": "BEARISH",
                    "zone_low": candle_low,
                    "zone_high": candle_high,
                    "open": candle_open,
                    "close": candle_close,
                    "time": order_candle["time"],
                    "index": index,
                    "impulse_size": bearish_impulse,
                })

        if not detected_blocks:
            return default_result

        latest_order_block = detected_blocks[-1]

        candles_after_confirmation = data.iloc[
            latest_order_block["index"] + impulse_candles + 1:
        ]

        mitigated = False
        active = True

        if not candles_after_confirmation.empty:
            if latest_order_block["direction"] == "BULLISH":
                returned_to_zone = (
                    candles_after_confirmation["low"]
                    <= latest_order_block["zone_high"]
                ).any()

                invalidated = (
                    candles_after_confirmation["close"]
                    < latest_order_block["zone_low"]
                ).any()

                mitigated = bool(returned_to_zone)

                if invalidated:
                    active = False

            elif latest_order_block["direction"] == "BEARISH":
                returned_to_zone = (
                    candles_after_confirmation["high"]
                    >= latest_order_block["zone_low"]
                ).any()

                invalidated = (
                    candles_after_confirmation["close"]
                    > latest_order_block["zone_high"]
                ).any()

                mitigated = bool(returned_to_zone)

                if invalidated:
                    active = False

        return {
            "order_block": True,
            "direction": latest_order_block["direction"],
            "zone_low": latest_order_block["zone_low"],
            "zone_high": latest_order_block["zone_high"],
            "open": latest_order_block["open"],
            "close": latest_order_block["close"],
            "time": latest_order_block["time"],
            "active": active,
            "mitigated": mitigated,
            "impulse_size": latest_order_block["impulse_size"],
        }