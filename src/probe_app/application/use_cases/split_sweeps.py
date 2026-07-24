from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from probe_app.domain.errors import OperationCancelled
from probe_app.domain.models.raw_series import RawSeriesDescriptor
from probe_app.domain.models.series_role import SeriesRole, SeriesRoleAssignments
from probe_app.domain.models.sweep import Sweep
from probe_app.domain.services.signal_alignment import align_current_and_voltage
from probe_app.domain.services.sweep_splitter import (
    LegacySweepSplitParameters,
    split_legacy_sweeps,
)
from probe_app.infrastructure.readers.panta_reader import PantaRawReader


@dataclass(frozen=True, slots=True)
class SweepSplitRequest:
    """Everything required to split sweeps without consulting a JSON file."""

    current_descriptor: RawSeriesDescriptor
    voltage_descriptor: RawSeriesDescriptor
    assignments: SeriesRoleAssignments
    parameters: LegacySweepSplitParameters

    def __post_init__(self) -> None:
        if self.current_descriptor.shot_id != self.voltage_descriptor.shot_id:
            raise ValueError("current and sweep voltage must belong to the same shot")
        current = self.assignments.for_role(SeriesRole.CURRENT)
        voltage = self.assignments.for_role(SeriesRole.SWEEP_VOLTAGE)
        if current is None or voltage is None:
            raise ValueError("current and sweep voltage must both be assigned")
        if current.series_id != self.current_descriptor.series_id:
            raise ValueError("current assignment and descriptor do not match")
        if voltage.series_id != self.voltage_descriptor.series_id:
            raise ValueError("sweep-voltage assignment and descriptor do not match")


@dataclass(frozen=True, slots=True)
class SweepSplitResult:
    """Background-safe output consumed by state and later Sweep UI."""

    sweeps: tuple[Sweep, ...]
    current_series_id: str
    voltage_series_id: str
    interpolated_current: bool
    parameters: LegacySweepSplitParameters

    @property
    def sweep_count(self) -> int:
        return len(self.sweeps)


class SplitSweeps:
    """Load two assigned series, align them, then split complete half-cycles."""

    def __init__(self, reader: PantaRawReader | None = None) -> None:
        self._reader = reader or PantaRawReader()

    def execute(
        self,
        request: SweepSplitRequest,
        *,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> SweepSplitResult:
        self._raise_if_cancelled(is_cancelled)
        current_raw = self._reader.read(
            request.current_descriptor,
            is_cancelled=is_cancelled,
        )
        current = request.assignments.prepare(SeriesRole.CURRENT, current_raw)

        self._raise_if_cancelled(is_cancelled)
        voltage_raw = self._reader.read(
            request.voltage_descriptor,
            is_cancelled=is_cancelled,
        )
        voltage = request.assignments.prepare(SeriesRole.SWEEP_VOLTAGE, voltage_raw)

        self._raise_if_cancelled(is_cancelled)
        aligned = align_current_and_voltage(current, voltage)
        self._raise_if_cancelled(is_cancelled)
        sweeps = split_legacy_sweeps(aligned, request.parameters)
        self._raise_if_cancelled(is_cancelled)

        return SweepSplitResult(
            sweeps=sweeps,
            current_series_id=aligned.current_series_id,
            voltage_series_id=aligned.voltage_series_id,
            interpolated_current=aligned.interpolated_current,
            parameters=request.parameters,
        )

    @staticmethod
    def _raise_if_cancelled(
        is_cancelled: Callable[[], bool] | None,
    ) -> None:
        if is_cancelled is not None and is_cancelled():
            raise OperationCancelled()
