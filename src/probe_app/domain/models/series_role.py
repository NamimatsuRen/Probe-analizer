from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from probe_app.domain.models.raw_series import FloatArray, RawSeries


class SeriesRole(StrEnum):
    """Physical meaning assigned by the user to a discovered raw series."""

    CURRENT = "current"
    SWEEP_VOLTAGE = "sweep_voltage"


@dataclass(frozen=True, slots=True)
class SignalTransform:
    """Explicit device conversion applied after header calibration."""

    scale: float
    sign: float
    output_unit: str

    def __post_init__(self) -> None:
        if not np.isfinite(self.scale) or self.scale <= 0:
            raise ValueError("scale must be a finite positive number")
        if self.sign not in (-1.0, 1.0):
            raise ValueError("sign must be either -1 or 1")
        if not self.output_unit.strip():
            raise ValueError("output_unit cannot be empty")

    def apply(self, values: FloatArray) -> FloatArray:
        return np.asarray(values, dtype=np.float64) * self.scale * self.sign


def legacy_current_transform(*, sign: float) -> SignalTransform:
    """Reproduce the old current conversion without making it an input default."""

    return SignalTransform(scale=1.0 / 20.0, sign=sign, output_unit="A")


def legacy_sweep_voltage_transform() -> SignalTransform:
    """Reproduce the old sweep-voltage conversion without basename coupling."""

    return SignalTransform(scale=100.0, sign=1.0, output_unit="V")


@dataclass(frozen=True, slots=True)
class AssignedSeries:
    """One raw series assigned to one physical role."""

    role: SeriesRole
    series_id: str
    transform: SignalTransform

    def __post_init__(self) -> None:
        if not self.series_id.strip():
            raise ValueError("series_id cannot be empty")


@dataclass(frozen=True, slots=True)
class PhysicalSignal:
    """A loaded series after an explicit role-specific conversion."""

    role: SeriesRole
    series_id: str
    unit: str
    time_s: FloatArray
    values: FloatArray

    def __post_init__(self) -> None:
        if self.time_s.ndim != 1 or self.values.ndim != 1:
            raise ValueError("time_s and values must be one-dimensional")
        if self.time_s.size != self.values.size:
            raise ValueError("time_s and values must have the same length")
        if self.time_s.size == 0:
            raise ValueError("a physical signal cannot be empty")


@dataclass(frozen=True, slots=True)
class SeriesRoleAssignments:
    """Role configuration independent from folder discovery and file names."""

    items: tuple[AssignedSeries, ...] = ()

    def __post_init__(self) -> None:
        roles = [item.role for item in self.items]
        series_ids = [item.series_id for item in self.items]
        if len(roles) != len(set(roles)):
            raise ValueError("each role can be assigned only once")
        if len(series_ids) != len(set(series_ids)):
            raise ValueError("one series cannot be assigned to multiple roles")

    def for_role(self, role: SeriesRole) -> AssignedSeries | None:
        return next((item for item in self.items if item.role is role), None)

    @property
    def is_complete(self) -> bool:
        return all(self.for_role(role) is not None for role in SeriesRole)

    @property
    def unassigned_roles(self) -> tuple[SeriesRole, ...]:
        return tuple(role for role in SeriesRole if self.for_role(role) is None)

    def assign(self, assignment: AssignedSeries) -> SeriesRoleAssignments:
        remaining = tuple(item for item in self.items if item.role is not assignment.role)
        return SeriesRoleAssignments((*remaining, assignment))

    def prepare(self, role: SeriesRole, series: RawSeries) -> PhysicalSignal:
        assignment = self.for_role(role)
        if assignment is None:
            raise ValueError(f"{role.value} is not assigned")
        if assignment.series_id != series.descriptor.series_id:
            raise ValueError(
                f"{role.value} expects {assignment.series_id}, "
                f"not {series.descriptor.series_id}"
            )
        return PhysicalSignal(
            role=role,
            series_id=assignment.series_id,
            unit=assignment.transform.output_unit,
            time_s=np.asarray(series.time_s, dtype=np.float64),
            values=assignment.transform.apply(series.values),
        )
