from __future__ import annotations

import math

import pyqtgraph as pg
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from probe_app.domain.models.raw_series import RawSeries
from probe_app.domain.models.sweep import Sweep, SweepDirection
from probe_app.ui.downsampling import min_max_downsample
from probe_app.ui.plot_policy import add_zero_reference, constrain_y_to_data


class RawPlot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._highlighted_sweep: Sweep | None = None
        self._sweep_region: pg.LinearRegionItem | None = None
        self._displayed_series_id: str | None = None
        self._preview_current_time_offset_s: float | None = None
        self._zero_line: pg.InfiniteLine | None = None

        self._selection_info = QLabel()
        self._selection_info.setObjectName("rawSweepSelectionInfo")
        self._selection_info.setWordWrap(True)
        self._selection_info.setStyleSheet(
            "background: #fff7e6; color: #7a4b00; padding: 5px 8px;"
            " border-bottom: 1px solid #f0c36d;"
        )
        self._selection_info.hide()

        self._plot = pg.PlotWidget()
        self._plot.setBackground("w")
        self._plot.showGrid(x=True, y=True, alpha=0.2)
        self._plot.setTitle("Raw波形")
        self._plot.setLabel("bottom", "Time", units="ms")
        self._plot.setLabel("left", "Signal")
        self._plot.getPlotItem().setMenuEnabled(True)
        self._plot.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        self._zero_line = add_zero_reference(self._plot)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._selection_info)
        layout.addWidget(self._plot)

    @property
    def highlighted_sweep(self) -> Sweep | None:
        return self._highlighted_sweep

    @property
    def highlighted_interval_s(self) -> tuple[float, float] | None:
        if self._highlighted_sweep is None:
            return None
        if self._displayed_series_id == self._highlighted_sweep.current_series_id:
            offset_s = self.effective_current_time_offset_s
            return (
                float(self._highlighted_sweep.time_s[0]) + offset_s,
                float(self._highlighted_sweep.time_s[-1]) + offset_s,
            )
        return (
            float(self._highlighted_sweep.time_s[0]),
            float(self._highlighted_sweep.time_s[-1]),
        )

    @property
    def highlighted_interval_ms(self) -> tuple[float, float] | None:
        interval_s = self.highlighted_interval_s
        if interval_s is None:
            return None
        return interval_s[0] * 1_000.0, interval_s[1] * 1_000.0

    @property
    def preview_current_time_offset_s(self) -> float | None:
        return self._preview_current_time_offset_s

    @property
    def effective_current_time_offset_s(self) -> float:
        if self._preview_current_time_offset_s is not None:
            return self._preview_current_time_offset_s
        if self._highlighted_sweep is not None:
            return self._highlighted_sweep.current_time_offset_s
        return 0.0

    @property
    def displayed_series_id(self) -> str | None:
        return self._displayed_series_id

    @property
    def highlight_description(self) -> str:
        return self._selection_info.text()

    def clear_plot(self, message: str = "系列を選択してください") -> None:
        self.clear_sweep_highlight()
        self._displayed_series_id = None
        self._plot.clear()
        self._zero_line = add_zero_reference(self._plot)
        self._plot.setTitle(message)

    def show_series(self, series: RawSeries) -> None:
        self._displayed_series_id = series.descriptor.series_id
        x, y = min_max_downsample(series.time_s, series.values)
        x_ms = x * 1_000.0
        self._plot.clear()
        self._zero_line = add_zero_reference(self._plot)
        self._sweep_region = None
        self._plot.plot(
            x_ms,
            y,
            pen=pg.mkPen("#2563eb", width=1.2),
            antialias=False,
        )
        self._plot.setTitle(series.descriptor.display_name)
        self._plot.setLabel("bottom", "Time", units="ms")
        self._plot.setLabel(
            "left",
            "Signal",
            units=series.descriptor.value_unit or None,
        )
        self._plot.enableAutoRange()
        constrain_y_to_data(self._plot, (y,))
        self._update_selection_info()
        self._draw_sweep_highlight()

    def highlight_sweep(self, sweep: Sweep) -> None:
        self._highlighted_sweep = sweep
        self._update_selection_info()
        self._draw_sweep_highlight()

    def preview_current_time_offset(self, offset_s: float | None) -> None:
        if offset_s is not None and not math.isfinite(offset_s):
            raise ValueError("preview current time offset must be finite")
        self._preview_current_time_offset_s = offset_s
        self._update_selection_info()
        self._draw_sweep_highlight()

    def clear_current_time_offset_preview(self) -> None:
        self.preview_current_time_offset(None)

    def clear_sweep_highlight(self) -> None:
        self._remove_sweep_region()
        self._highlighted_sweep = None
        self._selection_info.clear()
        self._selection_info.hide()

    def _update_selection_info(self) -> None:
        sweep = self._highlighted_sweep
        if sweep is None:
            return
        direction = "上昇" if sweep.direction is SweepDirection.UP else "下降"
        voltage_start_ms = float(sweep.time_s[0]) * 1_000.0
        voltage_stop_ms = float(sweep.time_s[-1]) * 1_000.0
        applied_offset_ms = sweep.current_time_offset_s * 1_000.0
        effective_offset_ms = self.effective_current_time_offset_s * 1_000.0
        is_preview = self._preview_current_time_offset_s is not None and not math.isclose(
            self._preview_current_time_offset_s,
            sweep.current_time_offset_s,
            rel_tol=0.0,
            abs_tol=5e-10,
        )
        offset_description = (
            f"プレビュー {effective_offset_ms:+.6f} ms（未適用）／"
            f"適用済み {applied_offset_ms:+.6f} ms"
            if is_preview
            else f"補正 {applied_offset_ms:+.6f} ms"
        )
        if self._displayed_series_id == sweep.current_series_id:
            current_start_ms = voltage_start_ms + effective_offset_ms
            current_stop_ms = voltage_stop_ms + effective_offset_ms
            time_description = (
                f"表示中current参照 {current_start_ms:.8g}–{current_stop_ms:.8g} ms"
                f"（{offset_description}）｜ "
                f"Sweep電圧基準 {voltage_start_ms:.8g}–{voltage_stop_ms:.8g} ms"
            )
        else:
            time_description = (
                f"Sweep電圧基準 {voltage_start_ms:.8g}–{voltage_stop_ms:.8g} ms ｜ "
                f"current {offset_description}"
            )
        self._selection_info.setText(
            f"選択Sweep: {sweep.sweep_id} ｜ {direction} ｜ "
            f"{time_description} ｜ "
            f"sweep voltage元系列 {sweep.voltage_series_id} のsample "
            f"{sweep.source_start_index:,}–{sweep.source_stop_index - 1:,}"
        )
        self._selection_info.show()

    def _draw_sweep_highlight(self) -> None:
        if self._highlighted_sweep is None:
            self._remove_sweep_region()
            return
        start_ms, stop_ms = self.highlighted_interval_ms or (0.0, 0.0)
        if self._sweep_region is not None:
            self._sweep_region.setRegion((start_ms, stop_ms))
            return
        region = pg.LinearRegionItem(
            values=(start_ms, stop_ms),
            orientation="vertical",
            movable=False,
            brush=pg.mkBrush(245, 158, 11, 55),
            pen=pg.mkPen("#d97706", width=1.2),
        )
        region.setZValue(10)
        self._plot.addItem(region, ignoreBounds=True)
        self._sweep_region = region

    def _remove_sweep_region(self) -> None:
        if self._sweep_region is None:
            return
        self._plot.removeItem(self._sweep_region)
        self._sweep_region = None
