from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from probe_app.domain.models.raw_series import RawSeriesDescriptor


@dataclass(frozen=True, slots=True)
class ScanProblem:
    path: Path
    message: str


@dataclass(frozen=True, slots=True)
class FolderCatalog:
    root: Path
    series: tuple[RawSeriesDescriptor, ...]
    problems: tuple[ScanProblem, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.series

    @property
    def is_partial(self) -> bool:
        return bool(self.series and self.problems)

    @property
    def shots(self) -> tuple[str, ...]:
        return tuple(sorted({item.shot_id for item in self.series}))

    def series_for_shot(self, shot_id: str) -> tuple[RawSeriesDescriptor, ...]:
        return tuple(item for item in self.series if item.shot_id == shot_id)

    def find(self, series_id: str) -> RawSeriesDescriptor | None:
        return next((item for item in self.series if item.series_id == series_id), None)
