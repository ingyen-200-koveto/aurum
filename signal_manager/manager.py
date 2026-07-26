from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any


class SignalManager:
    """
    AURUM jelzésállapot-kezelő.

    Feladatai:

    - egyszerre csak egy aktív jelzés
    - napi maximális jelzésszám
    - cooldown
    - belépési jelzés lejárata
    - entry, TP és SL figyelése
    - állapot mentése JSON-fájlba
    """

    ACTIVE_STATUSES = {
        "WAITING",
        "ACTIVE",
        "TP1",
        "TP2",
    }

    TERMINAL_STATUSES = {
        "TP3",
        "STOPPED",
        "EXPIRED",
    }

    def __init__(
        self,
        state_file: str = "database/signal_state.json",
        max_signals_per_day: int = 6,
        cooldown_minutes: int = 30,
        expiration_minutes: int = 180,
    ) -> None:
        self.state_file = state_file
        self.max_signals_per_day = max_signals_per_day
        self.cooldown_minutes = cooldown_minutes
        self.expiration_minutes = expiration_minutes

        self._ensure_state_directory()
        self.state = self._load_state()
        self._reset_daily_counter_if_needed()
        self._save_state()

    def _ensure_state_directory(self) -> None:
        directory = os.path.dirname(self.state_file)

        if directory:
            os.makedirs(
                directory,
                exist_ok=True,
            )

    def _default_state(self) -> dict[str, Any]:
        now = self._now()

        return {
            "date": now.date().isoformat(),
            "daily_signal_count": 0,
            "active_signal": None,
            "cooldown_until": None,
            "last_completed_signal": None,
            "history": [],
        }

    def _load_state(self) -> dict[str, Any]:
        if not os.path.exists(self.state_file):
            return self._default_state()

        try:
            with open(
                self.state_file,
                "r",
                encoding="utf-8",
            ) as file:
                loaded_state = json.load(file)

            default_state = self._default_state()

            for key, value in default_state.items():
                if key not in loaded_state:
                    loaded_state[key] = value

            return loaded_state

        except (
            json.JSONDecodeError,
            OSError,
            TypeError,
        ):
            return self._default_state()

    def _save_state(self) -> None:
        temporary_file = f"{self.state_file}.tmp"

        with open(
            temporary_file,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                self.state,
                file,
                ensure_ascii=False,
                indent=4,
            )

        os.replace(
            temporary_file,
            self.state_file,
        )

    def _now(self) -> datetime:
        return datetime.now().astimezone()

    def _parse_datetime(
        self,
        value: str | None,
    ) -> datetime | None:
        if not value:
            return None

        try:
            return datetime.fromisoformat(value)

        except ValueError:
            return None

    def _reset_daily_counter_if_needed(
        self,
        now: datetime | None = None,
    ) -> None:
        current_time = now or self._now()
        current_date = current_time.date().isoformat()

        if self.state.get("date") != current_date:
            self.state["date"] = current_date
            self.state["daily_signal_count"] = 0

    def has_active_signal(self) -> bool:
        signal = self.state.get("active_signal")

        if signal is None:
            return False

        return signal.get("status") in self.ACTIVE_STATUSES

    def get_active_signal(
        self,
    ) -> dict[str, Any] | None:
        signal = self.state.get("active_signal")

        if signal is None:
            return None

        return deepcopy(signal)

    def get_daily_signal_count(self) -> int:
        self._reset_daily_counter_if_needed()

        return int(
            self.state.get(
                "daily_signal_count",
                0,
            )
        )

    def get_remaining_daily_signals(self) -> int:
        used_signals = self.get_daily_signal_count()

        return max(
            0,
            self.max_signals_per_day - used_signals,
        )

    def get_cooldown_until(
        self,
    ) -> datetime | None:
        return self._parse_datetime(
            self.state.get("cooldown_until")
        )

    def can_create_signal(
        self,
        now: datetime | None = None,
    ) -> tuple[bool, str]:
        current_time = now or self._now()

        self._reset_daily_counter_if_needed(
            current_time
        )

        if self.has_active_signal():
            return (
                False,
                "Már van aktív vagy belépésre váró jelzés.",
            )

        daily_count = int(
            self.state.get(
                "daily_signal_count",
                0,
            )
        )

        if daily_count >= self.max_signals_per_day:
            return (
                False,
                "Elérte a napi maximális jelzésszámot.",
            )

        cooldown_until = self.get_cooldown_until()

        if (
            cooldown_until is not None
            and current_time < cooldown_until
        ):
            remaining_seconds = int(
                (
                    cooldown_until
                    - current_time
                ).total_seconds()
            )

            remaining_minutes = max(
                1,
                (
                    remaining_seconds + 59
                ) // 60,
            )

            return (
                False,
                (
                    "Cooldown aktív. "
                    f"Még körülbelül {remaining_minutes} perc."
                ),
            )

        return (
            True,
            "Új jelzés létrehozható.",
        )

    def create_signal(
        self,
        symbol: str,
        signal_result: dict[str, Any],
        trade_levels: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        current_time = now or self._now()

        allowed, _ = self.can_create_signal(
            current_time
        )

        if not allowed:
            return None

        if not trade_levels.get("valid", False):
            return None

        direction = trade_levels.get(
            "direction",
            "NONE",
        )

        if direction not in {"BUY", "SELL"}:
            return None

        created_at = current_time
        expires_at = (
            created_at
            + timedelta(
                minutes=self.expiration_minutes
            )
        )

        signal_id = (
            f"{created_at.strftime('%Y%m%d-%H%M%S')}"
            f"-{direction}"
        )

        active_signal = {
            "id": signal_id,
            "symbol": symbol,
            "direction": direction,
            "status": "WAITING",
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "activated_at": None,
            "completed_at": None,
            "entry_low": float(
                trade_levels["entry_low"]
            ),
            "entry_high": float(
                trade_levels["entry_high"]
            ),
            "entry_price": float(
                trade_levels["entry_price"]
            ),
            "stop_loss": float(
                trade_levels["stop_loss"]
            ),
            "tp1": float(
                trade_levels["tp1"]
            ),
            "tp2": float(
                trade_levels["tp2"]
            ),
            "tp3": float(
                trade_levels["tp3"]
            ),
            "entry_source": trade_levels.get(
                "entry_source",
                "UNKNOWN",
            ),
            "stop_source": trade_levels.get(
                "stop_source",
                "UNKNOWN",
            ),
            "risk_distance": float(
                trade_levels["risk_distance"]
            ),
            "buy_score": int(
                signal_result.get(
                    "buy_score",
                    0,
                )
            ),
            "sell_score": int(
                signal_result.get(
                    "sell_score",
                    0,
                )
            ),
            "confidence": signal_result.get(
                "confidence",
                "UNKNOWN",
            ),
            "highest_tp": 0,
            "last_bid": None,
            "last_ask": None,
            "exit_price": None,
            "result": None,
        }

        self.state["active_signal"] = active_signal

        self.state["daily_signal_count"] = (
            int(
                self.state.get(
                    "daily_signal_count",
                    0,
                )
            )
            + 1
        )

        self._save_state()

        return deepcopy(active_signal)

    def update_active_signal(
        self,
        bid: float,
        ask: float,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        current_time = now or self._now()

        self._reset_daily_counter_if_needed(
            current_time
        )

        signal = self.state.get("active_signal")

        if signal is None:
            self._save_state()
            return []

        events: list[dict[str, Any]] = []

        status = signal.get(
            "status",
            "UNKNOWN",
        )

        if status not in self.ACTIVE_STATUSES:
            self._save_state()
            return events

        direction = signal["direction"]

        bid_price = float(bid)
        ask_price = float(ask)

        previous_bid = signal.get("last_bid")
        previous_ask = signal.get("last_ask")

        signal["last_bid"] = bid_price
        signal["last_ask"] = ask_price

        if status == "WAITING":
            expires_at = self._parse_datetime(
                signal.get("expires_at")
            )

            if (
                expires_at is not None
                and current_time >= expires_at
            ):
                events.append({
                    "type": "EXPIRED",
                    "message": (
                        "A jelzés lejárt, mert az ár "
                        "nem érte el időben a belépési zónát."
                    ),
                    "signal": deepcopy(signal),
                })

                self._complete_signal(
                    final_status="EXPIRED",
                    result="EXPIRED",
                    exit_price=None,
                    completed_at=current_time,
                )

                return events

            entry_hit = self._entry_was_hit(
                signal=signal,
                bid=bid_price,
                ask=ask_price,
                previous_bid=previous_bid,
                previous_ask=previous_ask,
            )

            if entry_hit:
                signal["status"] = "ACTIVE"
                signal["activated_at"] = (
                    current_time.isoformat()
                )

                events.append({
                    "type": "ENTRY",
                    "message": (
                        "Az ár elérte a belépési zónát. "
                        "A jelzés aktív."
                    ),
                    "signal": deepcopy(signal),
                })

        current_status = signal.get("status")

        if current_status in {
            "ACTIVE",
            "TP1",
            "TP2",
        }:
            market_events = (
                self._check_active_trade_levels(
                    signal=signal,
                    bid=bid_price,
                    ask=ask_price,
                    now=current_time,
                )
            )

            events.extend(market_events)

        self._save_state()

        return events

    def _entry_was_hit(
        self,
        signal: dict[str, Any],
        bid: float,
        ask: float,
        previous_bid: float | None,
        previous_ask: float | None,
    ) -> bool:
        entry_low = float(
            signal["entry_low"]
        )

        entry_high = float(
            signal["entry_high"]
        )

        direction = signal["direction"]

        if direction == "BUY":
            inside_zone = (
                entry_low <= ask <= entry_high
            )

            crossed_entire_zone = (
                previous_ask is not None
                and float(previous_ask) > entry_high
                and ask < entry_low
            )

            return (
                inside_zone
                or crossed_entire_zone
            )

        inside_zone = (
            entry_low <= bid <= entry_high
        )

        crossed_entire_zone = (
            previous_bid is not None
            and float(previous_bid) < entry_low
            and bid > entry_high
        )

        return (
            inside_zone
            or crossed_entire_zone
        )

    def _check_active_trade_levels(
        self,
        signal: dict[str, Any],
        bid: float,
        ask: float,
        now: datetime,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        direction = signal["direction"]

        stop_loss = float(
            signal["stop_loss"]
        )

        tp1 = float(signal["tp1"])
        tp2 = float(signal["tp2"])
        tp3 = float(signal["tp3"])

        highest_tp = int(
            signal.get(
                "highest_tp",
                0,
            )
        )

        if direction == "BUY":
            exit_price = bid

            if exit_price <= stop_loss:
                events.append({
                    "type": "STOPPED",
                    "message": "A Stop Loss teljesült.",
                    "signal": deepcopy(signal),
                    "price": exit_price,
                })

                self._complete_signal(
                    final_status="STOPPED",
                    result="STOP_LOSS",
                    exit_price=exit_price,
                    completed_at=now,
                )

                return events

            reached_tp = 0

            if exit_price >= tp3:
                reached_tp = 3

            elif exit_price >= tp2:
                reached_tp = 2

            elif exit_price >= tp1:
                reached_tp = 1

        else:
            exit_price = ask

            if exit_price >= stop_loss:
                events.append({
                    "type": "STOPPED",
                    "message": "A Stop Loss teljesült.",
                    "signal": deepcopy(signal),
                    "price": exit_price,
                })

                self._complete_signal(
                    final_status="STOPPED",
                    result="STOP_LOSS",
                    exit_price=exit_price,
                    completed_at=now,
                )

                return events

            reached_tp = 0

            if exit_price <= tp3:
                reached_tp = 3

            elif exit_price <= tp2:
                reached_tp = 2

            elif exit_price <= tp1:
                reached_tp = 1

        if reached_tp > highest_tp:
            for target_number in range(
                highest_tp + 1,
                reached_tp + 1,
            ):
                signal["highest_tp"] = target_number
                signal["status"] = (
                    f"TP{target_number}"
                )

                target_price = float(
                    signal[
                        f"tp{target_number}"
                    ]
                )

                events.append({
                    "type": (
                        f"TP{target_number}"
                    ),
                    "message": (
                        f"TP{target_number} teljesült."
                    ),
                    "signal": deepcopy(signal),
                    "price": target_price,
                })

        if reached_tp >= 3:
            self._complete_signal(
                final_status="TP3",
                result="TAKE_PROFIT_3",
                exit_price=exit_price,
                completed_at=now,
            )

        return events

    def _complete_signal(
        self,
        final_status: str,
        result: str,
        exit_price: float | None,
        completed_at: datetime,
    ) -> None:
        signal = self.state.get("active_signal")

        if signal is None:
            return

        signal["status"] = final_status
        signal["result"] = result
        signal["exit_price"] = exit_price
        signal["completed_at"] = (
            completed_at.isoformat()
        )

        completed_signal = deepcopy(signal)

        history = self.state.get(
            "history",
            [],
        )

        history.append(completed_signal)

        self.state["history"] = history[-100:]
        self.state["last_completed_signal"] = (
            completed_signal
        )

        self.state["active_signal"] = None

        cooldown_until = (
            completed_at
            + timedelta(
                minutes=self.cooldown_minutes
            )
        )

        self.state["cooldown_until"] = (
            cooldown_until.isoformat()
        )

        self._save_state()

    def get_status_summary(
        self,
    ) -> dict[str, Any]:
        self._reset_daily_counter_if_needed()

        allowed, reason = self.can_create_signal()

        return {
            "active_signal": self.get_active_signal(),
            "daily_signal_count": (
                self.get_daily_signal_count()
            ),
            "remaining_daily_signals": (
                self.get_remaining_daily_signals()
            ),
            "max_signals_per_day": (
                self.max_signals_per_day
            ),
            "cooldown_until": (
                self.state.get("cooldown_until")
            ),
            "can_create_signal": allowed,
            "create_signal_reason": reason,
            "last_completed_signal": deepcopy(
                self.state.get(
                    "last_completed_signal"
                )
            ),
        }