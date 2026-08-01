from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class ProbePositionUnit(StrEnum):
    """Supported physical units for an explicitly entered probe position."""

    MILLIMETER = "mm"
    CENTIMETER = "cm"
    METER = "m"


_TO_MILLIMETER = {
    ProbePositionUnit.MILLIMETER: 1.0,
    ProbePositionUnit.CENTIMETER: 10.0,
    ProbePositionUnit.METER: 1_000.0,
}


@dataclass(frozen=True, slots=True)
class ProbePosition:
    """A user-supplied position; it is never inferred from a file or shot name."""

    value: float
    unit: ProbePositionUnit = ProbePositionUnit.MILLIMETER
    label: str = ""

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("probe position must be finite")

    @property
    def millimeters(self) -> float:
        return self.value * _TO_MILLIMETER[self.unit]


@dataclass(frozen=True, slots=True)
class ShotMetadata:
    """Typed metadata for one shot inside one measurement folder."""

    folder_key: str
    shot_id: str
    position: ProbePosition | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.folder_key.strip():
            raise ValueError("folder_key cannot be empty")
        if not self.shot_id.strip():
            raise ValueError("shot_id cannot be empty")

