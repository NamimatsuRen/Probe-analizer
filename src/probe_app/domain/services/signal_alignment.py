from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from probe_app.domain.errors import SignalAlignmentError, SignalAlignmentFailure
from probe_app.domain.models.raw_series import FloatArray
from probe_app.domain.models.series_role import PhysicalSignal, SeriesRole


@dataclass(frozen=True, slots=True)
class AlignedSignals:
    """Current interpolated onto the sweep-voltage sampling axis."""

    current_series_id: str
    voltage_series_id: str
    time_s: FloatArray
    current_a: FloatArray
    sweep_voltage_v: FloatArray
    voltage_source_start_index: int
    interpolated_current: bool

    def __post_init__(self) -> None:
        arrays = (self.time_s, self.current_a, self.sweep_voltage_v)
        if any(array.ndim != 1 for array in arrays):
            raise ValueError("aligned arrays must be one-dimensional")
        if len({array.size for array in arrays}) != 1:
            raise ValueError("aligned arrays must have the same length")
        if self.time_s.size < 2:
            raise ValueError("aligned signals require at least two points")
        if self.voltage_source_start_index < 0:
            raise ValueError("voltage_source_start_index cannot be negative")


def _validate_signal(signal: PhysicalSignal, role: SeriesRole, unit: str) -> None:
    if signal.role is not role:
        raise SignalAlignmentError(
            SignalAlignmentFailure.WRONG_ROLE,
            f"expected {role.value}, got {signal.role.value}",
        )
    if signal.unit != unit:
        raise SignalAlignmentError(
            SignalAlignmentFailure.WRONG_UNIT,
            f"{role.value} must use {unit}, got {signal.unit}",
        )
    if not np.all(np.isfinite(signal.time_s)) or not np.all(np.isfinite(signal.values)):
        raise SignalAlignmentError(
            SignalAlignmentFailure.NON_FINITE_DATA,
            f"{role.value} contains NaN or infinity",
        )
    if signal.time_s.size > 1 and not np.all(np.diff(signal.time_s) > 0):
        raise SignalAlignmentError(
            SignalAlignmentFailure.NON_MONOTONIC_TIME,
            f"{role.value} time must be strictly increasing",
        )


def align_current_and_voltage(
    current: PhysicalSignal,
    sweep_voltage: PhysicalSignal,
    *,
    minimum_points: int = 2,
) -> AlignedSignals:
    """Align signals without extrapolation, using voltage time as the reference.

    Voltage samples outside the current time range are removed. Current samples
    are interpolated only when the two retained time axes are not already equal.
    """

    _validate_signal(current, SeriesRole.CURRENT, "A")
    _validate_signal(sweep_voltage, SeriesRole.SWEEP_VOLTAGE, "V")
    if minimum_points < 2:
        raise ValueError("minimum_points must be at least 2")

    overlap_start = max(float(current.time_s[0]), float(sweep_voltage.time_s[0]))
    overlap_stop = min(float(current.time_s[-1]), float(sweep_voltage.time_s[-1]))
    if overlap_stop < overlap_start:
        raise SignalAlignmentError(
            SignalAlignmentFailure.NO_TIME_OVERLAP,
            "current and sweep voltage have disjoint time ranges",
        )

    voltage_mask = (sweep_voltage.time_s >= overlap_start) & (
        sweep_voltage.time_s <= overlap_stop
    )
    retained_indices = np.flatnonzero(voltage_mask)
    if retained_indices.size < minimum_points:
        raise SignalAlignmentError(
            SignalAlignmentFailure.TOO_FEW_POINTS,
            f"overlap contains {retained_indices.size} voltage points",
        )

    source_start = int(retained_indices[0])
    source_stop = int(retained_indices[-1]) + 1
    reference_time = np.asarray(
        sweep_voltage.time_s[source_start:source_stop],
        dtype=np.float64,
    )
    reference_voltage = np.asarray(
        sweep_voltage.values[source_start:source_stop],
        dtype=np.float64,
    )

    direct = (
        current.time_s.size == reference_time.size
        and np.array_equal(current.time_s, reference_time)
    )
    if direct:
        aligned_current = np.asarray(current.values, dtype=np.float64)
    else:
        aligned_current = np.asarray(
            np.interp(reference_time, current.time_s, current.values),
            dtype=np.float64,
        )

    return AlignedSignals(
        current_series_id=current.series_id,
        voltage_series_id=sweep_voltage.series_id,
        time_s=reference_time,
        current_a=aligned_current,
        sweep_voltage_v=reference_voltage,
        voltage_source_start_index=source_start,
        interpolated_current=not direct,
    )
