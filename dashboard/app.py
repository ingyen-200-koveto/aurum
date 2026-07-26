from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("AURUM_DATA_DIR", PROJECT_DIR / "data"))
STATE_FILE = DATA_DIR / "signal_state.json"
STATISTICS_FILE = DATA_DIR / "statistics.json"
RUNTIME_FILE = DATA_DIR / "runtime_status.json"

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


def _read_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _seconds_since(value: Any) -> float | None:
    parsed = _parse_time(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return max(0.0, (datetime.now().astimezone() - parsed).total_seconds())


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_block(source: Any) -> dict[str, Any]:
    source = source if isinstance(source, dict) else {}
    keys = (
        "signals", "settled_trades", "wins", "losses", "breakeven",
        "expired", "tp1_locked", "tp1_hits", "tp2_hits", "tp3_hits",
        "win_rate", "loss_rate", "average_rr", "profit_factor", "net_r",
        "gross_profit_r", "gross_loss_r",
    )
    result = {key: source.get(key, 0) for key in keys}
    for key in ("win_rate", "loss_rate", "average_rr", "profit_factor", "net_r", "gross_profit_r", "gross_loss_r"):
        result[key] = round(_number(result[key]), 2)
    return result


def _build_equity(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    equity = 0.0
    points: list[dict[str, Any]] = [{"index": 0, "r": 0.0, "label": "Start"}]
    for index, trade in enumerate(history, start=1):
        result = str(trade.get("result", "")).upper()
        highest_tp = int(_number(trade.get("highest_tp"), 0))
        if result == "TAKE_PROFIT_3":
            trade_r = 3.0
        elif result == "TP1_LOCKED":
            trade_r = 1.0
        elif result == "BREAKEVEN":
            trade_r = 0.0
        elif result == "STOP_LOSS":
            trade_r = -1.0
        elif highest_tp >= 2:
            trade_r = 1.0
        elif highest_tp >= 1:
            trade_r = 0.0
        else:
            trade_r = 0.0
        equity += trade_r
        points.append({
            "index": index,
            "r": round(equity, 2),
            "label": trade.get("completed_at") or trade.get("created_at") or str(index),
        })
    return points


def _build_payload() -> dict[str, Any]:
    state = _read_json(STATE_FILE, {})
    raw_statistics = _read_json(STATISTICS_FILE, {})
    runtime = _read_json(RUNTIME_FILE, {})

    state = state if isinstance(state, dict) else {}
    runtime = runtime if isinstance(runtime, dict) else {}
    raw_statistics = raw_statistics if isinstance(raw_statistics, dict) else {}

    history_raw = state.get("history", [])
    history = [item for item in history_raw if isinstance(item, dict)] if isinstance(history_raw, list) else []
    active_signal = state.get("active_signal") if isinstance(state.get("active_signal"), dict) else None

    heartbeat_age = _seconds_since(runtime.get("heartbeat_at"))
    online = bool(runtime.get("running")) and heartbeat_age is not None and heartbeat_age <= 90

    statistics = {
        "updated_at": raw_statistics.get("updated_at") or raw_statistics.get("generated_at"),
        "all_time": _normalize_block(raw_statistics.get("all_time")),
        "today": _normalize_block(raw_statistics.get("today")),
    }

    return {
        "server_time": datetime.now().astimezone().isoformat(),
        "bot": {
            "online": online,
            "running": bool(runtime.get("running")),
            "mt5_connected": bool(runtime.get("mt5_connected")),
            "heartbeat_at": runtime.get("heartbeat_at"),
            "heartbeat_age_seconds": round(heartbeat_age, 1) if heartbeat_age is not None else None,
            "started_at": runtime.get("started_at"),
            "last_error": runtime.get("last_error"),
            "symbol": runtime.get("symbol"),
            "scan_interval_seconds": runtime.get("scan_interval_seconds"),
        },
        "state": {
            "date": state.get("date"),
            "daily_signal_count": state.get("daily_signal_count", 0),
            "cooldown_until": state.get("cooldown_until"),
            "active_signal": active_signal,
            "last_completed_signal": state.get("last_completed_signal"),
        },
        "statistics": statistics,
        "history": list(reversed(history[-100:])),
        "equity": _build_equity(history[-100:]),
    }


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/api/dashboard")
def api_dashboard() -> Response:
    return jsonify(_build_payload())


@app.get("/api/history.csv")
def export_history_csv() -> Response:
    payload = _build_payload()
    history = list(reversed(payload["history"]))
    fields = [
        "id", "symbol", "direction", "status", "result", "created_at",
        "activated_at", "completed_at", "entry_low", "entry_high",
        "entry_price", "original_stop_loss", "stop_loss", "tp1", "tp2",
        "tp3", "highest_tp", "exit_price", "confidence", "buy_score",
        "sell_score", "stop_stage",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in history:
        writer.writerow(item)
    filename = f"aurum_trade_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/health")
def health() -> Response:
    return jsonify({"ok": True, "time": datetime.now().astimezone().isoformat()})


if __name__ == "__main__":
    app.run(
        host=os.getenv("AURUM_DASHBOARD_HOST", "127.0.0.1"),
        port=int(os.getenv("AURUM_DASHBOARD_PORT", "5000")),
        debug=False,
        threaded=True,
    )
