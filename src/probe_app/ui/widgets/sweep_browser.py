from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from probe_app.application.state import SweepRunStatus
from probe_app.domain.models.sweep import (
    Sweep,
    SweepDirection,
    SweepExclusion,
    SweepExclusionReason,
)

SWEEP_ID_ROLE = int(Qt.ItemDataRole.UserRole)


class SweepBrowser(QWidget):
    """Display the complete sweep list without copying waveform arrays."""

    sweep_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sweeps: dict[str, Sweep] = {}
        self._exclusions: tuple[SweepExclusion, ...] = ()

        self._summary = QLabel("Sweep分割を実行すると一覧を表示します")
        self._summary.setObjectName("sweepSummary")
        self._summary.setWordWrap(True)

        self._position = QLabel("0 / 0")
        self._position.setObjectName("sweepPosition")
        self._position.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._tree = QTreeWidget()
        self._tree.setObjectName("sweepBrowser")
        self._tree.setHeaderLabels(
            [
                "No.",
                "方向",
                "電圧開始 [s]",
                "電圧終了 [s]",
                "点数",
                "電圧範囲 [V]",
            ]
        )
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

        self._issues_heading = QLabel("未分割・除外区間")
        self._issues_heading.setObjectName("sweepExclusionHeading")
        self._issues_heading.setStyleSheet("color: #9a3412; font-weight: 600;")
        self._issues_heading.hide()

        self._issues_tree = QTreeWidget()
        self._issues_tree.setObjectName("sweepExclusionBrowser")
        self._issues_tree.setHeaderLabels(
            ["sample範囲", "時間範囲 [s]", "点数", "理由"]
        )
        self._issues_tree.setAlternatingRowColors(True)
        self._issues_tree.setUniformRowHeights(True)
        self._issues_tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        issues_header = self._issues_tree.header()
        for column in range(self._issues_tree.columnCount() - 1):
            issues_header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        issues_header.setSectionResizeMode(
            self._issues_tree.columnCount() - 1,
            QHeaderView.ResizeMode.Stretch,
        )
        self._issues_tree.setMaximumHeight(150)
        self._issues_tree.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        header_layout = QHBoxLayout()
        header_layout.addWidget(self._summary, 1)
        header_layout.addWidget(self._position)
        layout.addLayout(header_layout)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._issues_heading)
        layout.addWidget(self._issues_tree)

    @property
    def sweep_count(self) -> int:
        return len(self._sweeps)

    @property
    def exclusion_count(self) -> int:
        return len(self._exclusions)

    @property
    def selected_sweep(self) -> Sweep | None:
        item: QTreeWidgetItem | None = self._tree.currentItem()
        if item is None:
            return None
        return self._sweeps.get(item.data(0, SWEEP_ID_ROLE))

    @property
    def selected_index(self) -> int | None:
        item: QTreeWidgetItem | None = self._tree.currentItem()
        if item is None:
            return None
        index = self._tree.indexOfTopLevelItem(item)
        return index if index >= 0 else None

    @property
    def can_select_previous(self) -> bool:
        index = self.selected_index
        return index is not None and index > 0

    @property
    def can_select_next(self) -> bool:
        index = self.selected_index
        return index is not None and index < self._tree.topLevelItemCount() - 1

    def clear_sweeps(self, message: str = "Sweep分割を実行すると一覧を表示します") -> None:
        self._sweeps.clear()
        self._exclusions = ()
        self._tree.clear()
        self._issues_tree.clear()
        self._issues_heading.hide()
        self._issues_tree.hide()
        self._summary.setText(message)
        self._update_position()

    def set_sweeps(self, sweeps: Iterable[Sweep], *, message: str = "") -> None:
        self.set_results(sweeps, (), message=message)

    def set_results(
        self,
        sweeps: Iterable[Sweep],
        exclusions: Iterable[SweepExclusion],
        *,
        message: str = "",
    ) -> None:
        sweep_items = tuple(sweeps)
        exclusion_items = tuple(exclusions)
        self._sweeps = {sweep.sweep_id: sweep for sweep in sweep_items}
        self._exclusions = exclusion_items
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
        self._render_exclusions()
        if first_item is not None:
            self._tree.setCurrentItem(first_item)
        else:
            self._update_position()

    def render_state(
        self,
        status: SweepRunStatus,
        sweeps: tuple[Sweep, ...],
        exclusions: tuple[SweepExclusion, ...],
        message: str,
    ) -> None:
        if status is SweepRunStatus.SUCCEEDED:
            current_ids = tuple(self._sweeps)
            incoming_ids = tuple(sweep.sweep_id for sweep in sweeps)
            current_exclusions = tuple(
                (
                    item.source_start_index,
                    item.source_stop_index,
                    item.reason,
                )
                for item in self._exclusions
            )
            incoming_exclusions = tuple(
                (
                    item.source_start_index,
                    item.source_stop_index,
                    item.reason,
                )
                for item in exclusions
            )
            if current_ids != incoming_ids or current_exclusions != incoming_exclusions:
                self.set_results(sweeps, exclusions, message=message)
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

    def select_previous(self) -> bool:
        return self._move_selection(-1)

    def select_next(self) -> bool:
        return self._move_selection(1)

    def _move_selection(self, offset: int) -> bool:
        index = self.selected_index
        if index is None:
            return False
        target_index = index + offset
        if not 0 <= target_index < self._tree.topLevelItemCount():
            return False
        target = self._tree.topLevelItem(target_index)
        if target is None:
            return False
        self._tree.setCurrentItem(target)
        self._tree.scrollToItem(target)
        return True

    def _emit_selection(self) -> None:
        self._update_position()
        sweep = self.selected_sweep
        if sweep is not None:
            self.sweep_selected.emit(sweep)

    def _update_position(self) -> None:
        index = self.selected_index
        current = 0 if index is None else index + 1
        self._position.setText(f"{current:,} / {self.sweep_count:,}")

    def _render_exclusions(self) -> None:
        self._issues_tree.clear()
        for exclusion in self._exclusions:
            item = QTreeWidgetItem(
                [
                    (
                        f"{exclusion.source_start_index:,}"
                        f"–{exclusion.source_stop_index - 1:,}"
                    ),
                    (
                        f"{_format_float(exclusion.start_time_s)}"
                        f" – {_format_float(exclusion.end_time_s)}"
                    ),
                    f"{exclusion.point_count:,}",
                    _exclusion_label(exclusion.reason),
                ]
            )
            item.setToolTip(3, exclusion.detail)
            self._issues_tree.addTopLevelItem(item)
        visible = bool(self._exclusions)
        self._issues_heading.setVisible(visible)
        self._issues_tree.setVisible(visible)


def _direction_label(direction: SweepDirection) -> str:
    return "↑ 上昇" if direction is SweepDirection.UP else "↓ 下降"


def _exclusion_label(reason: SweepExclusionReason) -> str:
    return {
        SweepExclusionReason.ALIGNMENT_PREFIX: "先頭の周期合わせ",
        SweepExclusionReason.ALIGNMENT_SUFFIX: "末尾の周期合わせ",
        SweepExclusionReason.INCOMPLETE_SWEEP: "短い未完了Sweep",
    }[reason]


def _format_float(value: float) -> str:
    return f"{value:.8g}"
