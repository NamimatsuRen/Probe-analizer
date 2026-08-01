from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget

from probe_app.domain.models.summary import (
    SUMMARY_METHOD_ORDER,
    SummaryAggregateSnapshot,
    SummaryMethod,
    SummaryMetric,
)

_COLORS = {
    SummaryMethod.FILTERED_LOG: "#2563eb",
    SummaryMethod.FILTERED_DERIVATIVE: "#ea580c",
    SummaryMethod.RAW_LOG: "#16a34a",
    SummaryMethod.RAW_DERIVATIVE: "#9333ea",
}

_LABELS = {
    SummaryMethod.FILTERED_LOG: "Filtered / log交点",
    SummaryMethod.FILTERED_DERIVATIVE: "Filtered / dI/dV",
    SummaryMethod.RAW_LOG: "Raw / log交点",
    SummaryMethod.RAW_DERIVATIVE: "Raw / 多窓dI/dV",
}


class SummaryAggregatePlot(QWidget):
    """Read-only shot/position means with optional real sample deviations."""

    def __init__(self, metric: SummaryMetric, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._metric = metric
        self._plot = pg.PlotWidget()
        self._plot.setBackground("w")
        self._plot.showGrid(x=True, y=True, alpha=0.18)
        self._plot.addLegend(offset=(8, 8))
        self._plot.setLabel(
            "left",
            "T_i" if metric is SummaryMetric.TI else "Phi",
            units="eV" if metric is SummaryMetric.TI else "V",
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot)

    def render_snapshot(self, snapshot: SummaryAggregateSnapshot | None) -> None:
        self._plot.clear()
        legend = self._plot.plotItem.legend
        if legend is not None:
            legend.clear()
        if snapshot is None:
            self._plot.setTitle("複数shot結果がありません")
            return
        x_label = snapshot.x_label
        if snapshot.x_unit:
            x_label = f"{x_label} [{snapshot.x_unit}]"
        self._plot.setLabel("bottom", x_label)
        self._plot.setTitle(
            ("T_i" if self._metric is SummaryMetric.TI else "Phi")
            + " — "
            + ("shot比較" if snapshot.kind.value == "loaded_shots" else "位置依存")
        )
        for method in SUMMARY_METHOD_ORDER:
            points = snapshot.points_for(self._metric, method)
            if not points:
                continue
            x_values = [point.x_value for point in points]
            y_values = [point.mean for point in points]
            color = _COLORS[method]
            self._plot.plot(
                x_values,
                y_values,
                pen=pg.mkPen(color, width=1.6),
                symbol="o",
                symbolSize=8,
                symbolPen=pg.mkPen(color),
                symbolBrush=pg.mkBrush(color),
                name=_LABELS[method],
            )
            error_points = tuple(point for point in points if point.sample_std is not None)
            if error_points:
                error_item = pg.ErrorBarItem(
                    x=[point.x_value for point in error_points],
                    y=[point.mean for point in error_points],
                    top=[point.sample_std for point in error_points],
                    bottom=[point.sample_std for point in error_points],
                    beam=0.15,
                    pen=pg.mkPen(color, width=1),
                )
                self._plot.addItem(error_item)
        if self._metric is SummaryMetric.TI:
            self._plot.setYRange(0.0, 5.0, padding=0.02)
        else:
            self._plot.enableAutoRange(axis="y", enable=True)
        self._plot.enableAutoRange(axis="x", enable=True)
