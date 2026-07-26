from __future__ import annotations

import MetaTrader5 as mt5
import pandas as pd


class MT5Connector:
    def __init__(self, symbol: str = "XAUUSD") -> None:
        self.symbol = symbol
        self.connected = False

    def connect(self) -> bool:
        """Kapcsolódás a MetaTrader 5 terminálhoz."""
        if not mt5.initialize():
            print("❌ Nem sikerült csatlakozni az MT5-höz.")
            print(f"MT5 hiba: {mt5.last_error()}")
            return False

        self.connected = True
        print("✅ Sikeres kapcsolat az MT5-höz.")

        if not mt5.symbol_select(self.symbol, True):
            print(f"❌ Nem sikerült aktiválni a szimbólumot: {self.symbol}")
            print(f"MT5 hiba: {mt5.last_error()}")
            self.disconnect()
            return False

        return True

    def disconnect(self) -> None:
        """MT5 kapcsolat lezárása."""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            print("🔌 MT5 kapcsolat lezárva.")

    def get_tick(self):
        """Aktuális Bid és Ask ár lekérése."""
        tick = mt5.symbol_info_tick(self.symbol)

        if tick is None:
            print(f"❌ Nem érhető el az aktuális ár: {self.symbol}")
            print(f"MT5 hiba: {mt5.last_error()}")
            return None

        return tick

    def get_candles(self, timeframe: int, count: int = 100) -> pd.DataFrame | None:
        """Gyertyaadatok lekérése DataFrame formátumban."""
        rates = mt5.copy_rates_from_pos(
            self.symbol,
            timeframe,
            0,
            count,
        )

        if rates is None or len(rates) == 0:
            print(f"❌ Nem sikerült lekérni a gyertyákat: {self.symbol}")
            print(f"MT5 hiba: {mt5.last_error()}")
            return None

        candles = pd.DataFrame(rates)
        candles["time"] = pd.to_datetime(candles["time"], unit="s")

        return candles