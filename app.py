from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("AURUM_DATA_DIR", BASE_DIR / "data"))
STATE_FILE = DATA_DIR / "signal_state.json"
STATISTICS_FILE = DATA_DIR / "statistics.json"

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


def _read_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _file_age_seconds(path: Path) -> float | None:
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
        return max(0.0, (datetime.now().astimezone() - modified).total_seconds())
    except OSError:
        return None


def _normalize_statistics(raw: dict[str, Any]) -> dict[str, Any]:
    all_time = raw.get("all_time") if isinstance(raw.get("all_time"), dict) else {}
    today = raw.get("today") if isinstance(raw.get("today"), dict) else {}

    defaults = {
        "signals": 0,
        "wins": 0,
        "losses": 0,
        "breakeven": 0,
        "tp1_locked": 0,
        "tp1_hits": 0,
        "tp2_hits": 0,
        "tp3_hits": 0,
        "win_rate": 0.0,
        "average_rr": 0.0,
        "net_r": 0.0,
        "profit_factor": 0.0,
    }

    def merge(source: dict[str, Any]) -> dict[str, Any]:
        result = dict(defaults)
        result.update(source)
        return result

    return {
        "generated_at": raw.get("generated_at"),
        "all_time": merge(all_time),
        "today": merge(today),
    }


def _build_payload() -> dict[str, Any]:
    state = _read_json(STATE_FILE, {})
    statistics = _normalize_statistics(_read_json(STATISTICS_FILE, {}))
    history = state.get("history", []) if isinstance(state, dict) else []
    if not isinstance(history, list):
        history = []

    active_signal = state.get("active_signal") if isinstance(state, dict) else None
    age = _file_age_seconds(STATE_FILE)
    online = age is not None and age <= 120

    latest_completed = state.get("last_completed_signal") if isinstance(state, dict) else None
    last_activity = None
    if isinstance(active_signal, dict):
        last_activity = active_signal.get("activated_at") or active_signal.get("created_at")
    elif isinstance(latest_completed, dict):
        last_activity = latest_completed.get("completed_at") or latest_completed.get("created_at")

    return {
        "server_time": datetime.now().astimezone().isoformat(),
        "bot": {
            "online": online,
            "state_file_age_seconds": round(age, 1) if age is not None else None,
            "last_activity": last_activity,
            "mt5_status": "CONNECTED" if online else "UNKNOWN",
        },
        "state": {
            "date": state.get("date") if isinstance(state, dict) else None,
            "daily_signal_count": state.get("daily_signal_count", 0) if isinstance(state, dict) else 0,
            "cooldown_until": state.get("cooldown_until") if isinstance(state, dict) else None,
            "active_signal": active_signal,
            "last_completed_signal": latest_completed,
        },
        "statistics": statistics,
        "history": list(reversed(history[-100:])),
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
        "activated_at", "completed_at", "entry_price", "original_stop_loss",
        "stop_loss", "tp1", "tp2", "tp3", "highest_tp", "exit_price",
        "confidence", "buy_score", "sell_score", "stop_stage",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in history:
        if isinstance(item, dict):
            writer.writerow(item)

    filename = f"aurum_trade_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/health")
def health() -> Response:
    return jsonify({"ok": True, "time": datetime.now().astimezone().isoformat()})


if __name__ == "__main__":
    host = os.getenv("AURUM_DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("AURUM_DASHBOARD_PORT", "5000"))
    app.run(host=host, port=port, debug=False, threaded=True)
