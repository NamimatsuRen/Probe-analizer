from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks

from probe_app.analysis.fitting import (
    LinearFitError,
    RobustLinearFit,
    robust_linear_fit,
)
from probe_app.analysis.preprocessing import PreprocessedSweep
from probe_app.analysis.settings import PotentialSettings
from probe_app.domain.models.analysis_result import AnalysisStatus
from probe_app.domain.models.raw_series import FloatArray
from probe_app.domain.models.summary import SummaryMethod


class PotentialError(ValueError):
    """A user-correctable V_f or Phi estimation failure."""


@dataclass(frozen=True, slots=True)
class PotentialCandidate:
    """One selectable potential candidate with its method-level evidence."""

    candidate_id: str
    method_id: str
    label: str
    value_v: float
    status: AnalysisStatus
    score: float
    message: str = ""
    fit_low: RobustLinearFit | None = None
    fit_high: RobustLinearFit | None = None


@dataclass(frozen=True, slots=True)
class PotentialAnalysis:
    """All retained V_f/Phi candidates and explicit selected values."""

    vf_candidates: tuple[PotentialCandidate, ...]
    phi_candidates: tuple[PotentialCandidate, ...]
    selected_vf_candidate_id: str
    selected_phi_candidate_id: str
    status: AnalysisStatus
    message: str = ""

    @property
    def selected_vf(self) -> PotentialCandidate:
        return _candidate_by_id(
            self.vf_candidates,
            self.selected_vf_candidate_id,
        )

    @property
    def selected_phi(self) -> PotentialCandidate:
        return _candidate_by_id(
            self.phi_candidates,
            self.selected_phi_candidate_id,
        )


def estimate_potentials(
    result: PreprocessedSweep,
    settings: PotentialSettings | None = None,
) -> PotentialAnalysis:
    """Estimate V_f zero crossings and filtered log/derivative Phi candidates."""

    settings = settings or PotentialSettings()
    vf_candidates = _zero_crossing_candidates(
        result.voltage_v,
        result.filtered_current_a,
    )
    if not vf_candidates:
        raise PotentialError("I–Vにゼロ交差がないためV_f候補を作れません")

    phi_candidates = (
        *_log_intersection_candidates(result, settings),
        *_derivative_candidates(result, settings),
    )
    if not phi_candidates:
        raise PotentialError("log交点とdI/dVのどちらからもPhi候補を作れません")

    selected_phi = _select_phi(phi_candidates, settings.selected_phi_candidate_id)
    selected_vf = _select_vf(
        vf_candidates,
        settings.selected_vf_candidate_id,
        selected_phi.value_v,
    )
    statuses = (selected_vf.status, selected_phi.status)
    status = (
        AnalysisStatus.VALID
        if all(item is AnalysisStatus.VALID for item in statuses)
        else AnalysisStatus.REVIEW
    )
    messages = tuple(
        message
        for message in (selected_vf.message, selected_phi.message)
        if message
    )
    return PotentialAnalysis(
        vf_candidates=vf_candidates,
        phi_candidates=phi_candidates,
        selected_vf_candidate_id=selected_vf.candidate_id,
        selected_phi_candidate_id=selected_phi.candidate_id,
        status=status,
        message=" / ".join(messages),
    )


def _zero_crossing_candidates(
    voltage_v: FloatArray,
    current_a: FloatArray,
) -> tuple[PotentialCandidate, ...]:
    found: list[tuple[float, float]] = []
    for index in range(voltage_v.size):
        current = float(current_a[index])
        if current == 0.0:
            found.append((float(voltage_v[index]), _local_slope(voltage_v, current_a, index)))
        if index == voltage_v.size - 1:
            continue
        next_current = float(current_a[index + 1])
        if current == 0.0 or next_current == 0.0 or current * next_current >= 0:
            continue
        v0 = float(voltage_v[index])
        v1 = float(voltage_v[index + 1])
        crossing = v0 - current * (v1 - v0) / (next_current - current)
        slope = abs((next_current - current) / (v1 - v0))
        found.append((crossing, slope))

    unique: list[tuple[float, float]] = []
    for value, slope in sorted(found):
        if unique and abs(value - unique[-1][0]) <= 1e-9:
            if slope > unique[-1][1]:
                unique[-1] = (value, slope)
            continue
        unique.append((value, slope))
    return tuple(
        PotentialCandidate(
            candidate_id=f"vf:{index}",
            method_id="zero_crossing",
            label=f"V_f候補 {index + 1}: {value:.6g} V",
            value_v=value,
            status=AnalysisStatus.VALID,
            score=slope,
            message=(
                "ゼロ交差が複数あります。Raw波形とI–V形状を確認してください"
                if len(unique) > 1
                else ""
            ),
        )
        for index, (value, slope) in enumerate(unique)
    )


def _local_slope(voltage_v: FloatArray, current_a: FloatArray, index: int) -> float:
    lower = max(index - 1, 0)
    upper = min(index + 1, voltage_v.size - 1)
    delta_v = float(voltage_v[upper] - voltage_v[lower])
    if delta_v == 0.0:
        return 0.0
    return abs(float(current_a[upper] - current_a[lower]) / delta_v)


def _log_intersection_candidates(
    result: PreprocessedSweep,
    settings: PotentialSettings,
) -> tuple[PotentialCandidate, ...]:
    current = result.filtered_current_a
    positive = current > 0
    low_mask = (
        positive
        & (result.voltage_v >= settings.log_fit1_min_v)
        & (result.voltage_v <= settings.log_fit1_max_v)
    )
    high_mask = (
        positive
        & (result.voltage_v >= settings.log_fit2_min_v)
        & (result.voltage_v <= settings.log_fit2_max_v)
    )
    try:
        low_fit = robust_linear_fit(
            result.voltage_v[low_mask],
            np.log10(current[low_mask]),
            minimum_points=8,
        )
        high_fit = robust_linear_fit(
            result.voltage_v[high_mask],
            np.log10(current[high_mask]),
            minimum_points=8,
        )
    except LinearFitError:
        return ()

    slope_delta = low_fit.slope - high_fit.slope
    if abs(slope_delta) <= 1e-9:
        return ()
    phi_v = (high_fit.intercept - low_fit.intercept) / slope_delta
    if not np.isfinite(phi_v):
        return ()

    in_search_range = settings.phi_search_min_v <= phi_v <= settings.phi_search_max_v
    good_linearity = low_fit.r_squared >= 0.985 and high_fit.r_squared >= 0.985
    status = (
        AnalysisStatus.VALID
        if in_search_range and good_linearity
        else AnalysisStatus.REVIEW
    )
    messages: list[str] = []
    if not in_search_range:
        messages.append("log交点がPhi探索範囲外です")
    if not good_linearity:
        messages.append("log直線FitのR²が0.985未満です")
    return (
        PotentialCandidate(
            candidate_id="phi:filtered_log_intersection",
            method_id=SummaryMethod.FILTERED_LOG.value,
            label=f"log交点: {phi_v:.6g} V",
            value_v=float(phi_v),
            status=status,
            score=min(low_fit.r_squared, high_fit.r_squared),
            message=" / ".join(messages),
            fit_low=low_fit,
            fit_high=high_fit,
        ),
    )


def _derivative_candidates(
    result: PreprocessedSweep,
    settings: PotentialSettings,
) -> tuple[PotentialCandidate, ...]:
    mask = (
        (result.voltage_v >= settings.phi_search_min_v)
        & (result.voltage_v <= settings.phi_search_max_v)
        & (result.dcurrent_dvoltage_a_per_v > 0)
    )
    indices = np.flatnonzero(mask)
    if not indices.size:
        return ()
    derivative = result.dcurrent_dvoltage_a_per_v[indices]
    peak_positions, _ = find_peaks(derivative)
    candidate_indices = indices[peak_positions]
    if not candidate_indices.size:
        candidate_indices = np.asarray(
            [indices[int(np.argmax(derivative))]],
            dtype=np.int64,
        )
    ordered = sorted(
        (int(index) for index in candidate_indices),
        key=lambda index: float(result.dcurrent_dvoltage_a_per_v[index]),
        reverse=True,
    )
    retained: list[int] = []
    for index in ordered:
        voltage = float(result.voltage_v[index])
        if any(abs(voltage - float(result.voltage_v[other])) < 0.25 for other in retained):
            continue
        retained.append(index)
        if len(retained) == 3:
            break
    return tuple(
        PotentialCandidate(
            candidate_id=f"phi:filtered_derivative_peak:{rank}",
            method_id=SummaryMethod.FILTERED_DERIVATIVE.value,
            label=f"dI/dVピーク {rank + 1}: {result.voltage_v[index]:.6g} V",
            value_v=float(result.voltage_v[index]),
            status=AnalysisStatus.VALID,
            score=float(result.dcurrent_dvoltage_a_per_v[index]),
        )
        for rank, index in enumerate(retained)
    )


def _select_phi(
    candidates: tuple[PotentialCandidate, ...],
    selected_id: str | None,
) -> PotentialCandidate:
    if selected_id is not None:
        selected = next(
            (candidate for candidate in candidates if candidate.candidate_id == selected_id),
            None,
        )
        if selected is not None:
            return selected
    log_candidate = next(
        (
            candidate
            for candidate in candidates
            if candidate.method_id == SummaryMethod.FILTERED_LOG.value
        ),
        None,
    )
    return log_candidate or max(candidates, key=lambda candidate: candidate.score)


def _select_vf(
    candidates: tuple[PotentialCandidate, ...],
    selected_id: str | None,
    phi_v: float,
) -> PotentialCandidate:
    if selected_id is not None:
        selected = next(
            (candidate for candidate in candidates if candidate.candidate_id == selected_id),
            None,
        )
        if selected is not None:
            return selected
    below_phi = tuple(candidate for candidate in candidates if candidate.value_v < phi_v)
    return max(below_phi or candidates, key=lambda candidate: candidate.value_v)


def _candidate_by_id(
    candidates: tuple[PotentialCandidate, ...],
    candidate_id: str,
) -> PotentialCandidate:
    return next(candidate for candidate in candidates if candidate.candidate_id == candidate_id)
