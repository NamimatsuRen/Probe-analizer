from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize_scalar

from probe_app.analysis.preprocessing import PreprocessedSweep
from probe_app.analysis.saturation import SaturationAnalysis
from probe_app.analysis.settings import TemperatureSettings
from probe_app.domain.models.analysis_result import AnalysisStatus
from probe_app.domain.models.raw_series import FloatArray


class TemperatureError(ValueError):
    """A user-correctable PANTA temperature fit failure."""


@dataclass(frozen=True, slots=True)
class TemperatureFit:
    """One Phi method's one-dimensional bounded T_i fit."""

    method_id: str
    phi_candidate_id: str
    phi_v: float
    ti_ev: float
    rmse_a: float
    objective: float
    fit_point_count: int
    simple_ti_ev: float | None
    relative_simple_difference: float | None
    objective_ti_ev: FloatArray
    objective_sse_a2: FloatArray
    status: AnalysisStatus
    message: str = ""


@dataclass(frozen=True, slots=True)
class TemperatureAnalysis:
    """Temperature fits retained by Phi method with one selected result."""

    fits: tuple[TemperatureFit, ...]
    selected_phi_candidate_id: str
    status: AnalysisStatus
    message: str = ""

    @property
    def selected_fit(self) -> TemperatureFit:
        return next(
            fit
            for fit in self.fits
            if fit.phi_candidate_id == self.selected_phi_candidate_id
        )


def panta_current(
    voltage_v: FloatArray,
    *,
    ti_ev: float,
    phi_v: float,
    vf_v: float,
    isat_i_a: float,
    r_ratio: float,
    k_per_v: float,
) -> FloatArray:
    """Return PANTA model current in A for voltage in V and T_i in eV."""

    voltage = np.asarray(voltage_v, dtype=np.float64)
    exponent = np.clip((phi_v - voltage) / ti_ev, -700.0, 700.0)
    return np.asarray(
        isat_i_a
        * (
            r_ratio * (1.0 + k_per_v * (voltage - vf_v))
            - np.exp(exponent)
        ),
        dtype=np.float64,
    )


def fit_panta_temperature(
    result: PreprocessedSweep,
    saturation: SaturationAnalysis,
    *,
    phi_candidate_id: str,
    method_id: str,
    phi_v: float,
    settings: TemperatureSettings | None = None,
) -> TemperatureFit:
    """Fit only T_i with all other model parameters fixed."""

    settings = settings or TemperatureSettings()
    fit_mask = (
        (result.voltage_v >= phi_v - settings.fit_window_v)
        & (result.voltage_v <= phi_v)
    )
    fit_voltage = result.voltage_v[fit_mask]
    fit_current = result.filtered_current_a[fit_mask]
    if fit_voltage.size < settings.minimum_points:
        raise TemperatureError(
            f"T_i評価窓に{fit_voltage.size}点しかありません"
            f"（最低{settings.minimum_points}点）"
        )

    def objective(ti_ev: float) -> float:
        model = panta_current(
            fit_voltage,
            ti_ev=ti_ev,
            phi_v=phi_v,
            vf_v=saturation.vf_v,
            isat_i_a=saturation.isat_i_a,
            r_ratio=saturation.r_ratio,
            k_per_v=saturation.k_per_v,
        )
        residual = fit_current - model
        value = float(np.sum(residual**2))
        return value if np.isfinite(value) else float("inf")

    optimized = minimize_scalar(
        objective,
        bounds=(settings.min_ti_ev, settings.max_ti_ev),
        method="bounded",
        options={"xatol": 1e-7},
    )
    if not optimized.success or not np.isfinite(optimized.x) or not np.isfinite(optimized.fun):
        raise TemperatureError("T_i有界最適化が収束しませんでした")

    ti_ev = float(optimized.x)
    objective_value = float(optimized.fun)
    rmse = float(np.sqrt(objective_value / fit_voltage.size))
    grid = np.linspace(
        settings.min_ti_ev,
        settings.max_ti_ev,
        settings.objective_grid_points,
        dtype=np.float64,
    )
    objective_grid = np.asarray([objective(float(value)) for value in grid])
    simple_ti = _simple_temperature(result, saturation.isat_i_a, phi_v)
    relative_difference = (
        None
        if simple_ti is None
        else abs(ti_ev - simple_ti) / max(abs(ti_ev), np.finfo(np.float64).eps)
    )
    tolerance = 0.01 * (settings.max_ti_ev - settings.min_ti_ev)
    boundary = (
        ti_ev <= settings.min_ti_ev + tolerance
        or ti_ev >= settings.max_ti_ev - tolerance
    )
    flat = _objective_is_flat(objective_grid)
    messages: list[str] = []
    if boundary:
        messages.append("T_i最小点が探索境界付近です")
    if flat:
        messages.append("目的関数の谷が平坦でT_iの拘束が弱いです")
    if relative_difference is not None and relative_difference > 0.7:
        messages.append("簡易微分推定との差が70%を超えます")
    status = AnalysisStatus.REVIEW if messages else AnalysisStatus.VALID
    return TemperatureFit(
        method_id=method_id,
        phi_candidate_id=phi_candidate_id,
        phi_v=phi_v,
        ti_ev=ti_ev,
        rmse_a=rmse,
        objective=objective_value,
        fit_point_count=int(fit_voltage.size),
        simple_ti_ev=simple_ti,
        relative_simple_difference=relative_difference,
        objective_ti_ev=grid,
        objective_sse_a2=objective_grid,
        status=status,
        message=" / ".join(messages),
    )


def _simple_temperature(
    result: PreprocessedSweep,
    isat_i_a: float,
    phi_v: float,
) -> float | None:
    mask = (
        (result.voltage_v >= phi_v - 0.5)
        & (result.voltage_v <= phi_v + 0.5)
        & (result.dcurrent_dvoltage_a_per_v > 0)
    )
    derivative = result.dcurrent_dvoltage_a_per_v[mask]
    if not derivative.size:
        return None
    effective = float(np.median(derivative))
    if effective <= np.finfo(np.float64).eps:
        return None
    value = isat_i_a / effective
    return float(value) if np.isfinite(value) and value > 0 else None


def _objective_is_flat(values: FloatArray) -> bool:
    finite = values[np.isfinite(values)]
    if finite.size < 3:
        return True
    minimum = float(np.min(finite))
    spread = float(np.max(finite) - minimum)
    scale = max(float(np.max(np.abs(finite))), np.finfo(np.float64).eps)
    return spread / scale < 1e-4
