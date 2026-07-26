from config import CANDLE_COUNT, SYMBOL, TIMEFRAMES
from market_data.mt5_connector import MT5Connector
from strategy.strategy import StrategyEngine


def main() -> None:
    print("=" * 45)
    print("🚀 AURUM AI")
    print("Version: 0.6")
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
            print(
                "Utolsó lezárt gyertya: "
                f"{latest_closed['time']}"
            )
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
            market_structure = (
                strategy.detect_market_structure(
                    candles=m15_candles,
                    swing_length=3,
                )
            )

            print("\n" + "=" * 45)
            print("🏗️ M15 MARKET STRUCTURE")
            print(
                "Struktúra: "
                f"{market_structure['structure']}"
            )

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
                print(
                    f"Irány: {bos_result['direction']}"
                )
                print(
                    "Áttört szint: "
                    f"{bos_result['broken_level']}"
                )
                print(
                    "Záróár: "
                    f"{bos_result['close']}"
                )
                print(
                    "Idő: "
                    f"{bos_result['time']}"
                )

            else:
                print("BOS: NINCS")
                print(
                    "Utolsó záróár: "
                    f"{bos_result['close']}"
                )
                print(
                    "Idő: "
                    f"{bos_result['time']}"
                )

            print("=" * 45)

    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()