from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from probe_app.application.state import SweepRunStatus
from probe_app.domain.services.sweep_splitter import LegacySweepSplitParameters


class SweepSplitPanel(QWidget):
    """Small, explicit replacement for legacy JSON sweep settings."""

    run_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ready = False
        self._running = False

        self._points_per_cycle = QSpinBox()
        self._points_per_cycle.setObjectName("pointsPerCycle")
        self._points_per_cycle.setRange(2, 100_000_000)
        self._points_per_cycle.setSingleStep(2)
        self._points_per_cycle.setValue(20_000)
        self._points_per_cycle.setToolTip("1周期に含まれるサンプル点数（偶数）")

        self._sample_start = QSpinBox()
        self._sample_start.setObjectName("sampleStart")
        self._sample_start.setRange(0, 100_000_000)
        self._sample_start.setValue(0)

        self._use_all_remaining = QCheckBox("末尾まで使う")
        self._use_all_remaining.setChecked(True)
        self._sample_stop = QSpinBox()
        self._sample_stop.setObjectName("sampleStop")
        self._sample_stop.setRange(1, 100_000_000)
        self._sample_stop.setValue(500_000)
        self._sample_stop.setEnabled(False)

        self._run_button = QPushButton("Sweep分割を実行")
        self._run_button.setObjectName("runSweepSplit")
        self._cancel_button = QPushButton("分割をキャンセル")
        self._cancel_button.setObjectName("cancelSweepSplit")
        self._status = QLabel("解析系列の役割を選択してください")
        self._status.setWordWrap(True)

        form = QFormLayout()
        form.addRow("1周期の点数", self._points_per_cycle)
        form.addRow("開始sample", self._sample_start)
        stop_row = QHBoxLayout()
        stop_row.addWidget(self._use_all_remaining)
        stop_row.addWidget(self._sample_stop, 1)
        form.addRow("終了sample", stop_row)

        buttons = QHBoxLayout()
        buttons.addWidget(self._run_button)
        buttons.addWidget(self._cancel_button)

        group = QGroupBox("Sweep分割")
        group_layout = QVBoxLayout(group)
        group_layout.addLayout(form)
        group_layout.addLayout(buttons)
        group_layout.addWidget(self._status)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(group)
        layout.addStretch(1)

        self._use_all_remaining.toggled.connect(self._all_remaining_toggled)
        self._run_button.clicked.connect(self.run_requested)
        self._cancel_button.clicked.connect(self.cancel_requested)
        self.render_state(SweepRunStatus.IDLE, self._status.text(), ready=False)

    def parameters(self) -> LegacySweepSplitParameters:
        return LegacySweepSplitParameters(
            points_per_cycle=self._points_per_cycle.value(),
            sample_start=self._sample_start.value(),
            sample_stop=(
                None if self._use_all_remaining.isChecked() else self._sample_stop.value()
            ),
        )

    def set_parameters(self, parameters: LegacySweepSplitParameters) -> None:
        self._points_per_cycle.setValue(parameters.points_per_cycle)
        self._sample_start.setValue(parameters.sample_start)
        use_all = parameters.sample_stop is None
        self._use_all_remaining.setChecked(use_all)
        if parameters.sample_stop is not None:
            self._sample_stop.setValue(parameters.sample_stop)

    def render_state(
        self,
        status: SweepRunStatus,
        message: str,
        *,
        ready: bool,
        details: str = "",
    ) -> None:
        self._ready = ready
        self._running = status is SweepRunStatus.RUNNING
        self._run_button.setEnabled(self._ready and not self._running)
        self._cancel_button.setEnabled(self._running)
        for control in (
            self._points_per_cycle,
            self._sample_start,
            self._use_all_remaining,
        ):
            control.setEnabled(not self._running)
        self._sample_stop.setEnabled(
            not self._running and not self._use_all_remaining.isChecked()
        )
        color = {
            SweepRunStatus.ERROR: "#b42318",
            SweepRunStatus.SUCCEEDED: "#067647",
            SweepRunStatus.RUNNING: "#175cd3",
        }.get(status, "#556070")
        self._status.setStyleSheet(f"color: {color};")
        self._status.setText(message)
        self._status.setToolTip(details)

    def _all_remaining_toggled(self, checked: bool) -> None:
        self._sample_stop.setEnabled(not checked and not self._running)
