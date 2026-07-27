from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from enum import StrEnum


class AnalysisStage(StrEnum):
    """Ordered stages whose downstream results can become stale."""

    PREPROCESSING = "preprocessing"
    POTENTIAL = "potential"
    SATURATION = "saturation"
    TEMPERATURE = "temperature"
    QUALITY = "quality"


ANALYSIS_STAGE_ORDER = (
    AnalysisStage.PREPROCESSING,
    AnalysisStage.POTENTIAL,
    AnalysisStage.SATURATION,
    AnalysisStage.TEMPERATURE,
    AnalysisStage.QUALITY,
)


class AnalysisStatus(StrEnum):
    """User-visible state of a record, stage, or method."""

    NOT_RUN = "not_run"
    RUNNING = "running"
    VALID = "valid"
    REVIEW = "review"
    BAD = "bad"
    ERROR = "error"
    STALE = "stale"
    EXCLUDED = "excluded"


USABLE_ANALYSIS_STATUSES = frozenset(
    (AnalysisStatus.VALID, AnalysisStatus.REVIEW)
)
FAILED_ANALYSIS_STATUSES = frozenset(
    (AnalysisStatus.BAD, AnalysisStatus.ERROR, AnalysisStatus.STALE)
)


@dataclass(frozen=True, slots=True)
class SignalAssignmentRevision:
    """One role assignment as it was when analysis started."""

    series_id: str
    scale: float
    sign: float
    output_unit: str

    def __post_init__(self) -> None:
        if not self.series_id.strip():
            raise ValueError("series_id cannot be empty")
        if not math.isfinite(self.scale) or self.scale <= 0:
            raise ValueError("scale must be finite and positive")
        if self.sign not in (-1.0, 1.0):
            raise ValueError("sign must be either -1 or 1")
        if not self.output_unit.strip():
            raise ValueError("output_unit cannot be empty")


@dataclass(frozen=True, slots=True)
class SweepSplitRevision:
    """Sweep boundaries and time alignment used by one analysis revision."""

    points_per_cycle: int
    sample_start: int
    sample_stop: int | None
    current_time_offset_s: float

    def __post_init__(self) -> None:
        if self.points_per_cycle < 2 or self.points_per_cycle % 2:
            raise ValueError("points_per_cycle must be an even integer of at least 2")
        if self.sample_start < 0:
            raise ValueError("sample_start cannot be negative")
        if self.sample_stop is not None and self.sample_stop <= self.sample_start:
            raise ValueError("sample_stop must be greater than sample_start")
        if not math.isfinite(self.current_time_offset_s):
            raise ValueError("current_time_offset_s must be finite")


@dataclass(frozen=True, slots=True)
class PreprocessingRevision:
    """Preprocessing settings that affect all downstream stages."""

    window_length: int
    polyorder: int

    def __post_init__(self) -> None:
        if self.window_length < 1:
            raise ValueError("window_length must be at least 1")
        if self.polyorder < 0:
            raise ValueError("polyorder cannot be negative")


@dataclass(frozen=True, slots=True)
class AnalysisInputRevision:
    """Complete provenance key for results derived from one Sweep."""

    folder_key: str
    shot_id: str
    sweep_id: str
    current: SignalAssignmentRevision
    sweep_voltage: SignalAssignmentRevision
    split: SweepSplitRevision
    preprocessing: PreprocessingRevision
    fit_settings: tuple[tuple[str, str], ...] = ()
    algorithm_version: str = "level3-sg-v1"
    schema_version: int = 1
    generation_id: int = 0

    def __post_init__(self) -> None:
        for name, value in (
            ("folder_key", self.folder_key),
            ("shot_id", self.shot_id),
            ("sweep_id", self.sweep_id),
            ("algorithm_version", self.algorithm_version),
        ):
            if not value.strip():
                raise ValueError(f"{name} cannot be empty")
        if self.schema_version < 1:
            raise ValueError("schema_version must be at least 1")
        if self.generation_id < 0:
            raise ValueError("generation_id cannot be negative")
        keys = [key for key, _ in self.fit_settings]
        if any(not key.strip() for key in keys):
            raise ValueError("fit setting keys cannot be empty")
        if len(keys) != len(set(keys)):
            raise ValueError("fit setting keys must be unique")
        if tuple(sorted(self.fit_settings)) != self.fit_settings:
            raise ValueError("fit_settings must be sorted by key")

    @property
    def cache_key(self) -> str:
        """Stable key used by the result store and export manifest."""

        payload = {
            "algorithm_version": self.algorithm_version,
            "current": {
                "output_unit": self.current.output_unit,
                "scale": self.current.scale,
                "series_id": self.current.series_id,
                "sign": self.current.sign,
            },
            "fit_settings": list(self.fit_settings),
            "folder_key": self.folder_key,
            "generation_id": self.generation_id,
            "preprocessing": {
                "polyorder": self.preprocessing.polyorder,
                "window_length": self.preprocessing.window_length,
            },
            "schema_version": self.schema_version,
            "shot_id": self.shot_id,
            "split": {
                "current_time_offset_s": self.split.current_time_offset_s,
                "points_per_cycle": self.split.points_per_cycle,
                "sample_start": self.split.sample_start,
                "sample_stop": self.split.sample_stop,
            },
            "sweep_id": self.sweep_id,
            "sweep_voltage": {
                "output_unit": self.sweep_voltage.output_unit,
                "scale": self.sweep_voltage.scale,
                "series_id": self.sweep_voltage.series_id,
                "sign": self.sweep_voltage.sign,
            },
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class MethodOutcome:
    """Outcome of one independent analysis method within a stage."""

    method_id: str
    status: AnalysisStatus
    message: str = ""
    selected_candidate_id: str | None = None
    manual_override: bool = False
    metrics: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if not self.method_id.strip():
            raise ValueError("method_id cannot be empty")
        metric_names = [name for name, _ in self.metrics]
        if any(not name.strip() for name in metric_names):
            raise ValueError("metric names cannot be empty")
        if len(metric_names) != len(set(metric_names)):
            raise ValueError("metric names must be unique")
        if tuple(sorted(self.metrics)) != self.metrics:
            raise ValueError("metrics must be sorted by name")
        if any(not math.isfinite(value) for _, value in self.metrics):
            raise ValueError("metric values must be finite")

    def mark_stale(self, reason: str) -> MethodOutcome:
        return replace(self, status=AnalysisStatus.STALE, message=reason)


@dataclass(frozen=True, slots=True)
class StageResult:
    """Result and method-level diagnostics for one analysis stage."""

    stage: AnalysisStage
    status: AnalysisStatus
    methods: tuple[MethodOutcome, ...] = ()
    message: str = ""

    def __post_init__(self) -> None:
        method_ids = [method.method_id for method in self.methods]
        if len(method_ids) != len(set(method_ids)):
            raise ValueError("method IDs must be unique within a stage")

    @property
    def partial_success(self) -> bool:
        statuses = {method.status for method in self.methods}
        return bool(statuses & USABLE_ANALYSIS_STATUSES) and bool(
            statuses & FAILED_ANALYSIS_STATUSES
        )

    def mark_stale(self, reason: str) -> StageResult:
        return replace(
            self,
            status=AnalysisStatus.STALE,
            methods=tuple(method.mark_stale(reason) for method in self.methods),
            message=reason,
        )


def downstream_stages(stage: AnalysisStage) -> tuple[AnalysisStage, ...]:
    """Return ``stage`` and every result that depends on it."""

    index = ANALYSIS_STAGE_ORDER.index(stage)
    return ANALYSIS_STAGE_ORDER[index:]


@dataclass(frozen=True, slots=True)
class SweepAnalysisRecord:
    """Revisioned metadata for one Sweep without duplicating numerical arrays."""

    revision: AnalysisInputRevision
    status: AnalysisStatus = AnalysisStatus.NOT_RUN
    stages: tuple[StageResult, ...] = ()
    message: str = ""
    exclusion_reason: str = ""

    def __post_init__(self) -> None:
        stage_ids = [stage.stage for stage in self.stages]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("analysis stages must be unique")
        if self.status is AnalysisStatus.EXCLUDED and not self.exclusion_reason.strip():
            raise ValueError("excluded records require an exclusion reason")

    @classmethod
    def running(cls, revision: AnalysisInputRevision) -> SweepAnalysisRecord:
        return cls(revision=revision, status=AnalysisStatus.RUNNING)

    @property
    def partial_success(self) -> bool:
        return any(stage.partial_success for stage in self.stages)

    @property
    def is_usable(self) -> bool:
        return self.status in USABLE_ANALYSIS_STATUSES

    def stage_result(self, stage: AnalysisStage) -> StageResult | None:
        return next((result for result in self.stages if result.stage is stage), None)

    def with_stage_result(
        self,
        result: StageResult,
        *,
        overall_status: AnalysisStatus | None = None,
    ) -> SweepAnalysisRecord:
        remaining = tuple(item for item in self.stages if item.stage is not result.stage)
        ordered = tuple(
            sorted(
                (*remaining, result),
                key=lambda item: ANALYSIS_STAGE_ORDER.index(item.stage),
            )
        )
        return replace(
            self,
            status=result.status if overall_status is None else overall_status,
            stages=ordered,
            message=result.message,
        )

    def mark_stale_from(
        self,
        stage: AnalysisStage,
        reason: str,
    ) -> SweepAnalysisRecord:
        affected = frozenset(downstream_stages(stage))
        updated = tuple(
            result.mark_stale(reason) if result.stage in affected else result
            for result in self.stages
        )
        return replace(
            self,
            status=(
                AnalysisStatus.EXCLUDED
                if self.status is AnalysisStatus.EXCLUDED
                else AnalysisStatus.STALE
            ),
            stages=updated,
            message=reason,
        )

    def exclude(self, reason: str) -> SweepAnalysisRecord:
        if not reason.strip():
            raise ValueError("exclusion reason cannot be empty")
        return replace(
            self,
            status=AnalysisStatus.EXCLUDED,
            exclusion_reason=reason,
            message=reason,
        )

    def restore(self) -> SweepAnalysisRecord:
        status = (
            AnalysisStatus.STALE
            if any(stage.status is AnalysisStatus.STALE for stage in self.stages)
            else AnalysisStatus.REVIEW
        )
        return replace(self, status=status, exclusion_reason="")
