from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from probe_app.application.state import SweepRunStatus
from probe_app.domain.models.sweep import Sweep, SweepDirection

SWEEP_ID_ROLE = int(Qt.ItemDataRole.UserRole)


class SweepBrowser(QWidget):
    """Display the complete sweep list without copying waveform arrays."""

    sweep_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sweeps: dict[str, Sweep] = {}

        self._summary = QLabel("Sweep分割を実行すると一覧を表示します")
        self._summary.setObjectName("sweepSummary")
        self._summary.setWordWrap(True)

        self._tree = QTreeWidget()
        self._tree.setObjectName("sweepBrowser")
        self._tree.setHeaderLabels(["No.", "方向", "開始 [s]", "終了 [s]", "点数", "電圧範囲 [V]"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.itemSelectionChanged.connect(self._emit_selection)
        header = self._tree.header()
        for column in range(self._tree.columnCount() - 1):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            self._tree.columnCount() - 1,
            QHeaderView.ResizeMode.Stretch,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._summary)
        layout.addWidget(self._tree, 1)

    @property
    def sweep_count(self) -> int:
        return len(self._sweeps)

    @property
    def selected_sweep(self) -> Sweep | None:
        item: QTreeWidgetItem | None = self._tree.currentItem()
        if item is None:
            return None
        return self._sweeps.get(item.data(0, SWEEP_ID_ROLE))

    def clear_sweeps(self, message: str = "Sweep分割を実行すると一覧を表示します") -> None:
        self._sweeps.clear()
        self._tree.clear()
        self._summary.setText(message)

    def set_sweeps(self, sweeps: Iterable[Sweep], *, message: str = "") -> None:
        sweep_items = tuple(sweeps)
        self._sweeps = {sweep.sweep_id: sweep for sweep in sweep_items}
        self._tree.clear()

        first_item: QTreeWidgetItem | None = None
        for number, sweep in enumerate(sweep_items, start=1):
            voltage_min = float(np.min(sweep.voltage_v))
            voltage_max = float(np.max(sweep.voltage_v))
            item = QTreeWidgetItem(
                [
                    str(number),
                    _direction_label(sweep.direction),
                    _format_float(float(sweep.time_s[0])),
                    _format_float(float(sweep.time_s[-1])),
                    f"{sweep.point_count:,}",
                    f"{_format_float(voltage_min)} – {_format_float(voltage_max)}",
                ]
            )
            item.setData(0, SWEEP_ID_ROLE, sweep.sweep_id)
            item.setToolTip(
                0,
                (
                    f"{sweep.sweep_id}\n"
                    f"source sample: {sweep.source_start_index:,}"
                    f"–{sweep.source_stop_index - 1:,}"
                ),
            )
            self._tree.addTopLevelItem(item)
            if first_item is None:
                first_item = item

        summary = message or f"{len(sweep_items):,} Sweep"
        self._summary.setText(summary)
        if first_item is not None:
            self._tree.setCurrentItem(first_item)

    def render_state(
        self,
        status: SweepRunStatus,
        sweeps: tuple[Sweep, ...],
        message: str,
    ) -> None:
        if status is SweepRunStatus.SUCCEEDED:
            current_ids = tuple(self._sweeps)
            incoming_ids = tuple(sweep.sweep_id for sweep in sweeps)
            if current_ids != incoming_ids:
                self.set_sweeps(sweeps, message=message)
            else:
                self._summary.setText(message)
            return
        if self._sweeps or self._tree.topLevelItemCount():
            self.clear_sweeps(message)
        else:
            self._summary.setText(message)

    def select_sweep(self, sweep_id: str) -> bool:
        if sweep_id not in self._sweeps:
            return False
        for index in range(self._tree.topLevelItemCount()):
            item: QTreeWidgetItem | None = self._tree.topLevelItem(index)
            if item is None:
                continue
            if item.data(0, SWEEP_ID_ROLE) == sweep_id:
                self._tree.setCurrentItem(item)
                return True
        return False

    def _emit_selection(self) -> None:
        sweep = self.selected_sweep
        if sweep is not None:
            self.sweep_selected.emit(sweep)


def _direction_label(direction: SweepDirection) -> str:
    return "↑ 上昇" if direction is SweepDirection.UP else "↓ 下降"


def _format_float(value: float) -> str:
    return f"{value:.8g}"
