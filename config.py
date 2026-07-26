from __future__ import annotations

import os
from pathlib import Path

import MetaTrader5 as mt5


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


def load_env_file(
    env_file: Path,
) -> None:
    """
    Egyszerű .env fájl betöltése külső csomag nélkül.

    A már létező rendszer-környezeti változókat
    nem írja felül.
    """

    if not env_file.exists():
        return

    try:
        with env_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            for raw_line in file:
                line = raw_line.strip()

                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                if not key:
                    continue

                if (
                    len(value) >= 2
                    and value[0] == value[-1]
                    and value[0] in {'"', "'"}
                ):
                    value = value[1:-1]

                os.environ.setdefault(key, value)

    except OSError as error:
        print(
            "⚠️ Nem sikerült betölteni a .env fájlt: "
            f"{error}"
        )


def env_bool(
    name: str,
    default: bool = False,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "igen",
    }


def env_int(
    name: str,
    default: int,
) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value.strip())
    except ValueError:
        return default


load_env_file(ENV_FILE)


# -------------------------------------------------
# MARKET DATA
# -------------------------------------------------

SYMBOL = "XAUUSD"
CANDLE_COUNT = 100

TIMEFRAMES = {
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
}


# -------------------------------------------------
# JELZÉSKEZELÉS
# -------------------------------------------------

SIGNAL_EXPIRY_MINUTES = 30
COOLDOWN_MINUTES = 20
DAILY_SIGNAL_LIMIT = 6

SIGNAL_STATE_FILE = (
    BASE_DIR
    / "data"
    / "signal_state.json"
)


# -------------------------------------------------
# TELEGRAM
# -------------------------------------------------

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "",
).strip()

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID",
    "",
).strip()

TELEGRAM_ENABLED = env_bool(
    "TELEGRAM_ENABLED",
    default=True,
)

TELEGRAM_SEND_STARTUP_MESSAGE = env_bool(
    "TELEGRAM_SEND_STARTUP_MESSAGE",
    default=False,
)


# -------------------------------------------------
# CHART
# -------------------------------------------------

CHART_ENABLED = env_bool(
    "CHART_ENABLED",
    default=True,
)

CHART_CANDLE_COUNT = env_int(
    "CHART_CANDLE_COUNT",
    default=70,
)

CHART_OUTPUT_DIR = (
    BASE_DIR
    / "data"
    / "charts"
)
