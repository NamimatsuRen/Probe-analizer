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


class SummaryMetric(StrEnum):
    """Quantities plotted and aggregated in the Summary workspace."""

    TI = "ti"
    PHI = "phi"


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
    phi_status: AnalysisStatus | None = None
    ti_status: AnalysisStatus | None = None
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

    def metric_value(self, metric: SummaryMetric) -> float | None:
        return self.ti_ev if metric is SummaryMetric.TI else self.phi_v

    def metric_status(self, metric: SummaryMetric) -> AnalysisStatus:
        status = self.ti_status if metric is SummaryMetric.TI else self.phi_status
        return self.status if status is None else status


@dataclass(frozen=True, slots=True)
class SummaryPlotPoint:
    """One visible point, including values excluded from the default aggregate."""

    number: int
    sweep_id: str
    method: SummaryMethod
    metric: SummaryMetric
    value: float
    status: AnalysisStatus
    included: bool

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError("number must be at least 1")
        if not self.sweep_id.strip():
            raise ValueError("sweep_id cannot be empty")
        if not math.isfinite(self.value):
            raise ValueError("plot value must be finite")


@dataclass(frozen=True, slots=True)
class SummaryMetricStatistics:
    """Method-specific aggregate with an explicit denominator."""

    method: SummaryMethod
    metric: SummaryMetric
    count: int
    scope_count: int
    mean: float | None = None
    sample_std: float | None = None
    minimum: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        if self.count < 0 or self.scope_count < 0:
            raise ValueError("aggregate counts cannot be negative")
        if self.count > self.scope_count:
            raise ValueError("count cannot exceed scope_count")
        for name, value in (
            ("mean", self.mean),
            ("sample_std", self.sample_std),
            ("minimum", self.minimum),
            ("maximum", self.maximum),
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

    def plot_points(
        self,
        metric: SummaryMetric,
        method: SummaryMethod,
    ) -> tuple[SummaryPlotPoint, ...]:
        points: list[SummaryPlotPoint] = []
        for row in self.rows:
            method_value = next(
                (value for value in row.methods if value.method is method),
                None,
            )
            if method_value is None:
                continue
            value = method_value.metric_value(metric)
            if value is None:
                continue
            status = method_value.metric_status(metric)
            included = (
                row.current_revision
                and row.status in (AnalysisStatus.VALID, AnalysisStatus.REVIEW)
                and status in (AnalysisStatus.VALID, AnalysisStatus.REVIEW)
                and (metric is SummaryMetric.PHI or 0.0 < value < 5.0)
            )
            points.append(
                SummaryPlotPoint(
                    number=row.number,
                    sweep_id=row.sweep_id,
                    method=method,
                    metric=metric,
                    value=value,
                    status=status,
                    included=included,
                )
            )
        return tuple(points)

    def metric_statistics(
        self,
        metric: SummaryMetric,
    ) -> tuple[SummaryMetricStatistics, ...]:
        statistics: list[SummaryMetricStatistics] = []
        for method in SUMMARY_METHOD_ORDER:
            values = tuple(
                point.value
                for point in self.plot_points(metric, method)
                if point.included
            )
            if values:
                mean = sum(values) / len(values)
                sample_std = (
                    math.sqrt(
                        sum((value - mean) ** 2 for value in values)
                        / (len(values) - 1)
                    )
                    if len(values) > 1
                    else None
                )
                minimum = min(values)
                maximum = max(values)
            else:
                mean = None
                sample_std = None
                minimum = None
                maximum = None
            statistics.append(
                SummaryMetricStatistics(
                    method=method,
                    metric=metric,
                    count=len(values),
                    scope_count=len(self.rows),
                    mean=mean,
                    sample_std=sample_std,
                    minimum=minimum,
                    maximum=maximum,
                )
            )
        return tuple(statistics)
