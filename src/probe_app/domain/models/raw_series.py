from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class RawSeriesDescriptor:
    """Lightweight information discovered without loading the waveform."""

    series_id: str
    shot_id: str
    channel_id: str
    header_path: Path
    data_path: Path
    sample_count: int
    value_unit: str
    time_unit: str
    trace_name: str = ""
    recorded_at: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        if self.trace_name and self.trace_name.upper() != "CH1":
            return f"{self.channel_id} — {self.trace_name}"
        return self.channel_id


@dataclass(frozen=True, slots=True)
class RawSeries:
    """One calibrated raw waveform and its sampling axis."""

    descriptor: RawSeriesDescriptor
    time_s: FloatArray
    values: FloatArray

    def __post_init__(self) -> None:
        if self.time_s.ndim != 1 or self.values.ndim != 1:
            raise ValueError("time_s and values must be one-dimensional")
        if self.time_s.size != self.values.size:
            raise ValueError("time_s and values must have the same length")
        if self.time_s.size == 0:
            raise ValueError("a raw series cannot be empty")

    @property
    def point_count(self) -> int:
        return int(self.values.size)

    @property
    def time_range_s(self) -> tuple[float, float]:
        return float(self.time_s[0]), float(self.time_s[-1])

    @property
    def value_range(self) -> tuple[float, float]:
        finite = self.values[np.isfinite(self.values)]
        if finite.size == 0:
            return float("nan"), float("nan")
        return float(np.min(finite)), float(np.max(finite))
