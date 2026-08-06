from __future__ import annotations

import numpy as np
import pytest

from probe_app.analysis import (
    AnalysisSettings,
    PreprocessedSweep,
    RobustLinearFit,
    SaturationAnalysis,
    SaturationSettings,
    TemperatureSettings,
    analyze_preprocessed,
    estimate_potentials,
    fit_panta_temperature,
    fit_saturation_regions,
    panta_current,
    robust_linear_fit,
)
from probe_app.domain.models.analysis_result import AnalysisStage, AnalysisStatus


def test_robust_linear_fit_rejects_a_large_outlier() -> None:
    x = np.linspace(-5.0, 5.0, 101, dtype=np.float64)
    y = 2.5 * x - 1.2
    y[50] += 100.0

    fit = robust_linear_fit(x, y)

    assert fit.slope == pytest.approx(2.5)
    assert fit.intercept == pytest.approx(-1.2)
    assert fit.used_point_count == 100
    assert fit.r_squared == pytest.approx(1.0)


def test_potential_analysis_retains_log_and_derivative_candidates() -> None:
    result = _piecewise_preprocessed()

    potentials = estimate_potentials(result)

    assert potentials.selected_vf.value_v == pytest.approx(0.0, abs=0.02)
    log_candidate = next(
        candidate
        for candidate in potentials.phi_candidates
        if candidate.method_id == "filtered_log_intersection"
    )
    assert log_candidate.value_v == pytest.approx(16.6666667)
    assert log_candidate.status is AnalysisStatus.VALID
    assert any(
        candidate.method_id == "filtered_derivative_peak" for candidate in potentials.phi_candidates
    )


def test_saturation_fit_calculates_isat_r_and_k_in_consistent_a_units() -> None:
    voltage = np.linspace(-50.0, 50.0, 10_001, dtype=np.float64)
    current = np.interp(
        voltage,
        [-50.0, -15.0, 20.0, 50.0],
        [-250e-6, -215e-6, 440e-6, 500e-6],
    )
    preprocessed = _preprocessed(voltage, current)

    result = fit_saturation_regions(preprocessed, vf_v=-5.0)

    assert result.isat_i_a == pytest.approx(205e-6, rel=1e-6)
    assert result.isat_e_a == pytest.approx(390e-6, rel=1e-6)
    assert result.r_ratio == pytest.approx(390.0 / 205.0, rel=1e-6)
    assert result.k_per_v == pytest.approx(2e-6 / 390e-6, rel=1e-6)
    assert result.status is AnalysisStatus.VALID


def test_panta_temperature_recovers_known_synthetic_ti() -> None:
    voltage = np.linspace(-1.0, 1.0, 2_001, dtype=np.float64)
    known_ti = 2.4
    current = panta_current(
        voltage,
        ti_ev=known_ti,
        phi_v=0.0,
        vf_v=-1.0,
        isat_i_a=1e-3,
        r_ratio=2.0,
        k_per_v=0.01,
    )
    derivative = 1e-3 * (2.0 * 0.01 + np.exp(-voltage / known_ti) / known_ti)
    preprocessed = PreprocessedSweep(
        sweep_id="synthetic",
        voltage_v=voltage,
        raw_current_a=current,
        filtered_current_a=current,
        dcurrent_dvoltage_a_per_v=derivative,
        requested_window_length=101,
        used_window_length=101,
        polyorder=3,
        voltage_step_v=0.001,
        max_spacing_deviation_fraction=0.0,
    )
    saturation = SaturationAnalysis(
        ion_fit=_line(-1e-6, -1e-3),
        electron_fit=_line(2e-6, 2e-3),
        vf_v=-1.0,
        ion_current_at_vf_a=-1e-3,
        electron_current_at_vf_a=2e-3,
        isat_i_a=1e-3,
        isat_e_a=2e-3,
        r_ratio=2.0,
        k_per_v=0.01,
        status=AnalysisStatus.VALID,
    )

    fit = fit_panta_temperature(
        preprocessed,
        saturation,
        phi_candidate_id="phi:test",
        method_id="filtered_log_intersection",
        phi_v=0.0,
        settings=TemperatureSettings(fit_window_v=0.1),
    )

    assert fit.ti_ev == pytest.approx(known_ti, rel=1e-5)
    assert fit.rmse_a < 1e-10
    assert fit.fit_point_count >= 100
    assert fit.objective_ti_ev.size == fit.objective_sse_a2.size


def test_panta_temperature_accepts_manual_ti_and_still_evaluates_sse() -> None:
    voltage = np.linspace(-1.0, 1.0, 2_001, dtype=np.float64)
    known_ti = 2.4
    manual_ti = 3.1
    current = panta_current(
        voltage,
        ti_ev=known_ti,
        phi_v=0.0,
        vf_v=-1.0,
        isat_i_a=1e-3,
        r_ratio=2.0,
        k_per_v=0.01,
    )
    preprocessed = _preprocessed(voltage, current)
    saturation = SaturationAnalysis(
        ion_fit=_line(-1e-6, -1e-3),
        electron_fit=_line(2e-6, 2e-3),
        vf_v=-1.0,
        ion_current_at_vf_a=-1e-3,
        electron_current_at_vf_a=2e-3,
        isat_i_a=1e-3,
        isat_e_a=2e-3,
        r_ratio=2.0,
        k_per_v=0.01,
        status=AnalysisStatus.VALID,
    )

    fit = fit_panta_temperature(
        preprocessed,
        saturation,
        phi_candidate_id="phi:test",
        method_id="filtered_log_intersection",
        phi_v=0.0,
        settings=TemperatureSettings(fit_window_v=0.1, manual_ti_ev=manual_ti),
    )

    assert fit.ti_ev == manual_ti
    assert fit.objective > 0
    assert fit.status is AnalysisStatus.REVIEW
    assert "手動指定" in fit.message


def test_pipeline_preserves_all_stages_and_partial_quality() -> None:
    result = analyze_preprocessed(_piecewise_preprocessed(), AnalysisSettings())

    assert result.potential is not None
    assert result.saturation is not None
    assert result.temperature is not None
    assert tuple(stage.stage for stage in result.stage_results) == (
        AnalysisStage.POTENTIAL,
        AnalysisStage.SATURATION,
        AnalysisStage.TEMPERATURE,
        AnalysisStage.QUALITY,
    )
    assert result.temperature.selected_fit.fit_point_count >= 5
    assert result.stage_results[-1].status in (
        AnalysisStatus.VALID,
        AnalysisStatus.REVIEW,
        AnalysisStatus.BAD,
    )


def test_analysis_settings_revision_values_are_stable_and_sorted() -> None:
    settings = AnalysisSettings(saturation=SaturationSettings(ion_min_v=-40.0, ion_max_v=-20.0))

    revision_values = settings.as_revision_settings()

    assert revision_values == tuple(sorted(revision_values))
    assert dict(revision_values)["ion_min_v"] == "-40"
    assert dict(revision_values)["selected_phi_candidate_id"] == "auto"
    assert dict(revision_values)["ti_manual_ev"] == "auto"


def test_manual_ti_is_part_of_analysis_revision() -> None:
    settings = AnalysisSettings(
        temperature=TemperatureSettings(manual_ti_ev=1.75),
    )

    assert dict(settings.as_revision_settings())["ti_manual_ev"] == "1.75"


def _piecewise_preprocessed() -> PreprocessedSweep:
    voltage = np.linspace(-50.0, 50.0, 10_001, dtype=np.float64)
    current = np.empty_like(voltage)
    negative = voltage < 0.0
    current[negative] = -2e-4 + 2e-6 * (voltage[negative] + 50.0)
    middle = (voltage >= 0.0) & (voltage < 10.0)
    current[middle] = 1e-6 * (voltage[middle] + 1.0)
    fit1 = (voltage >= 10.0) & (voltage <= 15.0)
    current[fit1] = 10 ** (0.1 * voltage[fit1] - 7.0)
    bridge = (voltage > 15.0) & (voltage < 20.0)
    current[bridge] = np.linspace(current[fit1][-1], 2e-5, int(bridge.sum()))
    fit2 = voltage >= 20.0
    current[fit2] = 10 ** (0.01 * voltage[fit2] - 5.5)
    return _preprocessed(voltage, current)


def _preprocessed(voltage: np.ndarray, current: np.ndarray) -> PreprocessedSweep:
    return PreprocessedSweep(
        sweep_id="synthetic",
        voltage_v=voltage,
        raw_current_a=current,
        filtered_current_a=current,
        dcurrent_dvoltage_a_per_v=np.gradient(current, voltage),
        requested_window_length=501,
        used_window_length=501,
        polyorder=3,
        voltage_step_v=float(voltage[1] - voltage[0]),
        max_spacing_deviation_fraction=0.0,
    )


def _line(slope: float, intercept: float) -> RobustLinearFit:
    return RobustLinearFit(
        slope=slope,
        intercept=intercept,
        rmse=0.0,
        r_squared=1.0,
        point_count=100,
        used_point_count=100,
        x_min=-50.0,
        x_max=50.0,
    )
