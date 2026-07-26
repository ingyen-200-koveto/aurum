from config import CANDLE_COUNT, SYMBOL, TIMEFRAMES
from market_data.mt5_connector import MT5Connector
from strategy.strategy import StrategyEngine


def print_separator() -> None:
    print("=" * 50)


def main() -> None:
    print_separator()
    print("🚀 AURUM AI")
    print("Version: 1.0")
    print_separator()

    connector = MT5Connector(symbol=SYMBOL)
    strategy = StrategyEngine()

    if not connector.connect():
        return

    try:
        tick = connector.get_tick()

        if tick is not None:
            spread = round(tick.ask - tick.bid, 2)

            print(f"\n💰 {SYMBOL}")
            print(f"Ask: {tick.ask}")
            print(f"Bid: {tick.bid}")
            print(f"Spread: {spread}")

        candle_data = {}

        for name, timeframe in TIMEFRAMES.items():
            candles = connector.get_candles(
                timeframe=timeframe,
                count=CANDLE_COUNT,
            )

            if candles is None:
                continue

            if len(candles) < 2:
                print(f"❌ Nincs elég gyertya: {name}")
                continue

            candle_data[name] = candles

            latest_closed = candles.iloc[-2]

            print(f"\n📊 {name} – {len(candles)} gyertya lekérve")
            print(f"Utolsó lezárt gyertya: {latest_closed['time']}")
            print(f"Open:  {latest_closed['open']}")
            print(f"High:  {latest_closed['high']}")
            print(f"Low:   {latest_closed['low']}")
            print(f"Close: {latest_closed['close']}")

        h1_candles = candle_data.get("H1")

        if h1_candles is not None:
            trend = strategy.detect_trend(h1_candles)

            print()
            print_separator()
            print("📈 H1 TREND")
            print(f"Trend: {trend}")
            print_separator()

        m15_candles = candle_data.get("M15")

        if m15_candles is not None:
            market_structure = strategy.detect_market_structure(
                candles=m15_candles,
                swing_length=3,
            )

            print()
            print_separator()
            print("🏗️ M15 MARKET STRUCTURE")
            print(f"Struktúra: {market_structure['structure']}")
            print_separator()

            bos_result = strategy.detect_bos(
                candles=m15_candles,
                swing_length=3,
            )

            print()
            print_separator()
            print("💥 M15 BREAK OF STRUCTURE")

            if bos_result["bos"]:
                print("BOS: IGEN ✅")
                print(f"Irány: {bos_result['direction']}")
                print(f"Áttört szint: {bos_result['broken_level']}")
                print(f"Záróár: {bos_result['close']}")
                print(f"Idő: {bos_result['time']}")
            else:
                print("BOS: NINCS")
                print(f"Utolsó záróár: {bos_result['close']}")
                print(f"Idő: {bos_result['time']}")

            print_separator()

            choch_result = strategy.detect_choch(
                candles=m15_candles,
                swing_length=3,
            )

            print()
            print_separator()
            print("🔄 M15 CHANGE OF CHARACTER")
            print(
                f"Korábbi struktúra: "
                f"{choch_result['previous_structure']}"
            )

            if choch_result["choch"]:
                print("CHoCH: IGEN ✅")
                print(f"Új irány: {choch_result['direction']}")
                print(f"Áttört szint: {choch_result['broken_level']}")
                print(f"Záróár: {choch_result['close']}")
                print(f"Idő: {choch_result['time']}")
            else:
                print("CHoCH: NINCS")
                print(f"Utolsó záróár: {choch_result['close']}")
                print(f"Idő: {choch_result['time']}")

            print_separator()

        m5_candles = candle_data.get("M5")

        if m5_candles is not None:
            sweep_result = strategy.detect_liquidity_sweep(
                candles=m5_candles,
                swing_length=3,
            )

            print()
            print_separator()
            print("💧 M5 LIQUIDITY SWEEP")

            if sweep_result["sweep"]:
                print("Liquidity sweep: IGEN ✅")
                print(f"Irány: {sweep_result['direction']}")
                print(f"Kisöpört szint: {sweep_result['swept_level']}")
                print(f"Kanóc széle: {sweep_result['wick_price']}")
                print(f"Záróár: {sweep_result['close']}")
                print(f"Idő: {sweep_result['time']}")
            else:
                print("Liquidity sweep: NINCS")
                print(f"Utolsó záróár: {sweep_result['close']}")
                print(f"Idő: {sweep_result['time']}")

            print_separator()

            fvg_result = strategy.detect_fvg(
                candles=m5_candles,
                lookback=30,
            )

            print()
            print_separator()
            print("⚡ M5 FAIR VALUE GAP")

            if fvg_result["fvg"]:
                print("FVG: TALÁLHATÓ ✅")
                print(f"Irány: {fvg_result['direction']}")
                print(
                    f"FVG zóna: "
                    f"{fvg_result['zone_low']} - "
                    f"{fvg_result['zone_high']}"
                )
                print(
                    f"FVG mérete: "
                    f"{round(fvg_result['gap_size'], 2)}"
                )
                print(f"Létrejött: {fvg_result['time']}")

                if fvg_result["active"]:
                    print("Állapot: AKTÍV ✅")
                else:
                    print("Állapot: BETÖLTÖTT ❌")
            else:
                print("FVG: NEM TALÁLHATÓ")

            print_separator()

            order_block_result = strategy.detect_order_block(
                candles=m5_candles,
                lookback=40,
                impulse_candles=3,
                minimum_impulse_ratio=1.5,
            )

            print()
            print_separator()
            print("🧱 M5 ORDER BLOCK")

            if order_block_result["order_block"]:
                print("Order Block: TALÁLHATÓ ✅")
                print(f"Irány: {order_block_result['direction']}")
                print(
                    f"OB zóna: "
                    f"{order_block_result['zone_low']} - "
                    f"{order_block_result['zone_high']}"
                )
                print(f"Gyertya open: {order_block_result['open']}")
                print(f"Gyertya close: {order_block_result['close']}")
                print(
                    f"Impulzus mérete: "
                    f"{round(order_block_result['impulse_size'], 2)}"
                )
                print(f"Létrejött: {order_block_result['time']}")

                if order_block_result["active"]:
                    print("Állapot: AKTÍV ✅")
                else:
                    print("Állapot: ÉRVÉNYTELEN ❌")

                if order_block_result["mitigated"]:
                    print("Mitigáció: AZ ÁR MÁR VISSZATÉRT A ZÓNÁBA")
                else:
                    print("Mitigáció: AZ ÁR MÉG NEM TÉRT VISSZA")
            else:
                print("Order Block: NEM TALÁLHATÓ")

            print_separator()

    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()