from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


class ChartGenerator:
    """
    M5 gyertyachart készítése Entry, SL és TP szintekkel.

    A bemenet lehet:
    - pandas DataFrame
    - NumPy structured array
    - list[dict]
    - MetaTrader5 rates tömb
    """

    def __init__(
        self,
        output_dir: str | Path,
        candle_count: int = 70,
        enabled: bool = True,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.candle_count = max(20, int(candle_count))
        self.enabled = enabled

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def create_signal_chart(
        self,
        candles: Any,
        signal: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.enabled:
            return {
                "success": False,
                "code": "DISABLED",
                "reason": "A chart készítés ki van kapcsolva.",
                "path": None,
            }

        try:
            rows = self._normalize_candles(candles)

            if len(rows) < 10:
                return {
                    "success": False,
                    "code": "NOT_ENOUGH_CANDLES",
                    "reason": (
                        "Nincs elegendő M5 gyertya "
                        "a chart elkészítéséhez."
                    ),
                    "path": None,
                }

            rows = rows[-self.candle_count:]
            path = self._build_output_path(signal)
            self._draw_chart(
                rows=rows,
                signal=signal,
                output_path=path,
            )

            return {
                "success": True,
                "code": "CREATED",
                "reason": "A chart elkészült.",
                "path": str(path),
            }

        except Exception as error:
            return {
                "success": False,
                "code": "CHART_ERROR",
                "reason": (
                    f"{type(error).__name__}: {error}"
                ),
                "path": None,
            }

    def _build_output_path(
        self,
        signal: dict[str, Any],
    ) -> Path:
        symbol = self._safe_filename(
            str(signal.get("symbol", "UNKNOWN"))
        )
        direction = self._safe_filename(
            str(signal.get("direction", "NONE"))
        )
        signal_id = self._safe_filename(
            str(
                signal.get(
                    "id",
                    datetime.now().strftime("%Y%m%d-%H%M%S"),
                )
            )
        )

        return (
            self.output_dir
            / f"{symbol}_{direction}_{signal_id}.png"
        )

    def _draw_chart(
        self,
        rows: list[dict[str, Any]],
        signal: dict[str, Any],
        output_path: Path,
    ) -> None:
        times = [row["time"] for row in rows]
        x_values = mdates.date2num(times)

        figure, axis = plt.subplots(
            figsize=(14, 8),
            dpi=140,
        )

        candle_width = self._candle_width(x_values)

        for x_value, row in zip(x_values, rows):
            open_price = row["open"]
            high_price = row["high"]
            low_price = row["low"]
            close_price = row["close"]

            is_bullish = close_price >= open_price
            candle_color = (
                "#18b87a"
                if is_bullish
                else "#e14b5a"
            )

            axis.vlines(
                x=x_value,
                ymin=low_price,
                ymax=high_price,
                linewidth=1.0,
                color=candle_color,
                zorder=2,
            )

            body_low = min(open_price, close_price)
            body_height = abs(close_price - open_price)

            if body_height == 0:
                body_height = max(
                    (high_price - low_price) * 0.02,
                    0.00001,
                )

            rectangle = Rectangle(
                (x_value - candle_width / 2, body_low),
                candle_width,
                body_height,
                facecolor=candle_color,
                edgecolor=candle_color,
                linewidth=0.8,
                zorder=3,
            )
            axis.add_patch(rectangle)

        entry_low = float(signal["entry_low"])
        entry_high = float(signal["entry_high"])
        stop_loss = float(signal["stop_loss"])
        tp1 = float(signal["tp1"])
        tp2 = float(signal["tp2"])
        tp3 = float(signal["tp3"])

        axis.axhspan(
            entry_low,
            entry_high,
            alpha=0.18,
            label="ENTRY ZÓNA",
        )

        axis.axhline(
            stop_loss,
            linestyle="--",
            linewidth=1.5,
            label=f"SL {self._format_price(stop_loss)}",
        )

        axis.axhline(
            tp1,
            linestyle="--",
            linewidth=1.2,
            label=f"TP1 {self._format_price(tp1)}",
        )
        axis.axhline(
            tp2,
            linestyle="--",
            linewidth=1.2,
            label=f"TP2 {self._format_price(tp2)}",
        )
        axis.axhline(
            tp3,
            linestyle="--",
            linewidth=1.2,
            label=f"TP3 {self._format_price(tp3)}",
        )

        latest_close = rows[-1]["close"]
        axis.axhline(
            latest_close,
            linewidth=0.9,
            alpha=0.55,
            label=(
                "Aktuális ár "
                f"{self._format_price(latest_close)}"
            ),
        )

        symbol = str(signal.get("symbol", "UNKNOWN"))
        direction = str(
            signal.get("direction", "NONE")
        ).upper()
        confidence = str(
            signal.get("confidence", "UNKNOWN")
        )

        axis.set_title(
            f"AURUM | {symbol} M5 | "
            f"{direction} | Bizalom: {confidence}",
            fontsize=15,
            fontweight="bold",
            pad=16,
        )

        axis.set_xlabel("Idő")
        axis.set_ylabel("Ár")
        axis.xaxis.set_major_formatter(
            mdates.DateFormatter("%H:%M")
        )
        axis.grid(
            True,
            alpha=0.20,
            linewidth=0.7,
        )
        axis.legend(
            loc="best",
            frameon=True,
        )

        figure.autofmt_xdate()
        figure.tight_layout()
        figure.savefig(
            output_path,
            format="png",
            bbox_inches="tight",
        )
        plt.close(figure)

    def _normalize_candles(
        self,
        candles: Any,
    ) -> list[dict[str, Any]]:
        if candles is None:
            return []

        if hasattr(candles, "to_dict"):
            try:
                records = candles.to_dict("records")
                return self._normalize_records(records)
            except TypeError:
                pass

        if hasattr(candles, "dtype") and getattr(
            candles.dtype,
            "names",
            None,
        ):
            records = []

            for row in candles:
                records.append({
                    name: row[name]
                    for name in candles.dtype.names
                })

            return self._normalize_records(records)

        if isinstance(candles, (list, tuple)):
            return self._normalize_records(list(candles))

        try:
            return self._normalize_records(list(candles))
        except TypeError:
            return []

    def _normalize_records(
        self,
        records: list[Any],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []

        for record in records:
            mapping = self._as_mapping(record)

            if not mapping:
                continue

            time_value = (
                mapping.get("time")
                or mapping.get("datetime")
                or mapping.get("date")
            )

            open_value = mapping.get("open")
            high_value = mapping.get("high")
            low_value = mapping.get("low")
            close_value = mapping.get("close")

            if (
                time_value is None
                or open_value is None
                or high_value is None
                or low_value is None
                or close_value is None
            ):
                continue

            normalized.append({
                "time": self._parse_time(time_value),
                "open": float(open_value),
                "high": float(high_value),
                "low": float(low_value),
                "close": float(close_value),
            })

        normalized.sort(key=lambda item: item["time"])
        return normalized

    @staticmethod
    def _as_mapping(
        record: Any,
    ) -> dict[str, Any]:
        if isinstance(record, dict):
            return record

        if hasattr(record, "_asdict"):
            return dict(record._asdict())

        if hasattr(record, "keys"):
            try:
                return {
                    key: record[key]
                    for key in record.keys()
                }
            except Exception:
                return {}

        return {}

    @staticmethod
    def _parse_time(
        value: Any,
    ) -> datetime:
        if isinstance(value, datetime):
            return value

        if hasattr(value, "to_pydatetime"):
            return value.to_pydatetime()

        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value))

        text = str(value)

        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass

        for pattern in (
            "%Y-%m-%d %H:%M:%S",
            "%Y.%m.%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                return datetime.strptime(text, pattern)
            except ValueError:
                continue

        raise ValueError(
            f"Nem értelmezhető gyertyaidő: {text}"
        )

    @staticmethod
    def _candle_width(
        x_values: list[float],
    ) -> float:
        if len(x_values) < 2:
            return 0.002

        distances = [
            x_values[index] - x_values[index - 1]
            for index in range(1, len(x_values))
            if x_values[index] > x_values[index - 1]
        ]

        if not distances:
            return 0.002

        return min(distances) * 0.65

    @staticmethod
    def _safe_filename(value: str) -> str:
        return "".join(
            character
            if character.isalnum() or character in {"-", "_"}
            else "_"
            for character in value
        )

    @staticmethod
    def _format_price(value: float) -> str:
        formatted = f"{float(value):.2f}"
        return formatted.rstrip("0").rstrip(".")
