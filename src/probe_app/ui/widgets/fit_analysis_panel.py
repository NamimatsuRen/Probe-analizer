from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from probe_app.analysis import (
    AnalysisSettings,
    CompleteAnalysisResult,
    PotentialSettings,
    SaturationSettings,
    TemperatureSettings,
)


class FitAnalysisPanel(QWidget):
    """Explicit Level 4–6 settings, candidate selection, and diagnostics."""

    run_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("fitAnalysisPanel")
        self._selected_sweep_id: str | None = None
        self._result: CompleteAnalysisResult | None = None

        self._fit1_min, self._fit1_max = self._range_boxes(10.0, 15.0)
        self._fit2_min, self._fit2_max = self._range_boxes(20.0, 50.0)
        self._phi_min, self._phi_max = self._range_boxes(10.0, 20.0)
        self._ion_min, self._ion_max = self._range_boxes(-35.0, -15.0)
        self._electron_min, self._electron_max = self._range_boxes(20.0, 50.0)
        self._ti_min, self._ti_max = self._range_boxes(0.1, 10.0)
        self._ti_window = self._double_box(0.1, 0.001, 10.0, decimals=3)

        self._vf_candidates = QComboBox()
        self._vf_candidates.setObjectName("vfCandidateSelection")
        self._vf_candidates.addItem("自動選択", None)
        self._phi_candidates = QComboBox()
        self._phi_candidates.setObjectName("phiCandidateSelection")
        self._phi_candidates.addItem("自動選択", None)
        self._vf_candidates.currentIndexChanged.connect(self._mark_pending)
        self._phi_candidates.currentIndexChanged.connect(self._mark_pending)
        for box in (
            self._fit1_min,
            self._fit1_max,
            self._fit2_min,
            self._fit2_max,
            self._phi_min,
            self._phi_max,
            self._ion_min,
            self._ion_max,
            self._electron_min,
            self._electron_max,
            self._ti_min,
            self._ti_max,
            self._ti_window,
        ):
            box.valueChanged.connect(self._mark_pending)

        potential_form = QFormLayout()
        potential_form.addRow("log Fit1 最小 [V]", self._fit1_min)
        potential_form.addRow("log Fit1 最大 [V]", self._fit1_max)
        potential_form.addRow("log Fit2 最小 [V]", self._fit2_min)
        potential_form.addRow("log Fit2 最大 [V]", self._fit2_max)
        potential_form.addRow("Phi探索 最小 [V]", self._phi_min)
        potential_form.addRow("Phi探索 最大 [V]", self._phi_max)
        potential_form.addRow("V_f候補", self._vf_candidates)
        potential_form.addRow("Phi候補", self._phi_candidates)
        potential_group = QGroupBox("V_f・Phi候補")
        potential_group.setObjectName("potentialFitControls")
        potential_group.setLayout(potential_form)

        saturation_form = QFormLayout()
        saturation_form.addRow("ion 最小 [V]", self._ion_min)
        saturation_form.addRow("ion 最大 [V]", self._ion_max)
        saturation_form.addRow("electron 最小 [V]", self._electron_min)
        saturation_form.addRow("electron 最大 [V]", self._electron_max)
        saturation_group = QGroupBox("飽和域Fit")
        saturation_group.setObjectName("saturationFitControls")
        saturation_group.setLayout(saturation_form)

        temperature_form = QFormLayout()
        temperature_form.addRow("T_i 最小 [eV]", self._ti_min)
        temperature_form.addRow("T_i 最大 [eV]", self._ti_max)
        temperature_form.addRow("Phi左の評価幅 [V]", self._ti_window)
        temperature_group = QGroupBox("PANTA T_i model fit")
        temperature_group.setObjectName("temperatureFitControls")
        temperature_group.setLayout(temperature_form)

        self._run_button = QPushButton("V_f・Phi・飽和域・T_iを解析")
        self._run_button.setObjectName("runLevel4To6Analysis")
        self._run_button.setEnabled(False)
        self._run_button.clicked.connect(self._emit_request)

        self._status = QLabel("Sweepを選択して明示的に解析を実行してください")
        self._status.setObjectName("level4To6AnalysisStatus")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #556070;")

        self._objective_plot = pg.PlotWidget()
        self._objective_plot.setObjectName("tiObjectivePlot")
        self._objective_plot.setBackground("w")
        self._objective_plot.showGrid(x=True, y=True, alpha=0.2)
        self._objective_plot.setLabel("bottom", "T_i", units="eV")
        self._objective_plot.setLabel("left", "SSE", units="A²")
        self._objective_plot.setTitle("T_i目的関数 — 未実行")
        self._objective_plot.setMinimumHeight(150)

        result_group = QGroupBox("解析結果・目的関数")
        result_layout = QVBoxLayout(result_group)
        result_layout.addWidget(self._status)
        result_layout.addWidget(self._objective_plot)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 8)
        layout.addWidget(potential_group)
        layout.addWidget(saturation_group)
        layout.addWidget(temperature_group)
        layout.addWidget(self._run_button)
        layout.addWidget(result_group)

    @property
    def result(self) -> CompleteAnalysisResult | None:
        return self._result

    @property
    def description(self) -> str:
        return self._status.text()

    def settings(self) -> AnalysisSettings:
        return AnalysisSettings(
            potential=PotentialSettings(
                log_fit1_min_v=self._fit1_min.value(),
                log_fit1_max_v=self._fit1_max.value(),
                log_fit2_min_v=self._fit2_min.value(),
                log_fit2_max_v=self._fit2_max.value(),
                phi_search_min_v=self._phi_min.value(),
                phi_search_max_v=self._phi_max.value(),
                selected_vf_candidate_id=self._vf_candidates.currentData(),
                selected_phi_candidate_id=self._phi_candidates.currentData(),
            ),
            saturation=SaturationSettings(
                ion_min_v=self._ion_min.value(),
                ion_max_v=self._ion_max.value(),
                electron_min_v=self._electron_min.value(),
                electron_max_v=self._electron_max.value(),
            ),
            temperature=TemperatureSettings(
                min_ti_ev=self._ti_min.value(),
                max_ti_ev=self._ti_max.value(),
                fit_window_v=self._ti_window.value(),
            ),
        )

    def select_sweep(self, sweep_id: str) -> None:
        if not sweep_id.strip():
            raise ValueError("sweep_id cannot be empty")
        if self._selected_sweep_id == sweep_id:
            return
        self._selected_sweep_id = sweep_id
        self._result = None
        self._reset_candidates()
        self._run_button.setEnabled(True)
        self._status.setStyleSheet("color: #556070;")
        self._status.setText(
            f"{sweep_id}\n設定を確認して解析ボタンを押してください。"
            "候補や範囲の変更だけでは再計算しません。"
        )
        self._clear_objective()

    def clear(self, message: str = "Sweepを選択してください") -> None:
        self._selected_sweep_id = None
        self._result = None
        self._reset_candidates()
        self._run_button.setEnabled(False)
        self._status.setStyleSheet("color: #556070;")
        self._status.setText(message)
        self._clear_objective()

    def invalidate(self, message: str) -> None:
        """Forget numerical results while keeping the selected Sweep."""

        self._result = None
        self._run_button.setEnabled(self._selected_sweep_id is not None)
        self._status.setStyleSheet("color: #b54708;")
        self._status.setText(message)
        self._clear_objective()

    def show_result(self, result: CompleteAnalysisResult) -> None:
        self._selected_sweep_id = result.preprocessed.sweep_id
        self._result = result
        self._run_button.setEnabled(True)
        self._populate_candidates(result)
        color = {
            "valid": "#067647",
            "review": "#b54708",
            "bad": "#b42318",
            "error": "#b42318",
        }.get(result.status.value, "#556070")
        self._status.setStyleSheet(f"color: {color};")
        lines = [result.preprocessed.sweep_id]
        if result.potential is not None:
            lines.append(
                f"V_f = {result.potential.selected_vf.value_v:.6g} V ｜ "
                f"Phi = {result.potential.selected_phi.value_v:.6g} V "
                f"({result.potential.selected_phi.method_id})"
            )
        if result.saturation is not None:
            lines.append(
                f"I_sat,i = {result.saturation.isat_i_a * 1_000:.6g} mA ｜ "
                f"I_sat,e = {result.saturation.isat_e_a * 1_000:.6g} mA ｜ "
                f"R = {result.saturation.r_ratio:.6g} ｜ "
                f"K = {result.saturation.k_per_v:.6g} V⁻¹"
            )
        if result.temperature is not None:
            fit = result.temperature.selected_fit
            lines.append(
                f"T_i = {fit.ti_ev:.6g} eV ｜ RMSE = {fit.rmse_a * 1_000:.6g} mA ｜ "
                f"評価点 {fit.fit_point_count}"
            )
        if result.message:
            lines.append(f"確認: {result.message}")
        self._status.setText("\n".join(lines))
        self._show_objective(result)

    def show_error(self, sweep_id: str, message: str) -> None:
        self._selected_sweep_id = sweep_id
        self._result = None
        self._run_button.setEnabled(True)
        self._status.setStyleSheet("color: #b42318;")
        self._status.setText(
            f"{sweep_id}\n解析できません: {message}\n"
            "候補・Fit範囲・前処理設定を確認してください。"
        )
        self._clear_objective()

    @staticmethod
    def _double_box(
        value: float,
        minimum: float,
        maximum: float,
        *,
        decimals: int = 3,
    ) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(decimals)
        box.setSingleStep(0.25)
        box.setValue(value)
        return box

    @classmethod
    def _range_boxes(
        cls,
        lower: float,
        upper: float,
    ) -> tuple[QDoubleSpinBox, QDoubleSpinBox]:
        return (
            cls._double_box(lower, -200.0, 200.0),
            cls._double_box(upper, -200.0, 200.0),
        )

    def _reset_candidates(self) -> None:
        for combo in (self._vf_candidates, self._phi_candidates):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("自動選択", None)
            combo.blockSignals(False)

    def _populate_candidates(self, result: CompleteAnalysisResult) -> None:
        if result.potential is None:
            self._reset_candidates()
            return
        for combo, candidates, selected_id, requested_id in (
            (
                self._vf_candidates,
                result.potential.vf_candidates,
                result.potential.selected_vf_candidate_id,
                result.settings.potential.selected_vf_candidate_id,
            ),
            (
                self._phi_candidates,
                result.potential.phi_candidates,
                result.potential.selected_phi_candidate_id,
                result.settings.potential.selected_phi_candidate_id,
            ),
        ):
            combo.blockSignals(True)
            combo.clear()
            selected_candidate = next(
                candidate
                for candidate in candidates
                if candidate.candidate_id == selected_id
            )
            combo.addItem(f"自動選択（{selected_candidate.label}）", None)
            for index, candidate in enumerate(candidates):
                combo.addItem(candidate.label, candidate.candidate_id)
                if candidate.candidate_id == requested_id:
                    combo.setCurrentIndex(index + 1)
            combo.blockSignals(False)

    def _show_objective(self, result: CompleteAnalysisResult) -> None:
        self._objective_plot.clear()
        if result.temperature is None:
            self._objective_plot.setTitle("T_i目的関数 — Fit未成立")
            return
        fit = result.temperature.selected_fit
        self._objective_plot.plot(
            fit.objective_ti_ev,
            fit.objective_sse_a2,
            pen=pg.mkPen("#7c3aed", width=1.5),
        )
        self._objective_plot.plot(
            [fit.ti_ev],
            [fit.objective],
            pen=None,
            symbol="o",
            symbolBrush="#dc2626",
            symbolPen="#991b1b",
            symbolSize=8,
        )
        self._objective_plot.setTitle(
            f"T_i目的関数 — 最小 {fit.ti_ev:.6g} eV"
        )
        self._objective_plot.enableAutoRange()

    def _clear_objective(self) -> None:
        self._objective_plot.clear()
        self._objective_plot.setTitle("T_i目的関数 — 未実行")

    def _mark_pending(self, *_: object) -> None:
        if self._result is None:
            return
        self._status.setStyleSheet("color: #b54708;")
        self._status.setText(
            "候補選択を変更しました。解析ボタンを押すまで、表示中のFit結果は変更されません。"
        )

    def _emit_request(self) -> None:
        if self._selected_sweep_id is None:
            return
        try:
            settings = self.settings()
        except ValueError as error:
            self.show_error(self._selected_sweep_id, str(error))
            return
        self.run_requested.emit(settings)
