from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from probe_app.domain.models.raw_series import FloatArray


class SweepDirection(StrEnum):
    """Voltage direction in acquisition order."""

    UP = "up"
    DOWN = "down"


class SweepExclusionReason(StrEnum):
    """Why a source interval was not emitted as a valid Sweep."""

    ALIGNMENT_PREFIX = "alignment_prefix"
    ALIGNMENT_SUFFIX = "alignment_suffix"
    INCOMPLETE_SWEEP = "incomplete_sweep"


@dataclass(frozen=True, slots=True)
class SweepExclusion:
    """A non-empty source interval intentionally excluded from valid Sweeps."""

    voltage_series_id: str
    source_start_index: int
    source_stop_index: int
    start_time_s: float
    end_time_s: float
    reason: SweepExclusionReason
    detail: str

    def __post_init__(self) -> None:
        if not self.voltage_series_id.strip():
            raise ValueError("voltage_series_id cannot be empty")
        if self.source_start_index < 0:
            raise ValueError("source_start_index cannot be negative")
        if self.source_stop_index <= self.source_start_index:
            raise ValueError("source_stop_index must be greater than source_start_index")
        if not np.isfinite(self.start_time_s) or not np.isfinite(self.end_time_s):
            raise ValueError("exclusion times must be finite")
        if self.end_time_s < self.start_time_s:
            raise ValueError("end_time_s cannot precede start_time_s")
        if not self.detail.strip():
            raise ValueError("detail cannot be empty")

    @property
    def point_count(self) -> int:
        return self.source_stop_index - self.source_start_index


@dataclass(frozen=True, slots=True)
class Sweep:
    """One half-cycle of an I–V acquisition.

    ``source_start_index`` is inclusive and ``source_stop_index`` is exclusive.
    Stored arrays remain in acquisition order so they map directly to the raw
    time series. The ``iv_*`` properties expose the legacy, voltage-ascending
    order used by later analysis.
    """

    sweep_id: str
    current_series_id: str
    voltage_series_id: str
    source_start_index: int
    source_stop_index: int
    direction: SweepDirection
    time_s: FloatArray
    voltage_v: FloatArray
    current_a: FloatArray

    def __post_init__(self) -> None:
        if not self.sweep_id.strip():
            raise ValueError("sweep_id cannot be empty")
        if not self.current_series_id.strip() or not self.voltage_series_id.strip():
            raise ValueError("source series IDs cannot be empty")
        if self.source_start_index < 0:
            raise ValueError("source_start_index cannot be negative")
        if self.source_stop_index <= self.source_start_index:
            raise ValueError("source_stop_index must be greater than source_start_index")
        arrays = (self.time_s, self.voltage_v, self.current_a)
        if any(array.ndim != 1 for array in arrays):
            raise ValueError("Sweep arrays must be one-dimensional")
        expected = self.source_stop_index - self.source_start_index
        if any(array.size != expected for array in arrays):
            raise ValueError("Sweep arrays must match the half-open source boundary")
        if not all(np.all(np.isfinite(array)) for array in arrays):
            raise ValueError("Sweep arrays must contain only finite values")
        if self.time_s.size > 1 and not np.all(np.diff(self.time_s) > 0):
            raise ValueError("Sweep time must be strictly increasing in acquisition order")

    @property
    def point_count(self) -> int:
        return int(self.time_s.size)

    @property
    def mid_time_s(self) -> float:
        return float(np.median(self.time_s))

    @property
    def iv_voltage_v(self) -> FloatArray:
        return self.voltage_v if self.direction is SweepDirection.UP else self.voltage_v[::-1]

    @property
    def iv_current_a(self) -> FloatArray:
        return self.current_a if self.direction is SweepDirection.UP else self.current_a[::-1]

    @property
    def iv_time_s(self) -> FloatArray:
        return self.time_s if self.direction is SweepDirection.UP else self.time_s[::-1]
