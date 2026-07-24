from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import savgol_filter

from probe_app.domain.models.raw_series import FloatArray
from probe_app.domain.models.sweep import Sweep


class PreprocessingError(ValueError):
    """A user-correctable failure while preprocessing one Sweep."""


@dataclass(frozen=True, slots=True)
class SavitzkyGolaySettings:
    """Configuration for Level 3 smoothing and differentiation."""

    window_length: int = 501
    polyorder: int = 3

    def __post_init__(self) -> None:
        if self.window_length < 1:
            raise ValueError("window_length must be at least 1")
        if self.polyorder < 0:
            raise ValueError("polyorder cannot be negative")


@dataclass(frozen=True, slots=True)
class PreprocessedSweep:
    """Raw, smoothed and differentiated values sharing one voltage axis."""

    sweep_id: str
    voltage_v: FloatArray
    raw_current_a: FloatArray
    filtered_current_a: FloatArray
    dcurrent_dvoltage_a_per_v: FloatArray
    requested_window_length: int
    used_window_length: int
    polyorder: int
    voltage_step_v: float
    max_spacing_deviation_fraction: float

    def __post_init__(self) -> None:
        if not self.sweep_id.strip():
            raise ValueError("sweep_id cannot be empty")
        arrays = (
            self.voltage_v,
            self.raw_current_a,
            self.filtered_current_a,
            self.dcurrent_dvoltage_a_per_v,
        )
        if any(array.ndim != 1 for array in arrays):
            raise ValueError("preprocessed arrays must be one-dimensional")
        if not self.voltage_v.size:
            raise ValueError("preprocessed arrays cannot be empty")
        if any(array.size != self.voltage_v.size for array in arrays):
            raise ValueError("preprocessed arrays must have the same length")
        if not all(np.all(np.isfinite(array)) for array in arrays):
            raise ValueError("preprocessed arrays must contain only finite values")
        if self.voltage_v.size > 1 and self.voltage_v[-1] <= self.voltage_v[0]:
            raise ValueError("preprocessed voltage must increase overall")
        if self.used_window_length % 2 != 1:
            raise ValueError("used_window_length must be odd")
        if self.used_window_length <= self.polyorder:
            raise ValueError("used_window_length must be greater than polyorder")
        if not np.isfinite(self.voltage_step_v) or self.voltage_step_v <= 0:
            raise ValueError("voltage_step_v must be finite and positive")
        if (
            not np.isfinite(self.max_spacing_deviation_fraction)
            or self.max_spacing_deviation_fraction < 0
        ):
            raise ValueError(
                "max_spacing_deviation_fraction must be finite and non-negative"
            )

    @property
    def spacing_warning(self) -> str:
        """Explain when the uniform-grid SG assumption deserves review."""

        if self.max_spacing_deviation_fraction <= 0.05:
            return ""
        return (
            "電圧刻みのばらつきが平均刻みの"
            f"{self.max_spacing_deviation_fraction:.1%}です。"
            "dI/dVは等間隔近似のため確認してください。"
        )


def safe_savgol_window(
    point_count: int,
    settings: SavitzkyGolaySettings,
) -> int:
    """Return the largest valid odd window no greater than the request/data."""

    if point_count <= settings.polyorder + 1:
        raise PreprocessingError(
            f"点数が不足しています（{point_count}点）。"
            f"{settings.polyorder}次では最低{settings.polyorder + 2}点必要です。"
        )

    window = min(settings.window_length, point_count)
    if window % 2 == 0:
        window -= 1

    if window <= settings.polyorder:
        window = settings.polyorder + 2
        if window % 2 == 0:
            window += 1

    if window > point_count:
        window = point_count if point_count % 2 == 1 else point_count - 1

    if window <= settings.polyorder:
        raise PreprocessingError(
            "有効なSavitzky–Golay窓を作れません。"
            "点数を増やすか多項式次数を下げてください。"
        )
    return window


def preprocess_sweep(
    sweep: Sweep,
    settings: SavitzkyGolaySettings | None = None,
) -> PreprocessedSweep:
    """Smooth current and calculate dI/dV in voltage-ascending order.

    The derivative intentionally follows the legacy rule: voltage spacing is
    represented by the endpoint-average spacing. The returned spacing
    deviation makes that approximation visible to the user.
    """

    settings = settings or SavitzkyGolaySettings()
    voltage_v = np.array(sweep.iv_voltage_v, dtype=np.float64, copy=True)
    raw_current_a = np.array(sweep.iv_current_a, dtype=np.float64, copy=True)
    if voltage_v.size != raw_current_a.size:
        raise PreprocessingError("電圧と電流の点数が一致しません。")
    if not np.all(np.isfinite(voltage_v)) or not np.all(np.isfinite(raw_current_a)):
        raise PreprocessingError("電圧または電流に非有限値が含まれています。")
    if voltage_v.size < 2:
        raise PreprocessingError("微分には2点以上必要です。")

    voltage_steps = np.diff(voltage_v)
    if voltage_v[-1] <= voltage_v[0]:
        raise PreprocessingError(
            "電圧の終点が始点以下です。Sweep方向と分割結果を確認してください。"
        )

    voltage_step_v = float((voltage_v[-1] - voltage_v[0]) / (voltage_v.size - 1))
    if not np.isfinite(voltage_step_v) or voltage_step_v <= 0:
        raise PreprocessingError("有効な電圧刻みを計算できません。")
    max_spacing_deviation_fraction = float(
        np.max(np.abs(voltage_steps - voltage_step_v)) / voltage_step_v
    )
    used_window = safe_savgol_window(voltage_v.size, settings)

    filtered_current_a = np.asarray(
        savgol_filter(
            raw_current_a,
            window_length=used_window,
            polyorder=settings.polyorder,
            deriv=0,
            mode="interp",
        ),
        dtype=np.float64,
    )
    derivative_a_per_v = np.asarray(
        savgol_filter(
            raw_current_a,
            window_length=used_window,
            polyorder=settings.polyorder,
            deriv=1,
            delta=voltage_step_v,
            mode="interp",
        ),
        dtype=np.float64,
    )

    return PreprocessedSweep(
        sweep_id=sweep.sweep_id,
        voltage_v=voltage_v,
        raw_current_a=raw_current_a,
        filtered_current_a=filtered_current_a,
        dcurrent_dvoltage_a_per_v=derivative_a_per_v,
        requested_window_length=settings.window_length,
        used_window_length=used_window,
        polyorder=settings.polyorder,
        voltage_step_v=voltage_step_v,
        max_spacing_deviation_fraction=max_spacing_deviation_fraction,
    )
