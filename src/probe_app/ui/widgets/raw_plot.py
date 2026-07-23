from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget

from probe_app.domain.models.raw_series import RawSeries
from probe_app.ui.downsampling import min_max_downsample


class RawPlot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._plot = pg.PlotWidget()
        self._plot.setBackground("w")
        self._plot.showGrid(x=True, y=True, alpha=0.2)
        self._plot.setTitle("Raw波形")
        self._plot.setLabel("bottom", "Time", units="s")
        self._plot.setLabel("left", "Signal")
        self._plot.getPlotItem().setMenuEnabled(True)
        self._plot.getViewBox().setMouseMode(pg.ViewBox.RectMode)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot)

    def clear_plot(self, message: str = "系列を選択してください") -> None:
        self._plot.clear()
        self._plot.setTitle(message)

    def show_series(self, series: RawSeries) -> None:
        x, y = min_max_downsample(series.time_s, series.values)
        self._plot.clear()
        self._plot.plot(x, y, pen=pg.mkPen("#2563eb", width=1.2), antialias=False)
        self._plot.setTitle(series.descriptor.display_name)
        self._plot.setLabel("bottom", "Time", units="s")
        self._plot.setLabel(
            "left",
            "Signal",
            units=series.descriptor.value_unit or None,
        )
        self._plot.enableAutoRange()
