from config import CANDLE_COUNT, SYMBOL, TIMEFRAMES
from market_data.mt5_connector import MT5Connector


def main() -> None:
    print("=" * 40)
    print("🚀 AURUM AI")
    print("Version: 0.3")
    print("=" * 40)

    connector = MT5Connector(symbol=SYMBOL)

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

        for name, timeframe in TIMEFRAMES.items():
            candles = connector.get_candles(
                timeframe=timeframe,
                count=CANDLE_COUNT,
            )

            if candles is None:
                continue

            latest = candles.iloc[-1]

            print(f"\n📊 {name} – {len(candles)} gyertya lekérve")
            print(f"Idő:   {latest['time']}")
            print(f"Open:  {latest['open']}")
            print(f"High:  {latest['high']}")
            print(f"Low:   {latest['low']}")
            print(f"Close: {latest['close']}")

    finally:
        connector.disconnect()


if __name__ == "__main__":
    main()