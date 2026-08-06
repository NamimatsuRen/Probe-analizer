from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSplitter, QVBoxLayout, QWidget

from probe_app.analysis import (
    CompleteAnalysisResult,
    PreprocessedSweep,
    panta_current,
)
from probe_app.domain.models.raw_series import FloatArray
from probe_app.domain.models.sweep import Sweep, SweepDirection
from probe_app.ui.plot_policy import (
    add_zero_reference,
    constrain_iv_x,
    constrain_y_to_data,
)


class SweepIVPlot(QWidget):
    """Plot one selected sweep in voltage-ascending I–V order."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        analysis_enabled: bool = True,
    ) -> None:
        super().__init__(parent)
        self._analysis_enabled = analysis_enabled
        self._selected_sweep: Sweep | None = None
        self._curve: pg.PlotDataItem | None = None
        self._filtered_curve: pg.PlotDataItem | None = None
        self._derivative_curve: pg.PlotDataItem | None = None
        self._preprocessed: PreprocessedSweep | None = None
        self._start_marker: pg.PlotDataItem | None = None
        self._end_marker: pg.PlotDataItem | None = None
        self._vf_line: pg.InfiniteLine | None = None
        self._phi_line: pg.InfiniteLine | None = None
        self._derivative_phi_line: pg.InfiniteLine | None = None
        self._ion_fit_curve: pg.PlotDataItem | None = None
        self._electron_fit_curve: pg.PlotDataItem | None = None
        self._model_curve: pg.PlotDataItem | None = None
        self._zero_line: pg.InfiniteLine | None = None
        self._derivative_zero_line: pg.InfiniteLine | None = None

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
        self._plot.setTitle(self._empty_iv_title)
        self._plot.setLabel("bottom", "Voltage", units="V")
        self._plot.setLabel("left", "Current", units="A")
        self._plot.getPlotItem().setMenuEnabled(True)
        self._plot.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        if self._analysis_enabled:
            self._plot.addLegend(offset=(10, 10))

        self._derivative_plot: pg.PlotWidget | None = None
        plot_container: QWidget = self._plot
        if self._analysis_enabled:
            self._derivative_plot = pg.PlotWidget()
            self._derivative_plot.setObjectName("sweepDerivativePlot")
            self._derivative_plot.setBackground("w")
            self._derivative_plot.showGrid(x=True, y=True, alpha=0.2)
            self._derivative_plot.setTitle("dI/dV")
            self._derivative_plot.setLabel("bottom", "Voltage", units="V")
            self._derivative_plot.setLabel("left", "dI/dV", units="A/V")
            self._derivative_plot.getPlotItem().setMenuEnabled(True)
            self._derivative_plot.getViewBox().setMouseMode(pg.ViewBox.RectMode)
            self._derivative_plot.setXLink(self._plot)

            plot_splitter = QSplitter(Qt.Orientation.Vertical)
            plot_splitter.setObjectName("sweepAnalysisPlotSplitter")
            plot_splitter.addWidget(self._plot)
            plot_splitter.addWidget(self._derivative_plot)
            plot_splitter.setStretchFactor(0, 3)
            plot_splitter.setStretchFactor(1, 2)
            plot_splitter.setSizes([330, 210])
            plot_container = plot_splitter

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._selection_info)
        layout.addWidget(plot_container, 1)
        constrain_iv_x(self._plot)
        self._zero_line = add_zero_reference(self._plot)
        if self._derivative_plot is not None:
            constrain_iv_x(self._derivative_plot)
            self._derivative_zero_line = add_zero_reference(self._derivative_plot)

    @property
    def analysis_enabled(self) -> bool:
        return self._analysis_enabled

    @property
    def _empty_iv_title(self) -> str:
        return "Sweep I–V — Raw / Filtered" if self._analysis_enabled else "Sweep I–V — Raw"

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
    def displayed_filtered_current_a(self) -> FloatArray | None:
        if self._preprocessed is None:
            return None
        return self._preprocessed.filtered_current_a

    @property
    def displayed_derivative_a_per_v(self) -> FloatArray | None:
        if self._preprocessed is None:
            return None
        return self._preprocessed.dcurrent_dvoltage_a_per_v

    @property
    def preprocessed(self) -> PreprocessedSweep | None:
        return self._preprocessed

    @property
    def description(self) -> str:
        return self._selection_info.text()

    def clear_plot(self, message: str = "Sweep分割後に一覧から選択してください") -> None:
        self._selected_sweep = None
        self._curve = None
        self._filtered_curve = None
        self._derivative_curve = None
        self._preprocessed = None
        self._start_marker = None
        self._end_marker = None
        self._reset_analysis_item_refs()
        self._plot.clear()
        self._zero_line = add_zero_reference(self._plot)
        self._plot.setTitle(self._empty_iv_title)
        if self._derivative_plot is not None:
            self._derivative_plot.clear()
            self._derivative_zero_line = add_zero_reference(self._derivative_plot)
            self._derivative_plot.setTitle("dI/dV")
        self._selection_info.setText(message)

    def show_sweep(self, sweep: Sweep) -> None:
        self._selected_sweep = sweep
        self._preprocessed = None
        self._filtered_curve = None
        self._derivative_curve = None
        self._reset_analysis_item_refs()
        self._plot.clear()
        self._zero_line = add_zero_reference(self._plot)
        if self._derivative_plot is not None:
            self._derivative_plot.clear()
            self._derivative_zero_line = add_zero_reference(self._derivative_plot)
        direction = "上昇" if sweep.direction is SweepDirection.UP else "下降"
        color = "#2563eb" if sweep.direction is SweepDirection.UP else "#d97706"
        self._curve = self._plot.plot(
            sweep.iv_voltage_v,
            sweep.iv_current_a,
            pen=pg.mkPen(color, width=1.5),
            antialias=False,
            name="Raw",
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
        suffix = "Raw / Filtered" if self._analysis_enabled else "Raw"
        self._plot.setTitle(f"Sweep I–V — {direction} — {suffix}")
        if self._derivative_plot is not None:
            self._derivative_plot.setTitle("dI/dV — 前処理を実行してください")
        self._plot.setLabel("bottom", "Voltage", units="V")
        self._plot.setLabel("left", "Current", units="A")
        self._plot.enableAutoRange()
        constrain_iv_x(self._plot)
        constrain_y_to_data(self._plot, (sweep.iv_current_a,))
        if self._derivative_plot is not None:
            self._derivative_plot.enableAutoRange()
            constrain_iv_x(self._derivative_plot)
        self._selection_info.setText(
            f"選択Sweep: {sweep.sweep_id} ｜ 取得方向: {direction} ｜ "
            f"current: {sweep.current_series_id} [A] ｜ "
            f"current時間補正: {sweep.current_time_offset_s * 1_000.0:+.6f} ms ｜ "
            f"voltage: {sweep.voltage_series_id} [V] ｜ "
            f"{sweep.point_count:,} 点 ｜ ● 始点 / ■ 終点"
        )

    def show_preprocessing(self, result: PreprocessedSweep) -> None:
        if not self._analysis_enabled or self._derivative_plot is None:
            raise RuntimeError("preprocessing display is disabled for this Raw-only plot")
        if self._selected_sweep is None or result.sweep_id != self._selected_sweep.sweep_id:
            raise ValueError("preprocessing result does not match the selected Sweep")
        if self._filtered_curve is not None:
            self._plot.removeItem(self._filtered_curve)
        self._derivative_plot.clear()
        self._derivative_zero_line = add_zero_reference(self._derivative_plot)

        self._preprocessed = result
        self._filtered_curve = self._plot.plot(
            result.voltage_v,
            result.filtered_current_a,
            pen=pg.mkPen("#dc2626", width=2.0),
            antialias=False,
            name="Filtered",
        )
        self._derivative_curve = self._derivative_plot.plot(
            result.voltage_v,
            result.dcurrent_dvoltage_a_per_v,
            pen=pg.mkPen("#7c3aed", width=1.5),
            antialias=False,
        )
        self._derivative_plot.setTitle(
            f"dI/dV — SG {result.used_window_length}点 / {result.polyorder}次"
        )
        self._plot.enableAutoRange()
        self._derivative_plot.enableAutoRange()
        constrain_iv_x(self._plot)
        constrain_iv_x(self._derivative_plot)
        constrain_y_to_data(
            self._plot,
            (result.raw_current_a, result.filtered_current_a),
        )
        constrain_y_to_data(
            self._derivative_plot,
            (result.dcurrent_dvoltage_a_per_v,),
        )

    def show_analysis_result(self, result: CompleteAnalysisResult) -> None:
        """Overlay selected potentials, saturation lines, and PANTA model."""

        if not self._analysis_enabled or self._derivative_plot is None:
            raise RuntimeError("analysis display is disabled for this Raw-only plot")
        if (
            self._selected_sweep is None
            or result.preprocessed.sweep_id != self._selected_sweep.sweep_id
        ):
            raise ValueError("analysis result does not match the selected Sweep")
        self._clear_analysis_overlays()
        if result.potential is None:
            return

        vf_v = result.potential.selected_vf.value_v
        phi_v = result.potential.selected_phi.value_v
        self._vf_line = pg.InfiniteLine(
            pos=vf_v,
            angle=90,
            pen=pg.mkPen("#16a34a", width=1.5, style=Qt.PenStyle.DashLine),
            label="V_f",
        )
        self._phi_line = pg.InfiniteLine(
            pos=phi_v,
            angle=90,
            pen=pg.mkPen("#ea580c", width=1.5, style=Qt.PenStyle.DashLine),
            label="Phi",
        )
        self._derivative_phi_line = pg.InfiniteLine(
            pos=phi_v,
            angle=90,
            pen=pg.mkPen("#ea580c", width=1.25, style=Qt.PenStyle.DashLine),
        )
        self._plot.addItem(self._vf_line)
        self._plot.addItem(self._phi_line)
        self._derivative_plot.addItem(self._derivative_phi_line)

        if result.saturation is not None:
            ion_voltage = np.linspace(
                result.settings.saturation.ion_min_v,
                vf_v,
                160,
                dtype=np.float64,
            )
            electron_voltage = np.linspace(
                vf_v,
                result.settings.saturation.electron_max_v,
                240,
                dtype=np.float64,
            )
            self._ion_fit_curve = self._plot.plot(
                ion_voltage,
                result.saturation.ion_fit.evaluate(ion_voltage),
                pen=pg.mkPen("#0891b2", width=2.0, style=Qt.PenStyle.DashLine),
                name="Ion saturation fit",
            )
            self._electron_fit_curve = self._plot.plot(
                electron_voltage,
                result.saturation.electron_fit.evaluate(electron_voltage),
                pen=pg.mkPen("#2563eb", width=2.0, style=Qt.PenStyle.DashLine),
                name="Electron saturation fit",
            )

        if result.saturation is not None and result.temperature is not None:
            fit = result.temperature.selected_fit
            model_mask = result.preprocessed.voltage_v >= fit.phi_v - 0.5
            model_voltage = result.preprocessed.voltage_v[model_mask]
            model_current = panta_current(
                model_voltage,
                ti_ev=fit.ti_ev,
                phi_v=fit.phi_v,
                vf_v=result.saturation.vf_v,
                isat_i_a=result.saturation.isat_i_a,
                r_ratio=result.saturation.r_ratio,
                k_per_v=result.saturation.k_per_v,
            )
            finite = np.isfinite(model_current)
            self._model_curve = self._plot.plot(
                model_voltage[finite],
                model_current[finite],
                pen=pg.mkPen("#9333ea", width=2.25),
                name=f"PANTA T_i={fit.ti_ev:.4g} eV",
            )
        constrain_iv_x(self._plot)
        constrain_y_to_data(
            self._plot,
            (
                result.preprocessed.raw_current_a,
                result.preprocessed.filtered_current_a,
            ),
        )

    def clear_analysis_result(self) -> None:
        self._clear_analysis_overlays()

    def clear_preprocessing(self, message: str = "前処理を実行できません") -> None:
        if self._filtered_curve is not None:
            self._plot.removeItem(self._filtered_curve)
        self._filtered_curve = None
        self._derivative_curve = None
        self._preprocessed = None
        self._clear_analysis_overlays()
        if self._derivative_plot is not None:
            self._derivative_plot.clear()
            self._derivative_zero_line = add_zero_reference(self._derivative_plot)
            self._derivative_plot.setTitle(message)

    def _clear_analysis_overlays(self) -> None:
        for item in (
            self._vf_line,
            self._phi_line,
            self._ion_fit_curve,
            self._electron_fit_curve,
            self._model_curve,
        ):
            if item is not None:
                self._plot.removeItem(item)
        if self._derivative_plot is not None and self._derivative_phi_line is not None:
            self._derivative_plot.removeItem(self._derivative_phi_line)
        self._reset_analysis_item_refs()

    def _reset_analysis_item_refs(self) -> None:
        self._vf_line = None
        self._phi_line = None
        self._derivative_phi_line = None
        self._ion_fit_curve = None
        self._electron_fit_curve = None
        self._model_curve = None
