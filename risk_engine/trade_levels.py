from __future__ import annotations

from typing import Any

import pandas as pd


class TradeLevelCalculator:
    """
    Belépési zóna, Stop Loss és Take Profit szintek számítása.
    """

    def __init__(
        self,
        risk_reward_tp1: float = 1.0,
        risk_reward_tp2: float = 2.0,
        risk_reward_tp3: float = 3.0,
        stop_buffer: float = 0.50,
        fallback_stop_distance: float = 3.00,
    ) -> None:
        self.risk_reward_tp1 = risk_reward_tp1
        self.risk_reward_tp2 = risk_reward_tp2
        self.risk_reward_tp3 = risk_reward_tp3
        self.stop_buffer = stop_buffer
        self.fallback_stop_distance = fallback_stop_distance

    def calculate_levels(
        self,
        signal_result: dict[str, Any],
        candles: pd.DataFrame,
        fvg_result: dict[str, Any],
        order_block_result: dict[str, Any],
        sweep_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        A jel iránya alapján meghatározza:

        - entry_low
        - entry_high
        - entry_price
        - stop_loss
        - TP1
        - TP2
        - TP3
        """

        default_result = {
            "valid": False,
            "direction": "NONE",
            "entry_low": None,
            "entry_high": None,
            "entry_price": None,
            "stop_loss": None,
            "tp1": None,
            "tp2": None,
            "tp3": None,
            "risk_distance": None,
            "entry_source": "NONE",
            "stop_source": "NONE",
            "reason": "Nincs érvényes kereskedési jel.",
        }

        if candles is None or len(candles) < 10:
            default_result["reason"] = "Nincs elég M5 gyertya."
            return default_result

        signal = signal_result.get(
            "signal",
            "NO_TRADE",
        )

        direction = signal_result.get(
            "direction",
            "NONE",
        )

        if signal not in {
            "BUY_SETUP",
            "SELL_SETUP",
        }:
            return default_result

        if direction not in {
            "BUY",
            "SELL",
        }:
            return default_result

        data = candles.iloc[:-1].copy()

        latest_closed = data.iloc[-1]
        latest_close = float(
            latest_closed["close"]
        )

        entry_low: float
        entry_high: float
        entry_source: str

        entry_zone = self._select_entry_zone(
            direction=direction,
            fvg_result=fvg_result,
            order_block_result=order_block_result,
            fallback_price=latest_close,
        )

        entry_low = entry_zone["entry_low"]
        entry_high = entry_zone["entry_high"]
        entry_source = entry_zone["source"]

        entry_price = (
            entry_low + entry_high
        ) / 2

        stop_result = self._calculate_stop_loss(
            direction=direction,
            entry_price=entry_price,
            entry_low=entry_low,
            entry_high=entry_high,
            candles=data,
            sweep_result=sweep_result,
            order_block_result=order_block_result,
        )

        stop_loss = stop_result["stop_loss"]
        stop_source = stop_result["source"]

        if direction == "BUY":
            risk_distance = (
                entry_price - stop_loss
            )

        else:
            risk_distance = (
                stop_loss - entry_price
            )

        if risk_distance <= 0:
            return {
                **default_result,
                "reason": (
                    "Érvénytelen Stop Loss távolság."
                ),
            }

        if direction == "BUY":
            tp1 = (
                entry_price
                + risk_distance
                * self.risk_reward_tp1
            )

            tp2 = (
                entry_price
                + risk_distance
                * self.risk_reward_tp2
            )

            tp3 = (
                entry_price
                + risk_distance
                * self.risk_reward_tp3
            )

        else:
            tp1 = (
                entry_price
                - risk_distance
                * self.risk_reward_tp1
            )

            tp2 = (
                entry_price
                - risk_distance
                * self.risk_reward_tp2
            )

            tp3 = (
                entry_price
                - risk_distance
                * self.risk_reward_tp3
            )

        return {
            "valid": True,
            "direction": direction,
            "entry_low": round(entry_low, 2),
            "entry_high": round(entry_high, 2),
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "tp1": round(tp1, 2),
            "tp2": round(tp2, 2),
            "tp3": round(tp3, 2),
            "risk_distance": round(
                risk_distance,
                2,
            ),
            "entry_source": entry_source,
            "stop_source": stop_source,
            "reason": "A kereskedési szintek elkészültek.",
        }

    def _select_entry_zone(
        self,
        direction: str,
        fvg_result: dict[str, Any],
        order_block_result: dict[str, Any],
        fallback_price: float,
    ) -> dict[str, Any]:
        """
        Elsődlegesen az Order Block és FVG közös metszetét keresi.

        Sorrend:

        1. Order Block és FVG átfedés
        2. Aktív Order Block
        3. Aktív FVG
        4. Aktuális záróár körüli tartomány
        """

        expected_direction = (
            "BULLISH"
            if direction == "BUY"
            else "BEARISH"
        )

        valid_order_block = (
            order_block_result.get(
                "order_block",
                False,
            )
            and order_block_result.get(
                "active",
                False,
            )
            and order_block_result.get(
                "direction"
            ) == expected_direction
            and order_block_result.get(
                "zone_low"
            ) is not None
            and order_block_result.get(
                "zone_high"
            ) is not None
        )

        valid_fvg = (
            fvg_result.get(
                "fvg",
                False,
            )
            and fvg_result.get(
                "active",
                False,
            )
            and fvg_result.get(
                "direction"
            ) == expected_direction
            and fvg_result.get(
                "zone_low"
            ) is not None
            and fvg_result.get(
                "zone_high"
            ) is not None
        )

        if valid_order_block and valid_fvg:
            order_low = float(
                order_block_result["zone_low"]
            )

            order_high = float(
                order_block_result["zone_high"]
            )

            fvg_low = float(
                fvg_result["zone_low"]
            )

            fvg_high = float(
                fvg_result["zone_high"]
            )

            overlap_low = max(
                order_low,
                fvg_low,
            )

            overlap_high = min(
                order_high,
                fvg_high,
            )

            if overlap_low <= overlap_high:
                return {
                    "entry_low": overlap_low,
                    "entry_high": overlap_high,
                    "source": "FVG + ORDER_BLOCK",
                }

        if valid_order_block:
            return {
                "entry_low": float(
                    order_block_result["zone_low"]
                ),
                "entry_high": float(
                    order_block_result["zone_high"]
                ),
                "source": "ORDER_BLOCK",
            }

        if valid_fvg:
            return {
                "entry_low": float(
                    fvg_result["zone_low"]
                ),
                "entry_high": float(
                    fvg_result["zone_high"]
                ),
                "source": "FVG",
            }

        fallback_half_width = 0.25

        return {
            "entry_low": (
                fallback_price
                - fallback_half_width
            ),
            "entry_high": (
                fallback_price
                + fallback_half_width
            ),
            "source": "CURRENT_PRICE",
        }

    def _calculate_stop_loss(
        self,
        direction: str,
        entry_price: float,
        entry_low: float,
        entry_high: float,
        candles: pd.DataFrame,
        sweep_result: dict[str, Any],
        order_block_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Stop Loss prioritás:

        1. Liquidity sweep kanóc
        2. Order Block széle
        3. Legutóbbi 10 gyertya szélsőértéke
        4. Fix tartalék távolság
        """

        if direction == "BUY":
            stop_candidates: list[
                tuple[float, str]
            ] = []

            if (
                sweep_result.get("sweep", False)
                and sweep_result.get(
                    "direction"
                ) == "BULLISH"
                and sweep_result.get(
                    "wick_price"
                ) is not None
            ):
                sweep_stop = (
                    float(
                        sweep_result["wick_price"]
                    )
                    - self.stop_buffer
                )

                stop_candidates.append((
                    sweep_stop,
                    "LIQUIDITY_SWEEP",
                ))

            if (
                order_block_result.get(
                    "order_block",
                    False,
                )
                and order_block_result.get(
                    "direction"
                ) == "BULLISH"
                and order_block_result.get(
                    "zone_low"
                ) is not None
            ):
                order_block_stop = (
                    float(
                        order_block_result[
                            "zone_low"
                        ]
                    )
                    - self.stop_buffer
                )

                stop_candidates.append((
                    order_block_stop,
                    "ORDER_BLOCK",
                ))

            recent_low = float(
                candles.tail(10)["low"].min()
            ) - self.stop_buffer

            stop_candidates.append((
                recent_low,
                "RECENT_SWING_LOW",
            ))

            valid_candidates = [
                candidate
                for candidate in stop_candidates
                if candidate[0] < entry_price
            ]

            if valid_candidates:
                selected = min(
                    valid_candidates,
                    key=lambda item: item[0],
                )

                return {
                    "stop_loss": selected[0],
                    "source": selected[1],
                }

            return {
                "stop_loss": (
                    entry_low
                    - self.fallback_stop_distance
                ),
                "source": "FALLBACK_DISTANCE",
            }

        stop_candidates = []

        if (
            sweep_result.get("sweep", False)
            and sweep_result.get(
                "direction"
            ) == "BEARISH"
            and sweep_result.get(
                "wick_price"
            ) is not None
        ):
            sweep_stop = (
                float(
                    sweep_result["wick_price"]
                )
                + self.stop_buffer
            )

            stop_candidates.append((
                sweep_stop,
                "LIQUIDITY_SWEEP",
            ))

        if (
            order_block_result.get(
                "order_block",
                False,
            )
            and order_block_result.get(
                "direction"
            ) == "BEARISH"
            and order_block_result.get(
                "zone_high"
            ) is not None
        ):
            order_block_stop = (
                float(
                    order_block_result[
                        "zone_high"
                    ]
                )
                + self.stop_buffer
            )

            stop_candidates.append((
                order_block_stop,
                "ORDER_BLOCK",
            ))

        recent_high = float(
            candles.tail(10)["high"].max()
        ) + self.stop_buffer

        stop_candidates.append((
            recent_high,
            "RECENT_SWING_HIGH",
        ))

        valid_candidates = [
            candidate
            for candidate in stop_candidates
            if candidate[0] > entry_price
        ]

        if valid_candidates:
            selected = max(
                valid_candidates,
                key=lambda item: item[0],
            )

            return {
                "stop_loss": selected[0],
                "source": selected[1],
            }

        return {
            "stop_loss": (
                entry_high
                + self.fallback_stop_distance
            ),
            "source": "FALLBACK_DISTANCE",
        }