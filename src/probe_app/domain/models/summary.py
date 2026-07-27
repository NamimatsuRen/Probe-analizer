from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from probe_app.domain.models.analysis_result import AnalysisStatus
from probe_app.domain.models.sweep import SweepDirection


class SummaryScopeKind(StrEnum):
    """Explicit aggregation scopes used by the Summary workspace."""

    CURRENT_SHOT = "current_shot"
    LOADED_SHOTS = "loaded_shots"
    POSITION = "position"


class SummaryMethod(StrEnum):
    """Stable IDs for the four legacy-compatible Phi/T_i result paths."""

    FILTERED_LOG = "filtered_log_intersection"
    FILTERED_DERIVATIVE = "filtered_derivative_peak"
    RAW_LOG = "raw_log_intersection"
    RAW_DERIVATIVE = "raw_multiscale_derivative"


SUMMARY_METHOD_ORDER = (
    SummaryMethod.FILTERED_LOG,
    SummaryMethod.FILTERED_DERIVATIVE,
    SummaryMethod.RAW_LOG,
    SummaryMethod.RAW_DERIVATIVE,
)


@dataclass(frozen=True, slots=True)
class SummaryScope:
    """Scope is independent from the single-Sweep Data/Analysis selection."""

    kind: SummaryScopeKind
    folder_key: str
    shot_ids: tuple[str, ...]
    current_revision_only: bool = True

    def __post_init__(self) -> None:
        if not self.folder_key.strip():
            raise ValueError("folder_key cannot be empty")
        if not self.shot_ids:
            raise ValueError("at least one shot_id is required")
        if any(not shot_id.strip() for shot_id in self.shot_ids):
            raise ValueError("shot_ids cannot contain an empty value")
        if len(self.shot_ids) != len(set(self.shot_ids)):
            raise ValueError("shot_ids must be unique")
        if self.kind is SummaryScopeKind.CURRENT_SHOT and len(self.shot_ids) != 1:
            raise ValueError("current-shot scope requires exactly one shot_id")


@dataclass(frozen=True, slots=True)
class SummaryMethodValue:
    """One method's values and quality without silently coercing missing values."""

    method: SummaryMethod
    status: AnalysisStatus
    phi_v: float | None = None
    ti_ev: float | None = None
    k_per_v: float | None = None
    k_source: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        for name, value in (
            ("phi_v", self.phi_v),
            ("ti_ev", self.ti_ev),
            ("k_per_v", self.k_per_v),
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite when present")


@dataclass(frozen=True, slots=True)
class SummaryRow:
    """Read-only projection for one Sweep in the selected summary scope."""

    number: int
    sweep_id: str
    shot_id: str
    direction: SweepDirection
    start_ms: float
    stop_ms: float
    point_count: int
    status: AnalysisStatus
    current_revision: bool
    revision_key: str = ""
    message: str = ""
    exclusion_reason: str = ""
    methods: tuple[SummaryMethodValue, ...] = ()

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError("number must be at least 1")
        if not self.sweep_id.strip() or not self.shot_id.strip():
            raise ValueError("sweep_id and shot_id cannot be empty")
        if self.point_count < 1:
            raise ValueError("point_count must be at least 1")
        if not math.isfinite(self.start_ms) or not math.isfinite(self.stop_ms):
            raise ValueError("summary times must be finite")
        method_ids = [method.method for method in self.methods]
        if len(method_ids) != len(set(method_ids)):
            raise ValueError("summary method IDs must be unique")

    @property
    def ti_value_count(self) -> int:
        return sum(method.ti_ev is not None for method in self.methods)

    @property
    def phi_value_count(self) -> int:
        return sum(method.phi_v is not None for method in self.methods)


@dataclass(frozen=True, slots=True)
class SummarySnapshot:
    """Complete, non-lossy result of one Summary query."""

    scope: SummaryScope
    rows: tuple[SummaryRow, ...]

    @property
    def status_counts(self) -> tuple[tuple[AnalysisStatus, int], ...]:
        return tuple(
            (status, sum(row.status is status for row in self.rows))
            for status in AnalysisStatus
        )

    @property
    def aggregate_row_count(self) -> int:
        """Rows eligible for default aggregates before metric-specific filtering."""

        return sum(
            row.current_revision
            and row.status in (AnalysisStatus.VALID, AnalysisStatus.REVIEW)
            for row in self.rows
        )

