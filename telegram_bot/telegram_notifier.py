from __future__ import annotations

import html
import json
import mimetypes
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TelegramNotifier:
    """
    Telegram értesítések, chartképek és üzenetfrissítések.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        enabled: bool = True,
        timeout_seconds: int = 20,
    ) -> None:
        self.bot_token = bot_token.strip()
        self.chat_id = str(chat_id).strip()
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        return bool(
            self.bot_token
            and self.chat_id
            and self.bot_token != "IDE_JON_A_BOTFATHER_TOKEN"
            and self.chat_id != "IDE_JON_A_CHAT_ID"
        )

    def _validate(self) -> dict[str, Any] | None:
        if not self.enabled:
            return {
                "success": False,
                "code": "DISABLED",
                "reason": "A Telegram küldés ki van kapcsolva.",
            }

        if not self.is_configured():
            return {
                "success": False,
                "code": "NOT_CONFIGURED",
                "reason": (
                    "A Telegram bot token vagy chat ID "
                    "nincs megfelelően beállítva."
                ),
            }

        return None

    def _request_form(
        self,
        method: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        validation_error = self._validate()

        if validation_error is not None:
            return validation_error

        url = (
            f"https://api.telegram.org/"
            f"bot{self.bot_token}/{method}"
        )

        request = Request(
            url=url,
            data=urlencode(payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": (
                    "application/x-www-form-urlencoded"
                ),
                "User-Agent": "AURUM-Trading-Bot/1.0",
            },
        )

        return self._execute_request(request)

    def _request_multipart(
        self,
        method: str,
        fields: dict[str, Any],
        file_field: str,
        file_path: str | Path,
    ) -> dict[str, Any]:
        validation_error = self._validate()

        if validation_error is not None:
            return validation_error

        path = Path(file_path)

        if not path.exists() or not path.is_file():
            return {
                "success": False,
                "code": "FILE_NOT_FOUND",
                "reason": f"A chartfájl nem található: {path}",
            }

        boundary = "----AURUM" + uuid.uuid4().hex
        body = bytearray()

        for name, value in fields.items():
            body.extend(
                f"--{boundary}\r\n".encode("utf-8")
            )
            body.extend(
                (
                    f'Content-Disposition: form-data; '
                    f'name="{name}"\r\n\r\n'
                ).encode("utf-8")
            )
            body.extend(str(value).encode("utf-8"))
            body.extend(b"\r\n")

        mime_type = (
            mimetypes.guess_type(path.name)[0]
            or "application/octet-stream"
        )

        body.extend(
            f"--{boundary}\r\n".encode("utf-8")
        )
        body.extend(
            (
                f'Content-Disposition: form-data; '
                f'name="{file_field}"; '
                f'filename="{path.name}"\r\n'
            ).encode("utf-8")
        )
        body.extend(
            f"Content-Type: {mime_type}\r\n\r\n".encode(
                "utf-8"
            )
        )
        body.extend(path.read_bytes())
        body.extend(b"\r\n")
        body.extend(
            f"--{boundary}--\r\n".encode("utf-8")
        )

        url = (
            f"https://api.telegram.org/"
            f"bot{self.bot_token}/{method}"
        )

        request = Request(
            url=url,
            data=bytes(body),
            method="POST",
            headers={
                "Content-Type": (
                    f"multipart/form-data; boundary={boundary}"
                ),
                "Content-Length": str(len(body)),
                "User-Agent": "AURUM-Trading-Bot/1.0",
            },
        )

        return self._execute_request(request)

    def _execute_request(
        self,
        request: Request,
    ) -> dict[str, Any]:
        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                response_body = response.read().decode("utf-8")

            parsed_response = json.loads(response_body)

            if not parsed_response.get("ok", False):
                return {
                    "success": False,
                    "code": "TELEGRAM_REJECTED",
                    "reason": parsed_response.get(
                        "description",
                        "A Telegram elutasította a kérést.",
                    ),
                }

            result = parsed_response.get("result", {})

            response_data: dict[str, Any] = {
                "success": True,
                "code": "SENT",
                "reason": "A Telegram-kérés sikeres.",
                "result": result,
            }

            if isinstance(result, dict):
                response_data["message_id"] = result.get(
                    "message_id"
                )

            return response_data

        except HTTPError as error:
            error_body = ""

            try:
                error_body = error.read().decode("utf-8")
            except Exception:
                error_body = ""

            reason = f"Telegram HTTP-hiba: {error.code}"

            if error_body:
                try:
                    error_data = json.loads(error_body)
                    description = error_data.get("description")

                    if description:
                        reason = description
                except json.JSONDecodeError:
                    reason = f"{reason} – {error_body}"

            if "message is not modified" in reason.lower():
                return {
                    "success": True,
                    "code": "NOT_MODIFIED",
                    "reason": (
                        "Az üzenet már ezt a tartalmat tartalmazza."
                    ),
                }

            return {
                "success": False,
                "code": "HTTP_ERROR",
                "reason": reason,
            }

        except URLError as error:
            return {
                "success": False,
                "code": "NETWORK_ERROR",
                "reason": (
                    "Nem sikerült kapcsolódni a Telegramhoz: "
                    f"{error.reason}"
                ),
            }

        except TimeoutError:
            return {
                "success": False,
                "code": "TIMEOUT",
                "reason": (
                    "A Telegram-kérés időtúllépés miatt megszakadt."
                ),
            }

        except json.JSONDecodeError:
            return {
                "success": False,
                "code": "INVALID_RESPONSE",
                "reason": (
                    "A Telegram válasza nem értelmezhető."
                ),
            }

        except Exception as error:
            return {
                "success": False,
                "code": "UNKNOWN_ERROR",
                "reason": (
                    f"Telegram-hiba: "
                    f"{type(error).__name__}: {error}"
                ),
            }

    def send_message(
        self,
        message: str,
        disable_notification: bool = False,
    ) -> dict[str, Any]:
        result = self._request_form(
            method="sendMessage",
            payload={
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "link_preview_options": json.dumps(
                    {"is_disabled": True}
                ),
                "disable_notification": (
                    "true"
                    if disable_notification
                    else "false"
                ),
            },
        )

        if result.get("success", False):
            result["message_type"] = "text"

        return result

    def send_photo(
        self,
        photo_path: str | Path,
        caption: str,
        disable_notification: bool = False,
    ) -> dict[str, Any]:
        result = self._request_multipart(
            method="sendPhoto",
            fields={
                "chat_id": self.chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "disable_notification": (
                    "true"
                    if disable_notification
                    else "false"
                ),
            },
            file_field="photo",
            file_path=photo_path,
        )

        if result.get("success", False):
            result["message_type"] = "photo"

        return result

    def edit_message(
        self,
        message_id: int,
        message: str,
    ) -> dict[str, Any]:
        return self._request_form(
            method="editMessageText",
            payload={
                "chat_id": self.chat_id,
                "message_id": str(int(message_id)),
                "text": message,
                "parse_mode": "HTML",
                "link_preview_options": json.dumps(
                    {"is_disabled": True}
                ),
            },
        )

    def edit_caption(
        self,
        message_id: int,
        caption: str,
    ) -> dict[str, Any]:
        return self._request_form(
            method="editMessageCaption",
            payload={
                "chat_id": self.chat_id,
                "message_id": str(int(message_id)),
                "caption": caption,
                "parse_mode": "HTML",
            },
        )

    def send_startup_message(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        return self.send_message(
            message=(
                "🚀 <b>AURUM ELINDULT</b>\n\n"
                f"📊 Instrumentum: "
                f"<b>{html.escape(symbol)}</b>\n"
                "📡 Piaci elemző rendszer: <b>ONLINE</b>\n"
                "🤖 Telegram kapcsolat: <b>SIKERES</b>"
            ),
            disable_notification=True,
        )

    def send_new_signal(
        self,
        signal: dict[str, Any],
        chart_path: str | Path | None = None,
    ) -> dict[str, Any]:
        caption = self._build_signal_message(signal)

        if chart_path is not None:
            photo_result = self.send_photo(
                photo_path=chart_path,
                caption=caption,
            )

            if photo_result.get("success", False):
                return photo_result

        return self.send_message(caption)

    def update_signal_message(
        self,
        signal: dict[str, Any],
    ) -> dict[str, Any]:
        message_id = signal.get("telegram_message_id")

        if message_id is None:
            return {
                "success": False,
                "code": "NO_MESSAGE_ID",
                "reason": (
                    "A jelzéshez nincs eltárolva "
                    "Telegram message ID."
                ),
            }

        message_type = str(
            signal.get(
                "telegram_message_type",
                "text",
            )
        ).lower()

        content = self._build_signal_message(signal)

        if message_type == "photo":
            return self.edit_caption(
                message_id=int(message_id),
                caption=content,
            )

        return self.edit_message(
            message_id=int(message_id),
            message=content,
        )


    def send_statistics_report(
        self,
        statistics: dict[str, Any],
        title: str = "AURUM STATISTICS",
        report_date: str | None = None,
    ) -> dict[str, Any]:
        safe_title = html.escape(title)
        date_line = (
            f"📅 Dátum: <b>{html.escape(report_date)}</b>\n"
            if report_date
            else ""
        )
        message = (
            f"📈 <b>{safe_title}</b>\n\n"
            f"{date_line}"
            f"📨 Jelzések: <b>{int(statistics.get('signals', 0))}</b>\n"
            f"✅ Nyerők: <b>{int(statistics.get('wins', 0))}</b>\n"
            f"❌ Vesztesek: <b>{int(statistics.get('losses', 0))}</b>\n"
            f"🟡 Breakeven: <b>{int(statistics.get('breakeven', 0))}</b>\n"
            f"⌛ Lejárt: <b>{int(statistics.get('expired', 0))}</b>\n\n"
            f"🎯 TP1: <b>{int(statistics.get('tp1_hits', 0))}</b>\n"
            f"🎯 TP2: <b>{int(statistics.get('tp2_hits', 0))}</b>\n"
            f"🎯 TP3: <b>{int(statistics.get('tp3_hits', 0))}</b>\n"
            f"🔒 TP1 Lock: <b>{int(statistics.get('tp1_locked', 0))}</b>\n\n"
            f"🏆 Win rate: <b>{float(statistics.get('win_rate', 0.0)):.2f}%</b>\n"
            f"📊 Átlagos R: <b>{float(statistics.get('average_rr', 0.0)):.2f}R</b>\n"
            f"💰 Nettó R: <b>{float(statistics.get('net_r', 0.0)):.2f}R</b>\n"
            f"⚖️ Profit factor: <b>{float(statistics.get('profit_factor', 0.0)):.2f}</b>"
        )
        return self.send_message(message, disable_notification=True)

    def send_test_message(self) -> dict[str, Any]:
        return self.send_message(
            "✅ <b>AURUM TELEGRAM TESZT</b>\n\n"
            "A Telegram kapcsolat megfelelően működik."
        )

    def _build_signal_message(
        self,
        signal: dict[str, Any],
    ) -> str:
        direction = str(
            signal.get("direction", "NONE")
        ).upper()
        symbol = html.escape(
            str(signal.get("symbol", "UNKNOWN"))
        )
        status = str(
            signal.get("status", "WAITING")
        ).upper()

        direction_icon = (
            "🟢"
            if direction == "BUY"
            else "🔴"
        )

        status_title, status_icon = self._status_display(
            status
        )

        entry_low = self._format_price(
            signal.get("entry_low")
        )
        entry_high = self._format_price(
            signal.get("entry_high")
        )
        entry_price = self._format_price(
            signal.get("entry_price")
        )
        current_stop = self._format_price(
            signal.get("stop_loss")
        )
        original_stop = self._format_price(
            signal.get("original_stop_loss")
        )
        tp1 = self._format_price(signal.get("tp1"))
        tp2 = self._format_price(signal.get("tp2"))
        tp3 = self._format_price(signal.get("tp3"))

        highest_tp = int(
            signal.get("highest_tp", 0) or 0
        )

        tp1_icon = "✅" if highest_tp >= 1 else "⏳"
        tp2_icon = "✅" if highest_tp >= 2 else "⏳"
        tp3_icon = "✅" if highest_tp >= 3 else "⏳"

        confidence = html.escape(
            str(signal.get("confidence", "UNKNOWN"))
        )

        buy_score = signal.get("buy_score", 0)
        sell_score = signal.get("sell_score", 0)

        expires_at = self._format_datetime(
            signal.get("expires_at")
        )
        activated_at = self._format_datetime(
            signal.get("activated_at")
        )
        completed_at = self._format_datetime(
            signal.get("completed_at")
        )

        stop_stage = str(
            signal.get("stop_stage", "ORIGINAL")
        ).upper()

        stop_label = self._stop_stage_display(
            stop_stage=stop_stage,
            current_stop=current_stop,
            original_stop=original_stop,
            entry_price=entry_price,
            tp1=tp1,
        )

        time_lines = []

        if activated_at != "N/A":
            time_lines.append(
                f"✅ Aktiválva: <code>{activated_at}</code>"
            )

        if status == "WAITING":
            time_lines.append(
                f"⌛ Lejárat: <code>{expires_at}</code>"
            )

        if completed_at != "N/A":
            time_lines.append(
                f"🏁 Lezárva: <code>{completed_at}</code>"
            )

        exit_line = ""

        if signal.get("exit_price") is not None:
            exit_line = (
                "\n💰 Záróár: "
                f"<b>{self._format_price(signal.get('exit_price'))}</b>"
            )

        result_line = self._result_display(
            signal.get("result")
        )

        time_block = ""

        if time_lines:
            time_block = "\n\n" + "\n".join(time_lines)

        return (
            f"🏆 <b>AURUM | {symbol}</b>\n\n"
            f"{direction_icon} <b>{direction}: "
            f"{entry_low} – {entry_high}</b>\n"
            f"🎯 Entry ár: <b>{entry_price}</b>\n\n"
            f"{stop_label}\n\n"
            f"{tp1_icon} TP1: <b>{tp1}</b>\n"
            f"{tp2_icon} TP2: <b>{tp2}</b>\n"
            f"{tp3_icon} TP3: <b>{tp3}</b>\n\n"
            f"{status_icon} Állapot: "
            f"<b>{status_title}</b>"
            f"{exit_line}"
            f"{result_line}\n\n"
            f"📊 BUY: <b>{buy_score}</b> | "
            f"SELL: <b>{sell_score}</b>\n"
            f"⭐ Bizalom: <b>{confidence}</b>"
            f"{time_block}\n\n"
            "⚠️ <i>Nem pénzügyi tanács.</i>"
        )

    @staticmethod
    def _stop_stage_display(
        stop_stage: str,
        current_stop: str,
        original_stop: str,
        entry_price: str,
        tp1: str,
    ) -> str:
        if stop_stage == "BREAKEVEN":
            return (
                "🛡️ SL: "
                f"<b>{current_stop}</b>\n"
                "✅ Védelem: <b>BREAKEVEN</b>\n"
                f"↪️ Entry szint: <b>{entry_price}</b>"
            )

        if stop_stage == "TP1_LOCK":
            return (
                "🔒 SL: "
                f"<b>{current_stop}</b>\n"
                "✅ Védelem: <b>TP1 PROFIT RÖGZÍTVE</b>\n"
                f"↪️ TP1 szint: <b>{tp1}</b>"
            )

        return (
            "🛑 SL: "
            f"<b>{current_stop}</b>\n"
            f"↪️ Eredeti SL: <b>{original_stop}</b>"
        )

    @staticmethod
    def _result_display(
        result: Any,
    ) -> str:
        if result is None:
            return ""

        result_text = str(result).upper()

        result_map = {
            "TAKE_PROFIT_3": "\n🏆 Eredmény: <b>TP3</b>",
            "STOP_LOSS": "\n❌ Eredmény: <b>STOP LOSS</b>",
            "BREAKEVEN": "\n🛡️ Eredmény: <b>BREAKEVEN</b>",
            "TP1_LOCKED": (
                "\n🔒 Eredmény: "
                "<b>TP1 PROFIT RÖGZÍTVE</b>"
            ),
            "EXPIRED": "\n⌛ Eredmény: <b>LEJÁRT</b>",
        }

        return result_map.get(
            result_text,
            f"\nℹ️ Eredmény: <b>{html.escape(result_text)}</b>",
        )

    @staticmethod
    def _status_display(
        status: str,
    ) -> tuple[str, str]:
        statuses = {
            "WAITING": ("BELÉPÉSRE VÁR", "⏳"),
            "ACTIVE": ("AKTÍV", "📡"),
            "TP1": ("TP1 ELÉRVE – BREAKEVEN", "🛡️"),
            "TP2": ("TP2 ELÉRVE – TP1 LOCK", "🔒"),
            "TP3": ("TP3 ELÉRVE – LEZÁRVA", "🏆"),
            "STOPPED": ("STOP TELJESÜLT – LEZÁRVA", "🛑"),
            "EXPIRED": ("LEJÁRT", "⌛"),
        }

        return statuses.get(
            status,
            (html.escape(status), "ℹ️"),
        )

    @staticmethod
    def _format_datetime(value: Any) -> str:
        if value is None:
            return "N/A"

        text = str(value)

        try:
            from datetime import datetime

            parsed = datetime.fromisoformat(text)
            return parsed.strftime("%Y.%m.%d. %H:%M:%S")
        except (TypeError, ValueError):
            return html.escape(text)

    @staticmethod
    def _format_price(value: Any) -> str:
        if value is None:
            return "N/A"

        try:
            number = float(value)
        except (TypeError, ValueError):
            return html.escape(str(value))

        formatted = f"{number:.2f}"
        return formatted.rstrip("0").rstrip(".")
