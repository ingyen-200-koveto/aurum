from config import CANDLE_COUNT, SYMBOL, TIMEFRAMES
from market_data.mt5_connector import MT5Connector
from strategy.strategy import StrategyEngine


def main() -> None:
    print("=" * 40)
    print("🚀 AURUM AI")
    print("Version: 0.4")
    print("=" * 40)

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

            print("\n" + "=" * 40)
            print("📈 H1 TREND ELEMZÉS")
            print(f"Trend: {trend}")
            print("=" * 40)

    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()