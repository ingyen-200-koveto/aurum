from __future__ import annotations

from typing import Any

from config import CANDLE_COUNT, SYMBOL, TIMEFRAMES
from market_data.mt5_connector import MT5Connector
from risk_engine.trade_levels import TradeLevelCalculator
from strategy.signal_generator import SignalGenerator
from strategy.strategy import StrategyEngine


def print_separator() -> None:
    print("=" * 58)


def print_reasons(
    title: str,
    reasons: list[str],
) -> None:
    print(f"\n{title}")

    if not reasons:
        print("- Nincs pontot adó feltétel.")
        return

    for reason in reasons:
        print(f"- {reason}")


def empty_structure_result() -> dict[str, Any]:
    return {
        "structure": "UNKNOWN",
        "last_high": None,
        "previous_high": None,
        "last_low": None,
        "previous_low": None,
    }


def empty_bos_result() -> dict[str, Any]:
    return {
        "bos": False,
        "direction": "NONE",
        "broken_level": None,
        "close": None,
        "time": None,
    }


def empty_choch_result() -> dict[str, Any]:
    return {
        "choch": False,
        "direction": "NONE",
        "previous_structure": "UNKNOWN",
        "broken_level": None,
        "close": None,
        "time": None,
    }


def empty_sweep_result() -> dict[str, Any]:
    return {
        "sweep": False,
        "direction": "NONE",
        "swept_level": None,
        "wick_price": None,
        "close": None,
        "time": None,
    }


def empty_fvg_result() -> dict[str, Any]:
    return {
        "fvg": False,
        "direction": "NONE",
        "zone_low": None,
        "zone_high": None,
        "gap_size": None,
        "time": None,
        "active": False,
    }


def empty_order_block_result() -> dict[str, Any]:
    return {
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


def main() -> None:
    print_separator()
    print("🚀 AURUM AI")
    print("Version: 1.2")
    print("Signal + Entry + SL + TP rendszer")
    print_separator()

    connector = MT5Connector(
        symbol=SYMBOL,
    )

    strategy = StrategyEngine()

    signal_generator = SignalGenerator(
        minimum_score=6,
        minimum_score_difference=2,
    )

    level_calculator = TradeLevelCalculator(
        risk_reward_tp1=1.0,
        risk_reward_tp2=2.0,
        risk_reward_tp3=3.0,
        stop_buffer=0.50,
        fallback_stop_distance=3.00,
    )

    if not connector.connect():
        print(
            "❌ Nem sikerült csatlakozni az MT5-höz."
        )
        return

    try:
        tick = connector.get_tick()

        if tick is not None:
            spread = round(
                tick.ask - tick.bid,
                2,
            )

            print(f"\n💰 {SYMBOL}")
            print(f"Ask: {tick.ask}")
            print(f"Bid: {tick.bid}")
            print(f"Spread: {spread}")

        candle_data: dict[str, Any] = {}

        for name, timeframe in TIMEFRAMES.items():
            candles = connector.get_candles(
                timeframe=timeframe,
                count=CANDLE_COUNT,
            )

            if candles is None:
                print(
                    f"❌ Nem sikerült lekérni: {name}"
                )
                continue

            if len(candles) < 2:
                print(
                    f"❌ Nincs elég gyertya: {name}"
                )
                continue

            candle_data[name] = candles

            latest_closed = candles.iloc[-2]

            print(
                f"\n📊 {name}: "
                f"{len(candles)} gyertya"
            )

            print(
                "Utolsó lezárt gyertya: "
                f"{latest_closed['time']}"
            )

            print(
                "OHLC: "
                f"{latest_closed['open']} / "
                f"{latest_closed['high']} / "
                f"{latest_closed['low']} / "
                f"{latest_closed['close']}"
            )

        h1_trend = "UNKNOWN"

        market_structure = (
            empty_structure_result()
        )

        bos_result = empty_bos_result()
        choch_result = empty_choch_result()
        sweep_result = empty_sweep_result()
        fvg_result = empty_fvg_result()

        order_block_result = (
            empty_order_block_result()
        )

        h1_candles = candle_data.get("H1")
        m15_candles = candle_data.get("M15")
        m5_candles = candle_data.get("M5")

        if h1_candles is not None:
            h1_trend = strategy.detect_trend(
                h1_candles
            )

        if m15_candles is not None:
            market_structure = (
                strategy.detect_market_structure(
                    candles=m15_candles,
                    swing_length=3,
                )
            )

            bos_result = strategy.detect_bos(
                candles=m15_candles,
                swing_length=3,
            )

            choch_result = strategy.detect_choch(
                candles=m15_candles,
                swing_length=3,
            )

        if m5_candles is not None:
            sweep_result = (
                strategy.detect_liquidity_sweep(
                    candles=m5_candles,
                    swing_length=3,
                )
            )

            fvg_result = strategy.detect_fvg(
                candles=m5_candles,
                lookback=30,
            )

            order_block_result = (
                strategy.detect_order_block(
                    candles=m5_candles,
                    lookback=40,
                    impulse_candles=3,
                    minimum_impulse_ratio=1.5,
                )
            )

        print()
        print_separator()
        print("📈 PIACI ELEMZÉS")
        print_separator()

        print(f"H1 trend: {h1_trend}")

        print(
            "M15 struktúra: "
            f"{market_structure['structure']}"
        )

        if bos_result["bos"]:
            print(
                "M15 BOS: "
                f"{bos_result['direction']} ✅"
            )
        else:
            print("M15 BOS: NINCS")

        if choch_result["choch"]:
            print(
                "M15 CHoCH: "
                f"{choch_result['direction']} ✅"
            )
        else:
            print("M15 CHoCH: NINCS")

        if sweep_result["sweep"]:
            print(
                "M5 Sweep: "
                f"{sweep_result['direction']} ✅"
            )
        else:
            print("M5 Sweep: NINCS")

        if fvg_result["fvg"]:
            fvg_status = (
                "AKTÍV"
                if fvg_result["active"]
                else "BETÖLTÖTT"
            )

            print(
                "M5 FVG: "
                f"{fvg_result['direction']} "
                f"({fvg_status})"
            )
        else:
            print("M5 FVG: NINCS")

        if order_block_result["order_block"]:
            order_block_status = (
                "AKTÍV"
                if order_block_result["active"]
                else "ÉRVÉNYTELEN"
            )

            print(
                "M5 Order Block: "
                f"{order_block_result['direction']} "
                f"({order_block_status})"
            )
        else:
            print("M5 Order Block: NINCS")

        signal_result = (
            signal_generator.generate_signal(
                h1_trend=h1_trend,
                m15_structure=market_structure,
                bos_result=bos_result,
                choch_result=choch_result,
                sweep_result=sweep_result,
                fvg_result=fvg_result,
                order_block_result=(
                    order_block_result
                ),
            )
        )

        print()
        print_separator()
        print("🏆 AURUM SIGNAL ENGINE")
        print_separator()

        print(
            "BUY pontszám: "
            f"{signal_result['buy_score']}"
        )

        print(
            "SELL pontszám: "
            f"{signal_result['sell_score']}"
        )

        print(
            "Pontkülönbség: "
            f"{signal_result['score_difference']}"
        )

        print_reasons(
            title="🟢 BUY indokok:",
            reasons=signal_result[
                "buy_reasons"
            ],
        )

        print_reasons(
            title="🔴 SELL indokok:",
            reasons=signal_result[
                "sell_reasons"
            ],
        )

        if signal_result["warnings"]:
            print("\n⚠️ Figyelmeztetések:")

            for warning in signal_result[
                "warnings"
            ]:
                print(f"- {warning}")

        print()
        print_separator()

        signal = signal_result["signal"]

        if signal == "BUY_SETUP":
            print("🟢 EREDMÉNY: BUY SETUP ✅")

        elif signal == "SELL_SETUP":
            print("🔴 EREDMÉNY: SELL SETUP ✅")

        else:
            print("⚪ EREDMÉNY: NO TRADE")

        print(
            "Bizalom: "
            f"{signal_result['confidence']}"
        )

        print_separator()

        if m5_candles is None:
            print()
            print_separator()
            print("❌ Nincs M5 adat a szintekhez.")
            print_separator()
            return

        trade_levels = (
            level_calculator.calculate_levels(
                signal_result=signal_result,
                candles=m5_candles,
                fvg_result=fvg_result,
                order_block_result=(
                    order_block_result
                ),
                sweep_result=sweep_result,
            )
        )

        print()
        print_separator()
        print("🎯 AURUM TRADE LEVELS")
        print_separator()

        if not trade_levels["valid"]:
            print("⚪ NINCS AKTÍV KERESKEDÉSI TERV")
            print(
                f"Ok: {trade_levels['reason']}"
            )

            print_separator()
            return

        direction = trade_levels["direction"]

        if direction == "BUY":
            print(f"🏆 {SYMBOL}")
            print()
            print(
                "🟢 BUY: "
                f"{trade_levels['entry_low']} - "
                f"{trade_levels['entry_high']}"
            )

        else:
            print(f"🏆 {SYMBOL}")
            print()
            print(
                "🔴 SELL: "
                f"{trade_levels['entry_low']} - "
                f"{trade_levels['entry_high']}"
            )

        print()
        print(
            f"🛑 SL: "
            f"{trade_levels['stop_loss']}"
        )

        print()
        print(
            f"🎯 TP1: "
            f"{trade_levels['tp1']}"
        )

        print(
            f"🎯 TP2: "
            f"{trade_levels['tp2']}"
        )

        print(
            f"🎯 TP3: "
            f"{trade_levels['tp3']}"
        )

        print()
        print(
            "Belépési középár: "
            f"{trade_levels['entry_price']}"
        )

        print(
            "Kockázati távolság: "
            f"{trade_levels['risk_distance']}"
        )

        print(
            "Belépési forrás: "
            f"{trade_levels['entry_source']}"
        )

        print(
            "Stop Loss forrás: "
            f"{trade_levels['stop_source']}"
        )

        print_separator()

    except Exception as error:
        print()
        print_separator()
        print("❌ HIBA TÖRTÉNT")
        print(
            f"Hiba típusa: "
            f"{type(error).__name__}"
        )
        print(f"Hiba: {error}")
        print_separator()

    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()