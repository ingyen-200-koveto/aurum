import MetaTrader5 as mt5


SYMBOL = "XAUUSD"
CANDLE_COUNT = 100

TIMEFRAMES = {
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
}