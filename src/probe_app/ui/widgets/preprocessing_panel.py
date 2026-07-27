from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from probe_app.analysis import PreprocessedSweep, SavitzkyGolaySettings


class PreprocessingPanel(QWidget):
    """Controls and diagnostics for selected-Sweep preprocessing."""

    run_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_sweep_id: str | None = None
        self._result: PreprocessedSweep | None = None

        self._window_length = QSpinBox()
        self._window_length.setObjectName("savgolWindowLength")
        self._window_length.setRange(1, 100_001)
        self._window_length.setSingleStep(2)
        self._window_length.setValue(501)
        self._window_length.setToolTip(
            "Savitzky–Golay窓の点数です。データより長い場合は有効な奇数へ自動調整します。"
        )

        self._polyorder = QSpinBox()
        self._polyorder.setObjectName("savgolPolyorder")
        self._polyorder.setRange(0, 9)
        self._polyorder.setValue(3)
        self._polyorder.setToolTip("局所多項式の次数です。既定値はlegacyと同じ3次です。")

        self._run_button = QPushButton("前処理を再計算")
        self._run_button.setObjectName("runPreprocessing")
        self._run_button.setEnabled(False)
        self._run_button.clicked.connect(self._emit_request)

        self._status = QLabel("Sweepを選択して前処理を実行してください")
        self._status.setObjectName("preprocessingStatus")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #556070;")

        form = QFormLayout()
        form.addRow("SG窓 [点]", self._window_length)
        form.addRow("多項式次数", self._polyorder)

        group = QGroupBox("Savitzky–Golay平滑化・微分")
        group_layout = QVBoxLayout(group)
        group_layout.addLayout(form)
        group_layout.addWidget(self._run_button)
        group_layout.addWidget(self._status)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(group)
        layout.addStretch(1)

    @property
    def selected_sweep_id(self) -> str | None:
        return self._selected_sweep_id

    @property
    def result(self) -> PreprocessedSweep | None:
        return self._result

    @property
    def description(self) -> str:
        return self._status.text()

    def settings(self) -> SavitzkyGolaySettings:
        return SavitzkyGolaySettings(
            window_length=self._window_length.value(),
            polyorder=self._polyorder.value(),
        )

    def set_settings(self, settings: SavitzkyGolaySettings) -> None:
        self._window_length.setValue(settings.window_length)
        self._polyorder.setValue(settings.polyorder)

    def select_sweep(self, sweep_id: str) -> None:
        if not sweep_id.strip():
            raise ValueError("sweep_id cannot be empty")
        if self._selected_sweep_id == sweep_id and self._result is not None:
            return
        self._selected_sweep_id = sweep_id
        self._result = None
        self._run_button.setEnabled(True)
        self._status.setStyleSheet("color: #556070;")
        self._status.setText(
            f"{sweep_id}\n未実行です。設定を確認して「前処理を再計算」を押してください。"
        )
        self._status.setToolTip("")

    def clear(self, message: str = "Sweepを選択して前処理を実行してください") -> None:
        self._selected_sweep_id = None
        self._result = None
        self._run_button.setEnabled(False)
        self._status.setStyleSheet("color: #556070;")
        self._status.setText(message)
        self._status.setToolTip("")

    def show_result(self, result: PreprocessedSweep) -> None:
        self._selected_sweep_id = result.sweep_id
        self._result = result
        self._run_button.setEnabled(True)
        warning = result.spacing_warning
        color = "#9a3412" if warning else "#067647"
        self._status.setStyleSheet(f"color: {color};")
        message = (
            f"{result.sweep_id}\n"
            f"Raw / Filtered / dI/dV: {result.voltage_v.size:,} 点 ｜ "
            f"SG窓 {result.used_window_length:,} 点"
        )
        if result.used_window_length != result.requested_window_length:
            message += f"（指定 {result.requested_window_length:,} 点から自動調整）"
        message += (
            f" ｜ {result.polyorder}次 ｜ "
            f"平均電圧刻み {result.voltage_step_v:.8g} V"
        )
        if warning:
            message += f"\n⚠ {warning}"
        self._status.setText(message)
        self._status.setToolTip(warning)

    def show_error(self, sweep_id: str, message: str) -> None:
        self._selected_sweep_id = sweep_id
        self._result = None
        self._run_button.setEnabled(True)
        self._status.setStyleSheet("color: #b42318;")
        self._status.setText(
            f"{sweep_id}\n前処理できません: {message}\n"
            "SG窓または多項式次数を変更して再計算してください。"
        )
        self._status.setToolTip(message)

    def _emit_request(self) -> None:
        try:
            settings = self.settings()
        except ValueError as error:
            if self._selected_sweep_id is not None:
                self.show_error(self._selected_sweep_id, str(error))
            return
        self.run_requested.emit(settings)
