from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from probe_app.analysis.fitting import (
    LinearFitError,
    RobustLinearFit,
    robust_linear_fit,
)
from probe_app.analysis.preprocessing import PreprocessedSweep
from probe_app.analysis.settings import SaturationSettings
from probe_app.domain.models.analysis_result import AnalysisStatus


class SaturationError(ValueError):
    """A user-correctable ion/electron saturation fit failure."""


@dataclass(frozen=True, slots=True)
class SaturationAnalysis:
    """Two robust saturation lines and their V_f-normalized parameters."""

    ion_fit: RobustLinearFit
    electron_fit: RobustLinearFit
    vf_v: float
    ion_current_at_vf_a: float
    electron_current_at_vf_a: float
    isat_i_a: float
    isat_e_a: float
    r_ratio: float
    k_per_v: float
    status: AnalysisStatus
    message: str = ""


def fit_saturation_regions(
    result: PreprocessedSweep,
    vf_v: float,
    settings: SaturationSettings | None = None,
) -> SaturationAnalysis:
    """Fit ion/electron ranges and extrapolate both lines to V_f."""

    settings = settings or SaturationSettings()
    ion_mask = (
        (result.voltage_v >= settings.ion_min_v)
        & (result.voltage_v <= settings.ion_max_v)
    )
    electron_mask = (
        (result.voltage_v >= settings.electron_min_v)
        & (result.voltage_v <= settings.electron_max_v)
    )
    try:
        ion_fit = robust_linear_fit(
            result.voltage_v[ion_mask],
            result.filtered_current_a[ion_mask],
            minimum_points=8,
        )
        electron_fit = robust_linear_fit(
            result.voltage_v[electron_mask],
            result.filtered_current_a[electron_mask],
            minimum_points=8,
        )
    except LinearFitError as error:
        raise SaturationError(str(error)) from error

    ion_current = float(ion_fit.evaluate(vf_v))
    electron_current = float(electron_fit.evaluate(vf_v))
    isat_i = abs(ion_current)
    isat_e = abs(electron_current)
    epsilon = np.finfo(np.float64).eps
    if isat_i <= epsilon:
        raise SaturationError("V_fでのイオン飽和電流が0に近くRを計算できません")
    r_ratio = isat_e / isat_i
    k_per_v = 0.0 if isat_e <= epsilon else abs(electron_fit.slope / isat_e)
    if not np.isfinite(r_ratio) or not np.isfinite(k_per_v):
        raise SaturationError("RまたはKが非有限値になりました")

    messages: list[str] = []
    if not settings.r_min <= r_ratio <= settings.r_max:
        messages.append(
            f"R={r_ratio:.4g} が品質範囲 "
            f"{settings.r_min:.4g}–{settings.r_max:.4g} 外です"
        )
    if not settings.k_min_per_v <= k_per_v <= settings.k_max_per_v:
        messages.append(
            f"K={k_per_v:.4g} V⁻¹ が品質範囲 "
            f"{settings.k_min_per_v:.4g}–{settings.k_max_per_v:.4g} 外です"
        )
    status = AnalysisStatus.BAD if messages else AnalysisStatus.VALID
    return SaturationAnalysis(
        ion_fit=ion_fit,
        electron_fit=electron_fit,
        vf_v=vf_v,
        ion_current_at_vf_a=ion_current,
        electron_current_at_vf_a=electron_current,
        isat_i_a=isat_i,
        isat_e_a=isat_e,
        r_ratio=r_ratio,
        k_per_v=k_per_v,
        status=status,
        message=" / ".join(messages),
    )
