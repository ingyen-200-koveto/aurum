from config import CANDLE_COUNT, SYMBOL, TIMEFRAMES
from market_data.mt5_connector import MT5Connector
from strategy.strategy import StrategyEngine


def main() -> None:
    print("=" * 45)
    print("🚀 AURUM AI")
    print("Version: 0.8")
    print("=" * 45)

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

            print("\n" + "=" * 45)
            print("📈 H1 TREND ELEMZÉS")
            print(f"Trend: {trend}")
            print("=" * 45)

        m15_candles = candle_data.get("M15")

        if m15_candles is not None:
            market_structure = strategy.detect_market_structure(
                candles=m15_candles,
                swing_length=3,
            )

            print("\n" + "=" * 45)
            print("🏗️ M15 MARKET STRUCTURE")
            print(f"Struktúra: {market_structure['structure']}")

            if market_structure["last_high"] is not None:
                print(
                    "Utolsó swing high: "
                    f"{market_structure['last_high']['price']} "
                    f"({market_structure['last_high']['time']})"
                )

                print(
                    "Előző swing high: "
                    f"{market_structure['previous_high']['price']} "
                    f"({market_structure['previous_high']['time']})"
                )

                print(
                    "Utolsó swing low: "
                    f"{market_structure['last_low']['price']} "
                    f"({market_structure['last_low']['time']})"
                )

                print(
                    "Előző swing low: "
                    f"{market_structure['previous_low']['price']} "
                    f"({market_structure['previous_low']['time']})"
                )

            print("=" * 45)

            bos_result = strategy.detect_bos(
                candles=m15_candles,
                swing_length=3,
            )

            print("\n" + "=" * 45)
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

            print("=" * 45)

            choch_result = strategy.detect_choch(
                candles=m15_candles,
                swing_length=3,
            )

            print("\n" + "=" * 45)
            print("🔄 M15 CHANGE OF CHARACTER")
            print(
                "Korábbi struktúra: "
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

            print("=" * 45)

        m5_candles = candle_data.get("M5")

        if m5_candles is not None:
            sweep_result = strategy.detect_liquidity_sweep(
                candles=m5_candles,
                swing_length=3,
            )

            print("\n" + "=" * 45)
            print("💧 M5 LIQUIDITY SWEEP")

            if sweep_result["sweep"]:
                print("Liquidity sweep: IGEN ✅")
                print(f"Irány: {sweep_result['direction']}")
                print(
                    "Kisöpört szint: "
                    f"{sweep_result['swept_level']}"
                )
                print(
                    "Kanóc széle: "
                    f"{sweep_result['wick_price']}"
                )
                print(f"Záróár: {sweep_result['close']}")
                print(f"Idő: {sweep_result['time']}")
            else:
                print("Liquidity sweep: NINCS")
                print(f"Utolsó záróár: {sweep_result['close']}")
                print(f"Idő: {sweep_result['time']}")

            print("=" * 45)

    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()