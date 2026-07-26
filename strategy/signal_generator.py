from __future__ import annotations

from typing import Any


class SignalGenerator:
    """
    Az összes technikai elemzés eredményéből
    BUY vagy SELL pontszámot készít.
    """

    def __init__(
        self,
        minimum_score: int = 6,
        minimum_score_difference: int = 2,
    ) -> None:
        self.minimum_score = minimum_score
        self.minimum_score_difference = minimum_score_difference

    def generate_signal(
        self,
        h1_trend: str,
        m15_structure: dict[str, Any],
        bos_result: dict[str, Any],
        choch_result: dict[str, Any],
        sweep_result: dict[str, Any],
        fvg_result: dict[str, Any],
        order_block_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        BUY és SELL pontok számítása.

        Pontozás:

        H1 trend:
        +2 pont

        M15 market structure:
        +2 pont

        M15 BOS:
        +2 pont

        M15 CHoCH:
        +2 pont

        M5 Liquidity Sweep:
        +2 pont

        M5 aktív FVG:
        +1 pont

        M5 aktív Order Block:
        +2 pont
        """

        buy_score = 0
        sell_score = 0

        buy_reasons: list[str] = []
        sell_reasons: list[str] = []
        warnings: list[str] = []

        # -------------------------------------------------
        # H1 TREND
        # -------------------------------------------------

        if h1_trend == "BULLISH":
            buy_score += 2
            buy_reasons.append(
                "H1 trend bullish (+2)"
            )

        elif h1_trend == "BEARISH":
            sell_score += 2
            sell_reasons.append(
                "H1 trend bearish (+2)"
            )

        elif h1_trend == "SIDEWAYS":
            warnings.append(
                "A H1 trend oldalazó."
            )

        else:
            warnings.append(
                f"Ismeretlen H1 trend: {h1_trend}"
            )

        # -------------------------------------------------
        # M15 MARKET STRUCTURE
        # -------------------------------------------------

        structure = m15_structure.get(
            "structure",
            "UNKNOWN",
        )

        if structure == "BULLISH":
            buy_score += 2
            buy_reasons.append(
                "M15 market structure bullish (+2)"
            )

        elif structure == "BEARISH":
            sell_score += 2
            sell_reasons.append(
                "M15 market structure bearish (+2)"
            )

        elif structure == "EXPANDING":
            warnings.append(
                "Az M15 struktúra expanding, magasabb kockázat."
            )

        elif structure == "CONSOLIDATION":
            warnings.append(
                "Az M15 piac konszolidál."
            )

        elif structure == "MIXED":
            warnings.append(
                "Az M15 struktúra vegyes."
            )

        else:
            warnings.append(
                f"Nincs egyértelmű M15 struktúra: {structure}"
            )

        # -------------------------------------------------
        # M15 BOS
        # -------------------------------------------------

        if bos_result.get("bos", False):
            bos_direction = bos_result.get(
                "direction",
                "NONE",
            )

            if bos_direction == "BULLISH":
                buy_score += 2
                buy_reasons.append(
                    "Bullish BOS történt M15-ön (+2)"
                )

            elif bos_direction == "BEARISH":
                sell_score += 2
                sell_reasons.append(
                    "Bearish BOS történt M15-ön (+2)"
                )

        # -------------------------------------------------
        # M15 CHOCH
        # -------------------------------------------------

        if choch_result.get("choch", False):
            choch_direction = choch_result.get(
                "direction",
                "NONE",
            )

            if choch_direction == "BULLISH":
                buy_score += 2
                buy_reasons.append(
                    "Bullish CHoCH történt M15-ön (+2)"
                )

            elif choch_direction == "BEARISH":
                sell_score += 2
                sell_reasons.append(
                    "Bearish CHoCH történt M15-ön (+2)"
                )

        # -------------------------------------------------
        # M5 LIQUIDITY SWEEP
        # -------------------------------------------------

        if sweep_result.get("sweep", False):
            sweep_direction = sweep_result.get(
                "direction",
                "NONE",
            )

            if sweep_direction == "BULLISH":
                buy_score += 2
                buy_reasons.append(
                    "Bullish liquidity sweep történt M5-ön (+2)"
                )

            elif sweep_direction == "BEARISH":
                sell_score += 2
                sell_reasons.append(
                    "Bearish liquidity sweep történt M5-ön (+2)"
                )

        # -------------------------------------------------
        # M5 FVG
        # -------------------------------------------------

        if (
            fvg_result.get("fvg", False)
            and fvg_result.get("active", False)
        ):
            fvg_direction = fvg_result.get(
                "direction",
                "NONE",
            )

            if fvg_direction == "BULLISH":
                buy_score += 1
                buy_reasons.append(
                    "Aktív bullish FVG található M5-ön (+1)"
                )

            elif fvg_direction == "BEARISH":
                sell_score += 1
                sell_reasons.append(
                    "Aktív bearish FVG található M5-ön (+1)"
                )

        elif fvg_result.get("fvg", False):
            warnings.append(
                "A legutóbbi FVG már betöltődött."
            )

        # -------------------------------------------------
        # M5 ORDER BLOCK
        # -------------------------------------------------

        if (
            order_block_result.get("order_block", False)
            and order_block_result.get("active", False)
        ):
            order_block_direction = order_block_result.get(
                "direction",
                "NONE",
            )

            if order_block_direction == "BULLISH":
                buy_score += 2
                buy_reasons.append(
                    "Aktív bullish Order Block található M5-ön (+2)"
                )

            elif order_block_direction == "BEARISH":
                sell_score += 2
                sell_reasons.append(
                    "Aktív bearish Order Block található M5-ön (+2)"
                )

            if order_block_result.get("mitigated", False):
                warnings.append(
                    "Az Order Block már mitigált."
                )

        elif order_block_result.get("order_block", False):
            warnings.append(
                "A legutóbbi Order Block már érvénytelen."
            )

        # -------------------------------------------------
        # SIGNAL DÖNTÉS
        # -------------------------------------------------

        score_difference = abs(
            buy_score - sell_score
        )

        signal = "NO_TRADE"
        direction = "NONE"
        confidence = "LOW"

        buy_is_valid = (
            buy_score >= self.minimum_score
            and buy_score > sell_score
            and score_difference
            >= self.minimum_score_difference
        )

        sell_is_valid = (
            sell_score >= self.minimum_score
            and sell_score > buy_score
            and score_difference
            >= self.minimum_score_difference
        )

        if buy_is_valid:
            signal = "BUY_SETUP"
            direction = "BUY"

        elif sell_is_valid:
            signal = "SELL_SETUP"
            direction = "SELL"

        # -------------------------------------------------
        # CONFIDENCE
        # -------------------------------------------------

        winning_score = max(
            buy_score,
            sell_score,
        )

        if winning_score >= 10:
            confidence = "VERY_HIGH"

        elif winning_score >= 8:
            confidence = "HIGH"

        elif winning_score >= 6:
            confidence = "MEDIUM"

        else:
            confidence = "LOW"

        # -------------------------------------------------
        # KONFLIKTUS ELLENŐRZÉS
        # -------------------------------------------------

        conflict = False

        if buy_score >= self.minimum_score:
            if sell_score >= self.minimum_score:
                conflict = True

        if conflict:
            signal = "NO_TRADE"
            direction = "NONE"
            confidence = "LOW"

            warnings.append(
                "Egyszerre erős BUY és SELL jelek vannak."
            )

        if score_difference < self.minimum_score_difference:
            if winning_score >= self.minimum_score:
                warnings.append(
                    "Túl kicsi a különbség a BUY és SELL pontok között."
                )

        return {
            "signal": signal,
            "direction": direction,
            "confidence": confidence,
            "buy_score": buy_score,
            "sell_score": sell_score,
            "score_difference": score_difference,
            "minimum_score": self.minimum_score,
            "minimum_score_difference": (
                self.minimum_score_difference
            ),
            "buy_reasons": buy_reasons,
            "sell_reasons": sell_reasons,
            "warnings": warnings,
        }