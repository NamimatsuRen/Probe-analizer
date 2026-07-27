from __future__ import annotations

import math

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from probe_app.domain.models.summary import (
    SUMMARY_METHOD_ORDER,
    SummaryMethod,
    SummaryMetric,
    SummarySnapshot,
)

_METHOD_LABELS = {
    SummaryMethod.FILTERED_LOG: "Filtered / log交点",
    SummaryMethod.FILTERED_DERIVATIVE: "Filtered / dI/dV",
    SummaryMethod.RAW_LOG: "Raw / log交点",
    SummaryMethod.RAW_DERIVATIVE: "Raw / 多窓dI/dV",
}

_METHOD_COLORS = {
    SummaryMethod.FILTERED_LOG: "#2563eb",
    SummaryMethod.FILTERED_DERIVATIVE: "#ea580c",
    SummaryMethod.RAW_LOG: "#16a34a",
    SummaryMethod.RAW_DERIVATIVE: "#9333ea",
}


class SummaryTrendPlot(QWidget):
    """Method-by-method Sweep trend with excluded values kept in gray."""

    sweep_selected = Signal(str)

    def __init__(
        self,
        metric: SummaryMetric,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._metric = metric
        self._snapshot: SummarySnapshot | None = None
        self._selected_line: pg.InfiniteLine | None = None
        self._plot = pg.PlotWidget()
        self._plot.setBackground("w")
        self._plot.showGrid(x=True, y=True, alpha=0.18)
        self._plot.setLabel("bottom", "Sweep No.")
        if metric is SummaryMetric.TI:
            self._plot.setLabel("left", "T_i", units="eV")
            self._plot.setTitle("T_i — Sweep推移")
        else:
            self._plot.setLabel("left", "Phi", units="V")
            self._plot.setTitle("Phi（プラズマ電位）— Sweep推移")
        self._plot.addLegend(offset=(8, 8))
        self._plot.setMinimumHeight(230)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot)

    @property
    def plotted_point_count(self) -> int:
        if self._snapshot is None:
            return 0
        return sum(
            len(self._snapshot.plot_points(self._metric, method))
            for method in SUMMARY_METHOD_ORDER
        )

    def render_snapshot(
        self,
        snapshot: SummarySnapshot | None,
        *,
        selected_sweep_id: str | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._plot.clear()
        legend = self._plot.plotItem.legend
        if legend is not None:
            legend.clear()
        self._selected_line = None
        if snapshot is None:
            self._set_empty_title()
            return
        self._set_active_title()

        for method in SUMMARY_METHOD_ORDER:
            points = snapshot.plot_points(self._metric, method)
            included = tuple(point for point in points if point.included)
            excluded = tuple(point for point in points if not point.included)
            if included:
                values_by_number = {point.number: point.value for point in included}
                x_values = [row.number for row in snapshot.rows]
                y_values = [
                    values_by_number.get(number, math.nan) for number in x_values
                ]
                color = _METHOD_COLORS[method]
                self._plot.plot(
                    x_values,
                    y_values,
                    pen=pg.mkPen(color, width=1.8),
                    name=_METHOD_LABELS[method],
                    connect="finite",
                )
                scatter = pg.ScatterPlotItem(
                    x=[point.number for point in included],
                    y=[point.value for point in included],
                    data=[point.sweep_id for point in included],
                    size=8,
                    symbol="o",
                    pen=pg.mkPen(color, width=1),
                    brush=pg.mkBrush(color),
                )
                scatter.sigClicked.connect(self._points_clicked)
                self._plot.addItem(scatter)
            if excluded:
                gray = pg.ScatterPlotItem(
                    x=[point.number for point in excluded],
                    y=[point.value for point in excluded],
                    data=[point.sweep_id for point in excluded],
                    size=9,
                    symbol="x",
                    pen=pg.mkPen("#98a2b3", width=1.5),
                    brush=pg.mkBrush(None),
                )
                gray.sigClicked.connect(self._points_clicked)
                self._plot.addItem(gray)

        if self._metric is SummaryMetric.TI:
            self._plot.setYRange(0.0, 5.0, padding=0.02)
        else:
            self._plot.enableAutoRange(axis="y", enable=True)
        self._plot.enableAutoRange(axis="x", enable=True)
        self.select_sweep(selected_sweep_id)

    def select_sweep(self, sweep_id: str | None) -> None:
        if self._selected_line is not None:
            self._plot.removeItem(self._selected_line)
            self._selected_line = None
        if self._snapshot is None or sweep_id is None:
            return
        row = next(
            (row for row in self._snapshot.rows if row.sweep_id == sweep_id),
            None,
        )
        if row is None:
            return
        self._selected_line = pg.InfiniteLine(
            pos=float(row.number),
            angle=90,
            movable=False,
            pen=pg.mkPen(
                "#344054",
                width=1,
                style=Qt.PenStyle.DashLine,
            ),
        )
        self._plot.addItem(self._selected_line)

    def _points_clicked(
        self,
        _item: pg.ScatterPlotItem,
        points: list[pg.SpotItem],
        _event: object,
    ) -> None:
        if not points:
            return
        sweep_id = points[0].data()
        if isinstance(sweep_id, str):
            self.sweep_selected.emit(sweep_id)

    def _set_empty_title(self) -> None:
        if self._metric is SummaryMetric.TI:
            self._plot.setTitle("T_i — 解析済みSweepがありません")
        else:
            self._plot.setTitle("Phi — 解析済みSweepがありません")

    def _set_active_title(self) -> None:
        if self._metric is SummaryMetric.TI:
            self._plot.setTitle("T_i — Sweep推移")
        else:
            self._plot.setTitle("Phi（プラズマ電位）— Sweep推移")
