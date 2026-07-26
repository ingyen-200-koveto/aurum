from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any


class SignalManager:
    """
    AURUM jelzésállapot-kezelő.

    Breakeven logika:
    - TP1 után az SL az Entry árra kerül.
    - TP2 után az SL a TP1 szintre kerül.
    """

    ACTIVE_STATUSES = {
        "WAITING",
        "ACTIVE",
        "TP1",
        "TP2",
    }

    def __init__(
        self,
        state_file: str = "data/signal_state.json",
        statistics_file: str = "data/statistics.json",
        max_signals_per_day: int = 6,
        cooldown_minutes: int = 30,
        expiration_minutes: int = 180,
    ) -> None:
        self.state_file = str(state_file)
        self.statistics_file = str(statistics_file)
        self.max_signals_per_day = max_signals_per_day
        self.cooldown_minutes = cooldown_minutes
        self.expiration_minutes = expiration_minutes

        self._ensure_state_directory()
        self._ensure_statistics_directory()
        self.state = self._load_state()
        self._reset_daily_counter_if_needed()
        self._save_state()
        self._save_statistics()

    def _ensure_state_directory(self) -> None:
        directory = os.path.dirname(self.state_file)

        if directory:
            os.makedirs(directory, exist_ok=True)


    def _ensure_statistics_directory(self) -> None:
        directory = os.path.dirname(self.statistics_file)

        if directory:
            os.makedirs(directory, exist_ok=True)

    def _default_state(self) -> dict[str, Any]:
        now = self._now()

        return {
            "date": now.date().isoformat(),
            "daily_signal_count": 0,
            "active_signal": None,
            "cooldown_until": None,
            "last_completed_signal": None,
            "history": [],
            "last_daily_report_date": None,
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
                loaded_state.setdefault(key, value)

            active_signal = loaded_state.get("active_signal")

            if isinstance(active_signal, dict):
                active_signal.setdefault(
                    "telegram_message_id",
                    None,
                )
                active_signal.setdefault(
                    "telegram_message_type",
                    "text",
                )
                active_signal.setdefault(
                    "chart_path",
                    None,
                )
                active_signal.setdefault(
                    "original_stop_loss",
                    active_signal.get("stop_loss"),
                )
                active_signal.setdefault(
                    "breakeven_active",
                    False,
                )
                active_signal.setdefault(
                    "stop_stage",
                    "ORIGINAL",
                )

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


    def _calculate_realized_r(self, signal: dict[str, Any]) -> float | None:
        result = str(signal.get("result") or "").upper()

        if result == "TAKE_PROFIT_3":
            return 3.0
        if result == "TP1_LOCKED":
            return 1.0
        if result == "BREAKEVEN":
            return 0.0
        if result == "STOP_LOSS":
            return -1.0
        if result == "EXPIRED":
            return None

        highest_tp = int(signal.get("highest_tp", 0) or 0)
        if highest_tp >= 3:
            return 3.0
        return None

    def _statistics_for_history(
        self,
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        completed = [item for item in history if isinstance(item, dict)]
        expired = sum(
            1
            for item in completed
            if str(item.get("result") or "").upper() == "EXPIRED"
        )
        trade_results: list[float] = []

        for item in completed:
            realized_r = self._calculate_realized_r(item)
            if realized_r is not None:
                trade_results.append(realized_r)

        wins = sum(1 for value in trade_results if value > 0)
        losses = sum(1 for value in trade_results if value < 0)
        breakeven = sum(1 for value in trade_results if value == 0)
        tp1_locked = sum(
            1
            for item in completed
            if str(item.get("result") or "").upper() == "TP1_LOCKED"
        )
        tp1_hits = sum(1 for item in completed if int(item.get("highest_tp", 0) or 0) >= 1)
        tp2_hits = sum(1 for item in completed if int(item.get("highest_tp", 0) or 0) >= 2)
        tp3_hits = sum(1 for item in completed if int(item.get("highest_tp", 0) or 0) >= 3)
        settled = len(trade_results)
        win_rate = (wins / settled * 100.0) if settled else 0.0
        loss_rate = (losses / settled * 100.0) if settled else 0.0
        average_rr = (sum(trade_results) / settled) if settled else 0.0
        gross_profit = sum(value for value in trade_results if value > 0)
        gross_loss = abs(sum(value for value in trade_results if value < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        return {
            "signals": len(completed),
            "settled_trades": settled,
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "expired": expired,
            "tp1_locked": tp1_locked,
            "tp1_hits": tp1_hits,
            "tp2_hits": tp2_hits,
            "tp3_hits": tp3_hits,
            "win_rate": round(win_rate, 2),
            "loss_rate": round(loss_rate, 2),
            "average_rr": round(average_rr, 2),
            "profit_factor": round(profit_factor, 2),
            "net_r": round(sum(trade_results), 2),
            "gross_profit_r": round(gross_profit, 2),
            "gross_loss_r": round(gross_loss, 2),
        }

    def get_statistics(self, date: str | None = None) -> dict[str, Any]:
        history = self.state.get("history", [])
        if not isinstance(history, list):
            history = []

        selected_history: list[dict[str, Any]] = []
        for item in history:
            if not isinstance(item, dict):
                continue
            if date is None:
                selected_history.append(item)
                continue
            completed_at = self._parse_datetime(item.get("completed_at"))
            if completed_at is not None and completed_at.date().isoformat() == date:
                selected_history.append(item)

        return self._statistics_for_history(selected_history)

    def get_statistics_summary(self) -> dict[str, Any]:
        today = self._now().date().isoformat()
        return {
            "updated_at": self._now().isoformat(),
            "all_time": self.get_statistics(),
            "today": self.get_statistics(today),
        }

    def _save_statistics(self) -> None:
        temporary_file = f"{self.statistics_file}.tmp"
        data = self.get_statistics_summary()

        with open(temporary_file, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

        os.replace(temporary_file, self.statistics_file)

    def get_pending_daily_report(
        self,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        current_time = now or self._now()
        report_date = (current_time.date() - timedelta(days=1)).isoformat()

        if self.state.get("last_daily_report_date") == report_date:
            return None

        statistics = self.get_statistics(report_date)
        if statistics.get("signals", 0) <= 0:
            self.state["last_daily_report_date"] = report_date
            self._save_state()
            return None

        return {
            "date": report_date,
            "statistics": statistics,
        }

    def mark_daily_report_sent(self, report_date: str) -> None:
        self.state["last_daily_report_date"] = report_date
        self._save_state()

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

        return bool(
            isinstance(signal, dict)
            and signal.get("status") in self.ACTIVE_STATUSES
        )

    def get_active_signal(
        self,
    ) -> dict[str, Any] | None:
        signal = self.state.get("active_signal")

        if not isinstance(signal, dict):
            return None

        return deepcopy(signal)

    def get_daily_signal_count(self) -> int:
        self._reset_daily_counter_if_needed()
        return int(
            self.state.get("daily_signal_count", 0)
        )

    def get_remaining_daily_signals(self) -> int:
        return max(
            0,
            self.max_signals_per_day
            - self.get_daily_signal_count(),
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
        self._reset_daily_counter_if_needed(current_time)

        if self.has_active_signal():
            return (
                False,
                "Már van aktív vagy belépésre váró jelzés.",
            )

        if (
            self.get_daily_signal_count()
            >= self.max_signals_per_day
        ):
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
                (remaining_seconds + 59) // 60,
            )

            return (
                False,
                (
                    "Cooldown aktív. "
                    f"Még körülbelül {remaining_minutes} perc."
                ),
            )

        return True, "Új jelzés létrehozható."

    def create_signal(
        self,
        symbol: str,
        signal_result: dict[str, Any],
        trade_levels: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        current_time = now or self._now()

        allowed, _ = self.can_create_signal(current_time)

        if not allowed:
            return None

        if not trade_levels.get("valid", False):
            return None

        direction = str(
            trade_levels.get("direction", "NONE")
        ).upper()

        if direction not in {"BUY", "SELL"}:
            return None

        created_at = current_time
        expires_at = (
            created_at
            + timedelta(minutes=self.expiration_minutes)
        )

        signal_id = (
            f"{created_at.strftime('%Y%m%d-%H%M%S')}"
            f"-{direction}"
        )

        original_stop_loss = float(
            trade_levels["stop_loss"]
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
            "entry_low": float(trade_levels["entry_low"]),
            "entry_high": float(trade_levels["entry_high"]),
            "entry_price": float(trade_levels["entry_price"]),
            "stop_loss": original_stop_loss,
            "original_stop_loss": original_stop_loss,
            "tp1": float(trade_levels["tp1"]),
            "tp2": float(trade_levels["tp2"]),
            "tp3": float(trade_levels["tp3"]),
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
                signal_result.get("buy_score", 0)
            ),
            "sell_score": int(
                signal_result.get("sell_score", 0)
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
            "breakeven_active": False,
            "stop_stage": "ORIGINAL",
            "telegram_message_id": None,
            "telegram_message_type": "text",
            "chart_path": None,
        }

        self.state["active_signal"] = active_signal
        self.state["daily_signal_count"] = (
            self.get_daily_signal_count() + 1
        )

        self._save_state()
        return deepcopy(active_signal)

    def set_telegram_message(
        self,
        signal_id: str,
        message_id: int,
        message_type: str = "text",
        chart_path: str | None = None,
    ) -> bool:
        signal = self.state.get("active_signal")

        if not isinstance(signal, dict):
            return False

        if signal.get("id") != signal_id:
            return False

        signal["telegram_message_id"] = int(message_id)
        signal["telegram_message_type"] = str(
            message_type
        ).lower()
        signal["chart_path"] = chart_path

        self._save_state()
        return True

    def set_telegram_message_id(
        self,
        signal_id: str,
        message_id: int,
    ) -> bool:
        return self.set_telegram_message(
            signal_id=signal_id,
            message_id=message_id,
            message_type="text",
        )

    def update_active_signal(
        self,
        bid: float,
        ask: float,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        current_time = now or self._now()
        self._reset_daily_counter_if_needed(current_time)

        signal = self.state.get("active_signal")

        if not isinstance(signal, dict):
            self._save_state()
            return []

        if signal.get("status") not in self.ACTIVE_STATUSES:
            self._save_state()
            return []

        events: list[dict[str, Any]] = []

        bid_price = float(bid)
        ask_price = float(ask)

        previous_bid = signal.get("last_bid")
        previous_ask = signal.get("last_ask")

        signal["last_bid"] = bid_price
        signal["last_ask"] = ask_price

        if signal.get("status") == "WAITING":
            expires_at = self._parse_datetime(
                signal.get("expires_at")
            )

            if (
                expires_at is not None
                and current_time >= expires_at
            ):
                signal["status"] = "EXPIRED"
                signal["result"] = "EXPIRED"
                signal["completed_at"] = (
                    current_time.isoformat()
                )

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

            if self._entry_was_hit(
                signal=signal,
                bid=bid_price,
                ask=ask_price,
                previous_bid=previous_bid,
                previous_ask=previous_ask,
            ):
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

        if signal.get("status") in {
            "ACTIVE",
            "TP1",
            "TP2",
        }:
            events.extend(
                self._check_active_trade_levels(
                    signal=signal,
                    bid=bid_price,
                    ask=ask_price,
                    now=current_time,
                )
            )

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
        entry_low = float(signal["entry_low"])
        entry_high = float(signal["entry_high"])

        if signal["direction"] == "BUY":
            inside_zone = entry_low <= ask <= entry_high
            crossed_zone = (
                previous_ask is not None
                and float(previous_ask) > entry_high
                and ask < entry_low
            )
            return inside_zone or crossed_zone

        inside_zone = entry_low <= bid <= entry_high
        crossed_zone = (
            previous_bid is not None
            and float(previous_bid) < entry_low
            and bid > entry_high
        )
        return inside_zone or crossed_zone

    def _check_active_trade_levels(
        self,
        signal: dict[str, Any],
        bid: float,
        ask: float,
        now: datetime,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        direction = signal["direction"]
        stop_loss = float(signal["stop_loss"])
        tp1 = float(signal["tp1"])
        tp2 = float(signal["tp2"])
        tp3 = float(signal["tp3"])
        highest_tp = int(signal.get("highest_tp", 0))

        exit_price = bid if direction == "BUY" else ask

        stop_hit = (
            exit_price <= stop_loss
            if direction == "BUY"
            else exit_price >= stop_loss
        )

        if stop_hit:
            stop_stage = str(
                signal.get("stop_stage", "ORIGINAL")
            ).upper()

            if stop_stage == "TP1_LOCK":
                result = "TP1_LOCKED"
                message = (
                    "A mozgó Stop Loss a TP1 szinten teljesült."
                )
            elif stop_stage == "BREAKEVEN":
                result = "BREAKEVEN"
                message = (
                    "A Breakeven Stop Loss teljesült."
                )
            else:
                result = "STOP_LOSS"
                message = "Az eredeti Stop Loss teljesült."

            signal["status"] = "STOPPED"
            signal["result"] = result
            signal["exit_price"] = exit_price
            signal["completed_at"] = now.isoformat()

            events.append({
                "type": "STOPPED",
                "message": message,
                "signal": deepcopy(signal),
                "price": exit_price,
            })

            self._complete_signal(
                final_status="STOPPED",
                result=result,
                exit_price=exit_price,
                completed_at=now,
            )

            return events

        if direction == "BUY":
            if exit_price >= tp3:
                reached_tp = 3
            elif exit_price >= tp2:
                reached_tp = 2
            elif exit_price >= tp1:
                reached_tp = 1
            else:
                reached_tp = 0
        else:
            if exit_price <= tp3:
                reached_tp = 3
            elif exit_price <= tp2:
                reached_tp = 2
            elif exit_price <= tp1:
                reached_tp = 1
            else:
                reached_tp = 0

        if reached_tp > highest_tp:
            for target_number in range(
                highest_tp + 1,
                reached_tp + 1,
            ):
                signal["highest_tp"] = target_number
                signal["status"] = f"TP{target_number}"

                if target_number == 1:
                    signal["stop_loss"] = float(
                        signal["entry_price"]
                    )
                    signal["breakeven_active"] = True
                    signal["stop_stage"] = "BREAKEVEN"

                elif target_number == 2:
                    signal["stop_loss"] = float(
                        signal["tp1"]
                    )
                    signal["breakeven_active"] = True
                    signal["stop_stage"] = "TP1_LOCK"

                elif target_number == 3:
                    signal["result"] = "TAKE_PROFIT_3"
                    signal["exit_price"] = exit_price
                    signal["completed_at"] = now.isoformat()

                events.append({
                    "type": f"TP{target_number}",
                    "message": self._tp_event_message(
                        target_number=target_number,
                        signal=signal,
                    ),
                    "signal": deepcopy(signal),
                    "price": float(
                        signal[f"tp{target_number}"]
                    ),
                })

        if reached_tp >= 3:
            self._complete_signal(
                final_status="TP3",
                result="TAKE_PROFIT_3",
                exit_price=exit_price,
                completed_at=now,
            )

        return events

    def _tp_event_message(
        self,
        target_number: int,
        signal: dict[str, Any],
    ) -> str:
        if target_number == 1:
            return (
                "TP1 teljesült. "
                "A Stop Loss Breakevenre, "
                "az Entry árra került."
            )

        if target_number == 2:
            return (
                "TP2 teljesült. "
                "A Stop Loss a TP1 szintre került."
            )

        return "TP3 teljesült. A jelzés lezárult."

    def _complete_signal(
        self,
        final_status: str,
        result: str,
        exit_price: float | None,
        completed_at: datetime,
    ) -> None:
        signal = self.state.get("active_signal")

        if not isinstance(signal, dict):
            return

        signal["status"] = final_status
        signal["result"] = result
        signal["exit_price"] = exit_price
        signal["completed_at"] = completed_at.isoformat()

        completed_signal = deepcopy(signal)

        history = self.state.get("history", [])
        history.append(completed_signal)

        self.state["history"] = history
        self.state["last_completed_signal"] = (
            completed_signal
        )
        self.state["active_signal"] = None
        self.state["cooldown_until"] = (
            completed_at
            + timedelta(minutes=self.cooldown_minutes)
        ).isoformat()

        self._save_state()
        self._save_statistics()

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
                self.state.get("last_completed_signal")
            ),
            "statistics": self.get_statistics_summary(),
        }