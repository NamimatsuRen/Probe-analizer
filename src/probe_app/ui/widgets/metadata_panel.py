from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

from probe_app.domain.models.raw_series import RawSeries, RawSeriesDescriptor


def _number(value: float, unit: str = "") -> str:
    if not math.isfinite(value):
        return "—"
    suffix = f" {unit}" if unit else ""
    return f"{value:.6g}{suffix}"


class MetadataPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fields: dict[str, QLabel] = {}
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        for key, label in (
            ("series", "系列"),
            ("shot", "Shot / フォルダ"),
            ("source", "元ファイル"),
            ("points", "点数"),
            ("time", "時間範囲"),
            ("value", "信号範囲"),
            ("recorded", "記録日時"),
            ("format", "形式"),
        ):
            value = QLabel("—")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            self._fields[key] = value
            form.addRow(label, value)

    def clear(self) -> None:
        for field in self._fields.values():
            field.setText("—")

    def show_loading(self, descriptor: RawSeriesDescriptor) -> None:
        self.clear()
        self._fields["series"].setText(descriptor.display_name)
        self._fields["shot"].setText(descriptor.shot_id)
        self._fields["source"].setText(descriptor.data_path.name)
        self._fields["points"].setText(f"{descriptor.sample_count:,}")
        self._fields["recorded"].setText(descriptor.recorded_at or "—")
        self._fields["format"].setText(
            f"{descriptor.metadata.get('data_type', '—')} / "
            f"{descriptor.metadata.get('endian', '—')}"
        )

    def show_series(self, series: RawSeries) -> None:
        descriptor = series.descriptor
        self.show_loading(descriptor)
        start, end = series.time_range_s
        low, high = series.value_range
        self._fields["points"].setText(f"{series.point_count:,}")
        self._fields["time"].setText(
            f"{_number(start * 1_000.0, 'ms')} ～ "
            f"{_number(end * 1_000.0, 'ms')}"
        )
        unit = descriptor.value_unit
        self._fields["value"].setText(f"{_number(low, unit)} ～ {_number(high, unit)}")
