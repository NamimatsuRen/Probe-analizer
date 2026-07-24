from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from probe_app.analysis import summarize_sweep
from probe_app.domain.models.sweep import Sweep


class AnalysisPreviewPanel(QWidget):
    """Read-only seam proving a Level 3 analysis can consume the selected Sweep."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_sweep: Sweep | None = None

        heading = QLabel("Level 3 接続プレビュー")
        heading.setStyleSheet("font-weight: 600;")
        self._message = QLabel("Sweepを選択すると解析層の入力概要を表示します")
        self._message.setObjectName("analysisPreviewMessage")
        self._message.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(heading)
        layout.addWidget(self._message)
        layout.addStretch(1)

    @property
    def selected_sweep(self) -> Sweep | None:
        return self._selected_sweep

    @property
    def description(self) -> str:
        return self._message.text()

    def clear(self, message: str = "Sweepを選択すると解析層の入力概要を表示します") -> None:
        self._selected_sweep = None
        self._message.setText(message)

    def show_sweep(self, sweep: Sweep) -> None:
        self._selected_sweep = sweep
        preview = summarize_sweep(sweep)
        step = (
            "—"
            if preview.median_voltage_step_v is None
            else f"{preview.median_voltage_step_v:.8g} V"
        )
        self._message.setText(
            f"{sweep.sweep_id}\n"
            f"{preview.point_count:,} 点 ｜ "
            f"電圧 {preview.voltage_min_v:.8g}–{preview.voltage_max_v:.8g} V ｜ "
            f"電流 {preview.current_min_a:.8g}–{preview.current_max_a:.8g} A ｜ "
            f"電圧刻み中央値 {step}\n"
            "この表示はreaderを再実行せず、選択済みSweepだけを解析層へ渡しています。"
        )
