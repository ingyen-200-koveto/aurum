from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from chart_engine.chart_generator import ChartGenerator
from config import (
    CANDLE_COUNT,
    CHART_CANDLE_COUNT,
    CHART_ENABLED,
    CHART_OUTPUT_DIR,
    COOLDOWN_MINUTES,
    DAILY_SIGNAL_LIMIT,
    SIGNAL_EXPIRY_MINUTES,
    SIGNAL_STATE_FILE,
    SYMBOL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_ENABLED,
    TELEGRAM_SEND_STARTUP_MESSAGE,
    TIMEFRAMES,
)
from market_data.mt5_connector import MT5Connector
from risk_engine.trade_levels import TradeLevelCalculator
from signal_manager.manager import SignalManager
from strategy.signal_generator import SignalGenerator
from strategy.strategy import StrategyEngine
from telegram_bot.telegram_notifier import TelegramNotifier


SCAN_INTERVAL_SECONDS = 30
RUNTIME_STATUS_FILE = Path("data/runtime_status.json")


def write_runtime_status(
    *,
    running: bool,
    mt5_connected: bool,
    started_at: str | None,
    last_error: str | None = None,
) -> None:
    """Atomikusan frissíti a dashboard heartbeat állományát."""
    now = datetime.now().astimezone().isoformat()
    payload = {
        "running": bool(running),
        "mt5_connected": bool(mt5_connected),
        "started_at": started_at,
        "heartbeat_at": now,
        "last_error": last_error,
        "symbol": SYMBOL,
        "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
    }
    RUNTIME_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = RUNTIME_STATUS_FILE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    temporary.replace(RUNTIME_STATUS_FILE)



def print_separator() -> None:
    print("=" * 62)


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


def print_telegram_result(
    result: dict[str, Any],
    success_message: str,
) -> None:
    if result.get("success", False):
        print(f"✅ {success_message}")

        message_id = result.get("message_id")

        if message_id is not None:
            print(f"Telegram message ID: {message_id}")

        message_type = result.get("message_type")

        if message_type:
            print(f"Telegram üzenettípus: {message_type}")

        return

    print("⚠️ Telegram üzenet nem ment el.")
    print(f"Hibakód: {result.get('code', 'UNKNOWN')}")
    print(f"Ok: {result.get('reason', 'Ismeretlen hiba')}")


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


def print_telegram_status(
    telegram: TelegramNotifier,
) -> None:
    print()
    print_separator()
    print("📨 TELEGRAM")
    print_separator()

    if not telegram.enabled:
        print("Telegram küldés: KIKAPCSOLVA")
    elif telegram.is_configured():
        print("Telegram küldés: BEKAPCSOLVA ✅")
        print("Token: BEÁLLÍTVA")
        print("Chat ID: BEÁLLÍTVA")
    else:
        print("Telegram küldés: NINCS BEÁLLÍTVA ❌")
        print(
            "Ellenőrizd a projekt gyökerében "
            "található .env fájlt."
        )

    print_separator()


def print_manager_status(
    signal_manager: SignalManager,
) -> None:
    status = signal_manager.get_status_summary()

    print()
    print_separator()
    print("🧠 SIGNAL MANAGER")
    print_separator()
    print(
        "Napi jelzések: "
        f"{status['daily_signal_count']} / "
        f"{status['max_signals_per_day']}"
    )
    print(
        "Hátralévő napi jelzések: "
        f"{status['remaining_daily_signals']}"
    )

    active_signal = status.get("active_signal")

    if isinstance(active_signal, dict):
        print(
            "Aktív jelzés: "
            f"{active_signal.get('symbol')} "
            f"{active_signal.get('direction')}"
        )
        print(f"Állapot: {active_signal.get('status')}")
        print(f"Lejárat: {active_signal.get('expires_at')}")
        print(
            "Aktuális SL: "
            f"{active_signal.get('stop_loss')}"
        )
        print(
            "SL állapot: "
            f"{active_signal.get('stop_stage')}"
        )
    else:
        print("Aktív jelzés: NINCS")

    cooldown_until = status.get("cooldown_until")

    if cooldown_until:
        print(f"Cooldown vége: {cooldown_until}")
    else:
        print("Cooldown: NINCS")

    print(
        "Új jelzés létrehozható: "
        f"{status['can_create_signal']}"
    )
    print(f"Állapot: {status['create_signal_reason']}")
    print_separator()



def print_statistics_panel(
    signal_manager: SignalManager,
) -> None:
    statistics = signal_manager.get_statistics_summary()
    all_time = statistics["all_time"]
    today = statistics["today"]

    print()
    print_separator()
    print("📊 AURUM STATISTICS")
    print_separator()
    print(
        f"Összes jelzés: {all_time['signals']} | "
        f"Mai jelzés: {today['signals']}"
    )
    print(
        f"Nyerő: {all_time['wins']} | "
        f"Vesztes: {all_time['losses']} | "
        f"Breakeven: {all_time['breakeven']}"
    )
    print(
        f"TP1: {all_time['tp1_hits']} | "
        f"TP2: {all_time['tp2_hits']} | "
        f"TP3: {all_time['tp3_hits']}"
    )
    print(f"Win rate: {all_time['win_rate']:.2f}%")
    print(f"Átlagos R: {all_time['average_rr']:.2f}R")
    print(f"Nettó R: {all_time['net_r']:.2f}R")
    print(f"Profit factor: {all_time['profit_factor']:.2f}")
    print_separator()


def send_pending_daily_report(
    signal_manager: SignalManager,
    telegram: TelegramNotifier,
) -> None:
    pending = signal_manager.get_pending_daily_report()

    if pending is None:
        return

    report_date = str(pending["date"])
    result = telegram.send_statistics_report(
        statistics=pending["statistics"],
        title="AURUM DAILY REPORT",
        report_date=report_date,
    )

    if result.get("success", False):
        signal_manager.mark_daily_report_sent(report_date)
        print(f"✅ Napi Telegram riport elküldve: {report_date}")
    else:
        print("⚠️ A napi Telegram riport nem ment el.")
        print(f"Ok: {result.get('reason', 'Ismeretlen hiba')}")


def send_manager_events(
    events: list[dict[str, Any]],
    telegram: TelegramNotifier,
    signal_manager: SignalManager,
) -> None:
    terminal_event = False

    for event in events:
        event_type = event.get("type", "UNKNOWN")
        if event_type in {"TP3", "STOPPED", "EXPIRED"}:
            terminal_event = True
        signal = event.get("signal")

        print()
        print_separator()
        print(f"📣 SIGNAL ESEMÉNY: {event_type}")
        print(event.get("message", ""))
        print_separator()

        if not isinstance(signal, dict):
            continue

        result = telegram.update_signal_message(signal)

        print_telegram_result(
            result=result,
            success_message=(
                "Az eredeti Telegram-jelzés frissítve."
            ),
        )

    if terminal_event:
        print_statistics_panel(signal_manager)


def fetch_candle_data(
    connector: MT5Connector,
) -> dict[str, Any]:
    candle_data: dict[str, Any] = {}

    for name, timeframe in TIMEFRAMES.items():
        candles = connector.get_candles(
            timeframe=timeframe,
            count=CANDLE_COUNT,
        )

        if candles is None:
            print(f"❌ Nem sikerült lekérni: {name}")
            continue

        if len(candles) < 2:
            print(f"❌ Nincs elég gyertya: {name}")
            continue

        candle_data[name] = candles

    return candle_data


def analyze_market(
    strategy: StrategyEngine,
    candle_data: dict[str, Any],
) -> dict[str, Any]:
    h1_trend = "UNKNOWN"
    market_structure = empty_structure_result()
    bos_result = empty_bos_result()
    choch_result = empty_choch_result()
    sweep_result = empty_sweep_result()
    fvg_result = empty_fvg_result()
    order_block_result = empty_order_block_result()

    h1_candles = candle_data.get("H1")
    m15_candles = candle_data.get("M15")
    m5_candles = candle_data.get("M5")

    if h1_candles is not None:
        h1_trend = strategy.detect_trend(h1_candles)

    if m15_candles is not None:
        market_structure = strategy.detect_market_structure(
            candles=m15_candles,
            swing_length=3,
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
        sweep_result = strategy.detect_liquidity_sweep(
            candles=m5_candles,
            swing_length=3,
        )
        fvg_result = strategy.detect_fvg(
            candles=m5_candles,
            lookback=30,
        )
        order_block_result = strategy.detect_order_block(
            candles=m5_candles,
            lookback=40,
            impulse_candles=3,
            minimum_impulse_ratio=1.5,
        )

    return {
        "h1_trend": h1_trend,
        "market_structure": market_structure,
        "bos_result": bos_result,
        "choch_result": choch_result,
        "sweep_result": sweep_result,
        "fvg_result": fvg_result,
        "order_block_result": order_block_result,
        "m5_candles": m5_candles,
    }


def print_analysis(
    analysis: dict[str, Any],
    signal_result: dict[str, Any],
) -> None:
    print()
    print_separator()
    print("📈 PIACI ELEMZÉS")
    print_separator()

    print(f"H1 trend: {analysis['h1_trend']}")
    print(
        "M15 struktúra: "
        f"{analysis['market_structure'].get('structure', 'UNKNOWN')}"
    )

    bos = analysis["bos_result"]

    print(
        "M15 BOS: "
        + (
            f"{bos['direction']} ✅"
            if bos.get("bos")
            else "NINCS"
        )
    )

    choch = analysis["choch_result"]

    print(
        "M15 CHoCH: "
        + (
            f"{choch['direction']} ✅"
            if choch.get("choch")
            else "NINCS"
        )
    )

    sweep = analysis["sweep_result"]

    print(
        "M5 Sweep: "
        + (
            f"{sweep['direction']} ✅"
            if sweep.get("sweep")
            else "NINCS"
        )
    )

    fvg = analysis["fvg_result"]

    if fvg.get("fvg"):
        fvg_status = (
            "AKTÍV"
            if fvg.get("active")
            else "BETÖLTÖTT"
        )

        print(
            f"M5 FVG: {fvg.get('direction')} "
            f"({fvg_status})"
        )
    else:
        print("M5 FVG: NINCS")

    order_block = analysis["order_block_result"]

    if order_block.get("order_block"):
        ob_status = (
            "AKTÍV"
            if order_block.get("active")
            else "ÉRVÉNYTELEN"
        )

        print(
            "M5 Order Block: "
            f"{order_block.get('direction')} "
            f"({ob_status})"
        )
    else:
        print("M5 Order Block: NINCS")

    print()
    print(
        f"BUY pontszám: "
        f"{signal_result.get('buy_score', 0)}"
    )
    print(
        f"SELL pontszám: "
        f"{signal_result.get('sell_score', 0)}"
    )
    print(
        "Pontkülönbség: "
        f"{signal_result.get('score_difference', 0)}"
    )

    print_reasons(
        "🟢 BUY indokok:",
        signal_result.get("buy_reasons", []),
    )
    print_reasons(
        "🔴 SELL indokok:",
        signal_result.get("sell_reasons", []),
    )

    warnings = signal_result.get("warnings", [])

    if warnings:
        print("\n⚠️ Figyelmeztetések:")

        for warning in warnings:
            print(f"- {warning}")

    print()
    print(
        f"Eredmény: "
        f"{signal_result.get('signal', 'NO_TRADE')}"
    )
    print(
        f"Bizalom: "
        f"{signal_result.get('confidence', 'UNKNOWN')}"
    )
    print_separator()


def scan_market(
    connector: MT5Connector,
    strategy: StrategyEngine,
    signal_generator: SignalGenerator,
    level_calculator: TradeLevelCalculator,
    signal_manager: SignalManager,
    telegram: TelegramNotifier,
    chart_generator: ChartGenerator,
) -> None:
    tick = connector.get_tick()

    if tick is None:
        print("❌ Nem érkezett aktuális ár az MT5-ből.")
        return

    bid = float(tick.bid)
    ask = float(tick.ask)

    print()
    print_separator()
    print("🔎 ÚJ PIACI ELLENŐRZÉS")
    print(f"Bid: {bid}")
    print(f"Ask: {ask}")
    print(f"Spread: {round(ask - bid, 2)}")
    print_separator()

    events = signal_manager.update_active_signal(
        bid=bid,
        ask=ask,
    )

    if events:
        send_manager_events(
            events=events,
            telegram=telegram,
            signal_manager=signal_manager,
        )

    active_signal = signal_manager.get_active_signal()

    if active_signal is not None:
        print(
            "📡 Aktív jelzés: "
            f"{active_signal['symbol']} "
            f"{active_signal['direction']} "
            f"({active_signal['status']})"
        )
        print(
            "🛡️ Aktuális SL: "
            f"{active_signal['stop_loss']} "
            f"({active_signal.get('stop_stage', 'ORIGINAL')})"
        )
        return

    allowed, reason = signal_manager.can_create_signal()

    if not allowed:
        print(
            f"⏸️ Új jelzés nem hozható létre: {reason}"
        )
        return

    candle_data = fetch_candle_data(connector)

    if not candle_data:
        print("❌ Nem érkezett gyertyaadat.")
        return

    analysis = analyze_market(
        strategy=strategy,
        candle_data=candle_data,
    )

    signal_result = signal_generator.generate_signal(
        h1_trend=analysis["h1_trend"],
        m15_structure=analysis["market_structure"],
        bos_result=analysis["bos_result"],
        choch_result=analysis["choch_result"],
        sweep_result=analysis["sweep_result"],
        fvg_result=analysis["fvg_result"],
        order_block_result=analysis["order_block_result"],
    )

    print_analysis(
        analysis=analysis,
        signal_result=signal_result,
    )

    if signal_result.get("signal") not in {
        "BUY_SETUP",
        "SELL_SETUP",
    }:
        print("⚪ Jelenleg nincs megfelelő setup.")
        return

    m5_candles = analysis["m5_candles"]

    if m5_candles is None:
        print(
            "❌ Nincs M5 adat a kereskedési szintekhez."
        )
        return

    trade_levels = level_calculator.calculate_levels(
        signal_result=signal_result,
        candles=m5_candles,
        fvg_result=analysis["fvg_result"],
        order_block_result=analysis["order_block_result"],
        sweep_result=analysis["sweep_result"],
    )

    if not trade_levels.get("valid", False):
        print(
            "❌ Nem hozható létre kereskedési terv."
        )
        print(
            f"Ok: "
            f"{trade_levels.get('reason', 'Ismeretlen ok')}"
        )
        return

    new_signal = signal_manager.create_signal(
        symbol=SYMBOL,
        signal_result=signal_result,
        trade_levels=trade_levels,
    )

    if new_signal is None:
        print(
            "❌ A Signal Manager nem engedte "
            "létrehozni a jelzést."
        )
        return

    print()
    print_separator()
    print("🏆 ÚJ AURUM JELZÉS")
    print_separator()
    print(
        f"{new_signal['direction']}: "
        f"{new_signal['entry_low']} - "
        f"{new_signal['entry_high']}"
    )
    print(f"SL: {new_signal['stop_loss']}")
    print(f"TP1: {new_signal['tp1']}")
    print(f"TP2: {new_signal['tp2']}")
    print(f"TP3: {new_signal['tp3']}")
    print(f"Lejárat: {new_signal['expires_at']}")
    print_separator()

    chart_result = chart_generator.create_signal_chart(
        candles=m5_candles,
        signal=new_signal,
    )

    chart_path = None

    if chart_result.get("success", False):
        chart_path = chart_result.get("path")
        print(f"✅ Chart elkészült: {chart_path}")
    else:
        print("⚠️ A chart nem készült el.")
        print(
            f"Ok: "
            f"{chart_result.get('reason', 'Ismeretlen hiba')}"
        )

    telegram_result = telegram.send_new_signal(
        signal=new_signal,
        chart_path=chart_path,
    )

    print_telegram_result(
        result=telegram_result,
        success_message=(
            "Az új jelzés elküldve Telegramra."
        ),
    )

    message_id = telegram_result.get("message_id")
    message_type = telegram_result.get(
        "message_type",
        "text",
    )

    if (
        telegram_result.get("success", False)
        and message_id is not None
    ):
        saved = signal_manager.set_telegram_message(
            signal_id=new_signal["id"],
            message_id=int(message_id),
            message_type=str(message_type),
            chart_path=chart_path,
        )

        if saved:
            print(
                "✅ Telegram-adatok eltárolva: "
                f"{message_id} ({message_type})"
            )
        else:
            print(
                "⚠️ A Telegram-adatok mentése "
                "nem sikerült."
            )


def main() -> None:
    print_separator()
    print("🚀 AURUM AI")
    print("Version: 2.0")
    print("Statistics Engine + Daily Report")
    print_separator()

    connector = MT5Connector(symbol=SYMBOL)
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

    signal_manager = SignalManager(
        state_file=str(SIGNAL_STATE_FILE),
        max_signals_per_day=DAILY_SIGNAL_LIMIT,
        cooldown_minutes=COOLDOWN_MINUTES,
        expiration_minutes=SIGNAL_EXPIRY_MINUTES,
    )

    telegram = TelegramNotifier(
        bot_token=TELEGRAM_BOT_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        enabled=TELEGRAM_ENABLED,
    )

    chart_generator = ChartGenerator(
        output_dir=CHART_OUTPUT_DIR,
        candle_count=CHART_CANDLE_COUNT,
        enabled=CHART_ENABLED,
    )

    print_telegram_status(telegram)
    print_manager_status(signal_manager)
    print_statistics_panel(signal_manager)

    print()
    print_separator()
    print("🛡️ KOCKÁZATKEZELÉS")
    print_separator()
    print("TP1 után: SL → ENTRY (BREAKEVEN)")
    print("TP2 után: SL → TP1 (PROFIT LOCK)")
    print_separator()

    if (
        TELEGRAM_SEND_STARTUP_MESSAGE
        and telegram.enabled
        and telegram.is_configured()
    ):
        startup_result = telegram.send_startup_message(
            symbol=SYMBOL
        )

        print_telegram_result(
            result=startup_result,
            success_message=(
                "Az indulási értesítés elküldve."
            ),
        )

    started_at = datetime.now().astimezone().isoformat()

    if not connector.connect():
        write_runtime_status(
            running=False,
            mt5_connected=False,
            started_at=started_at,
            last_error="Nem sikerült csatlakozni az MT5-höz.",
        )
        print("❌ Nem sikerült csatlakozni az MT5-höz.")
        return

    write_runtime_status(
        running=True,
        mt5_connected=True,
        started_at=started_at,
    )

    print()
    print("✅ AURUM elindult. Leállítás: Ctrl + C")

    try:
        while True:
            write_runtime_status(
                running=True,
                mt5_connected=True,
                started_at=started_at,
            )
            try:
                send_pending_daily_report(
                    signal_manager=signal_manager,
                    telegram=telegram,
                )
                scan_market(
                    connector=connector,
                    strategy=strategy,
                    signal_generator=signal_generator,
                    level_calculator=level_calculator,
                    signal_manager=signal_manager,
                    telegram=telegram,
                    chart_generator=chart_generator,
                )
            except Exception as error:
                print()
                print_separator()
                print("❌ ELLENŐRZÉSI HIBA")
                print(
                    f"Hiba típusa: "
                    f"{type(error).__name__}"
                )
                print(f"Hiba: {error}")
                print_separator()
                write_runtime_status(
                    running=True,
                    mt5_connected=True,
                    started_at=started_at,
                    last_error=f"{type(error).__name__}: {error}",
                )

            time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print()
        print_separator()
        print("🛑 AURUM LEÁLLÍTVA")
        print_separator()

    finally:
        write_runtime_status(
            running=False,
            mt5_connected=False,
            started_at=started_at,
        )
        connector.disconnect()


if __name__ == "__main__":
    main()
