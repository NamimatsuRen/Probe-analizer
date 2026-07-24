from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from probe_app.domain.models.raw_series import FloatArray
from probe_app.domain.models.sweep import Sweep, SweepDirection


class SweepIVPlot(QWidget):
    """Plot one selected sweep in voltage-ascending I–V order."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_sweep: Sweep | None = None
        self._curve: pg.PlotDataItem | None = None
        self._start_marker: pg.PlotDataItem | None = None
        self._end_marker: pg.PlotDataItem | None = None

        self._selection_info = QLabel("Sweep分割後に一覧から選択してください")
        self._selection_info.setObjectName("sweepIvSelectionInfo")
        self._selection_info.setWordWrap(True)
        self._selection_info.setStyleSheet(
            "background: #eef4ff; color: #173b6c; padding: 5px 8px;"
            " border-bottom: 1px solid #b7cdf5;"
        )

        self._plot = pg.PlotWidget()
        self._plot.setObjectName("sweepIvPlot")
        self._plot.setBackground("w")
        self._plot.showGrid(x=True, y=True, alpha=0.2)
        self._plot.setTitle("Sweep I–V")
        self._plot.setLabel("bottom", "Voltage", units="V")
        self._plot.setLabel("left", "Current", units="A")
        self._plot.getPlotItem().setMenuEnabled(True)
        self._plot.getViewBox().setMouseMode(pg.ViewBox.RectMode)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._selection_info)
        layout.addWidget(self._plot, 1)

    @property
    def selected_sweep(self) -> Sweep | None:
        return self._selected_sweep

    @property
    def displayed_voltage_v(self) -> FloatArray | None:
        if self._selected_sweep is None:
            return None
        return self._selected_sweep.iv_voltage_v

    @property
    def displayed_current_a(self) -> FloatArray | None:
        if self._selected_sweep is None:
            return None
        return self._selected_sweep.iv_current_a

    @property
    def description(self) -> str:
        return self._selection_info.text()

    def clear_plot(self, message: str = "Sweep分割後に一覧から選択してください") -> None:
        self._selected_sweep = None
        self._curve = None
        self._start_marker = None
        self._end_marker = None
        self._plot.clear()
        self._plot.setTitle("Sweep I–V")
        self._selection_info.setText(message)

    def show_sweep(self, sweep: Sweep) -> None:
        self._selected_sweep = sweep
        self._plot.clear()
        direction = "上昇" if sweep.direction is SweepDirection.UP else "下降"
        color = "#2563eb" if sweep.direction is SweepDirection.UP else "#d97706"
        self._curve = self._plot.plot(
            sweep.iv_voltage_v,
            sweep.iv_current_a,
            pen=pg.mkPen(color, width=1.5),
            antialias=False,
        )
        self._start_marker = self._plot.plot(
            [float(sweep.voltage_v[0])],
            [float(sweep.current_a[0])],
            pen=None,
            symbol="o",
            symbolSize=8,
            symbolBrush="#16a34a",
            symbolPen="#166534",
        )
        self._end_marker = self._plot.plot(
            [float(sweep.voltage_v[-1])],
            [float(sweep.current_a[-1])],
            pen=None,
            symbol="s",
            symbolSize=8,
            symbolBrush="#dc2626",
            symbolPen="#991b1b",
        )
        self._plot.setTitle(f"Sweep I–V — {direction}")
        self._plot.setLabel("bottom", "Voltage", units="V")
        self._plot.setLabel("left", "Current", units="A")
        self._plot.enableAutoRange()
        self._selection_info.setText(
            f"選択Sweep: {sweep.sweep_id} ｜ 取得方向: {direction} ｜ "
            f"current: {sweep.current_series_id} [A] ｜ "
            f"voltage: {sweep.voltage_series_id} [V] ｜ "
            f"{sweep.point_count:,} 点 ｜ ● 始点 / ■ 終点"
        )
