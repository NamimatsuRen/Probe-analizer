from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from enum import StrEnum

from probe_app.domain.models.analysis_result import AnalysisStatus
from probe_app.domain.models.summary import SummaryMethod


class ExportFigureType(StrEnum):
    """Paper figure recipes supported by the Level 8 renderer contract."""

    IV = "iv"
    FIT = "fit"
    TREND = "trend"
    POSITION = "position"
    METHOD_COMPARISON = "method_comparison"


class ExportDataVariant(StrEnum):
    """Numerical source displayed by one exported series."""

    RAW = "raw"
    FILTERED = "filtered"


class ExportArtifactKind(StrEnum):
    """Files that form one reproducible figure bundle."""

    SVG = "svg"
    PDF = "pdf"
    PNG = "png"
    SOURCE_CSV = "csv"
    MANIFEST = "manifest.json"


class ExportPreset(StrEnum):
    """Template-first layouts; arbitrary canvas editing is intentionally deferred."""

    SINGLE_COLUMN = "single_column"
    DOUBLE_COLUMN = "double_column"
    TWO_PANEL = "two_panel"
    FOUR_PANEL = "four_panel"


class AxisScale(StrEnum):
    LINEAR = "linear"
    LOG = "log"


@dataclass(frozen=True, slots=True)
class ExportSelection:
    """Explicit export scope, independent from the shared single-Sweep selection."""

    folder_key: str
    shot_ids: tuple[str, ...]
    sweep_ids: tuple[str, ...]
    methods: tuple[SummaryMethod, ...]
    variants: tuple[ExportDataVariant, ...]
    position_ids: tuple[str, ...] = ()
    include_excluded: bool = False
    current_revision_only: bool = True

    def __post_init__(self) -> None:
        if not self.folder_key.strip():
            raise ValueError("folder_key cannot be empty")
        _validate_unique_non_empty("shot_ids", self.shot_ids, required=True)
        _validate_unique_non_empty("sweep_ids", self.sweep_ids)
        _validate_unique_non_empty("position_ids", self.position_ids)
        _validate_unique("methods", self.methods)
        _validate_unique("variants", self.variants)


@dataclass(frozen=True, slots=True)
class AxisSpec:
    label: str
    unit: str
    scale: AxisScale = AxisScale.LINEAR
    minimum: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("axis label cannot be empty")
        if not self.unit.strip():
            raise ValueError("axis unit cannot be empty")
        for name, value in (("minimum", self.minimum), ("maximum", self.maximum)):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"axis {name} must be finite")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.maximum <= self.minimum
        ):
            raise ValueError("axis maximum must be greater than minimum")


@dataclass(frozen=True, slots=True)
class SeriesStyle:
    color: str
    line_style: str = "solid"
    marker: str = "none"
    line_width_pt: float = 1.0

    def __post_init__(self) -> None:
        if not self.color.strip():
            raise ValueError("series color cannot be empty")
        if not self.line_style.strip() or not self.marker.strip():
            raise ValueError("line_style and marker cannot be empty")
        if not math.isfinite(self.line_width_pt) or self.line_width_pt <= 0:
            raise ValueError("line_width_pt must be finite and positive")


@dataclass(frozen=True, slots=True)
class PanelSpec:
    panel_id: str
    figure_type: ExportFigureType
    title: str
    x_axis: AxisSpec
    y_axis: AxisSpec
    show_legend: bool = True
    show_error_bars: bool = True

    def __post_init__(self) -> None:
        if not self.panel_id.strip():
            raise ValueError("panel_id cannot be empty")


@dataclass(frozen=True, slots=True)
class FigureSpec:
    preset: ExportPreset
    width_mm: float
    height_mm: float
    dpi: int
    panels: tuple[PanelSpec, ...]

    def __post_init__(self) -> None:
        if not math.isfinite(self.width_mm) or self.width_mm <= 0:
            raise ValueError("width_mm must be finite and positive")
        if not math.isfinite(self.height_mm) or self.height_mm <= 0:
            raise ValueError("height_mm must be finite and positive")
        if self.dpi < 72:
            raise ValueError("dpi must be at least 72")
        if not self.panels:
            raise ValueError("at least one panel is required")
        panel_ids = tuple(panel.panel_id for panel in self.panels)
        _validate_unique_non_empty("panel IDs", panel_ids, required=True)


@dataclass(frozen=True, slots=True)
class ExportProvenance:
    """Inputs needed to audit and regenerate one selected result."""

    input_identity: str
    revision_key: str
    analysis_settings: tuple[tuple[str, str], ...]
    algorithm_version: str
    analysis_schema_version: int
    code_version: str
    used_point_ids: tuple[str, ...] = ()
    exclusion_reason: str = ""

    def __post_init__(self) -> None:
        for name, value in (
            ("input_identity", self.input_identity),
            ("revision_key", self.revision_key),
            ("algorithm_version", self.algorithm_version),
            ("code_version", self.code_version),
        ):
            if not value.strip():
                raise ValueError(f"{name} cannot be empty")
        if self.analysis_schema_version < 1:
            raise ValueError("analysis_schema_version must be at least 1")
        setting_names = tuple(name for name, _ in self.analysis_settings)
        _validate_unique_non_empty("analysis setting names", setting_names)
        if tuple(sorted(self.analysis_settings)) != self.analysis_settings:
            raise ValueError("analysis_settings must be sorted by name")
        _validate_unique_non_empty("used_point_ids", self.used_point_ids)


@dataclass(frozen=True, slots=True)
class ExportManifest:
    """Deterministic recipe for one figure and its companion artifacts."""

    selection: ExportSelection
    figure: FigureSpec
    styles: tuple[tuple[str, SeriesStyle], ...]
    provenance: tuple[ExportProvenance, ...]
    artifacts: tuple[ExportArtifactKind, ...]
    filename_stem: str
    renderer_version: str = "paper-renderer-v1"
    manifest_schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.filename_stem.strip():
            raise ValueError("filename_stem cannot be empty")
        if "/" in self.filename_stem or "\\" in self.filename_stem:
            raise ValueError("filename_stem cannot contain path separators")
        if not self.renderer_version.strip():
            raise ValueError("renderer_version cannot be empty")
        if self.manifest_schema_version < 1:
            raise ValueError("manifest_schema_version must be at least 1")
        style_ids = tuple(series_id for series_id, _ in self.styles)
        _validate_unique_non_empty("style IDs", style_ids)
        _validate_unique("artifacts", self.artifacts)
        if ExportArtifactKind.MANIFEST not in self.artifacts:
            raise ValueError("a reproducible bundle must include its manifest")
        provenance_ids = tuple(item.input_identity for item in self.provenance)
        _validate_unique_non_empty("provenance input identities", provenance_ids)

    @property
    def canonical_json(self) -> str:
        return json.dumps(
            asdict(self),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @property
    def manifest_id(self) -> str:
        return hashlib.sha256(self.canonical_json.encode()).hexdigest()

    @property
    def artifact_filenames(self) -> tuple[str, ...]:
        return tuple(
            f"{self.filename_stem}.{artifact.value}" for artifact in self.artifacts
        )


@dataclass(frozen=True, slots=True)
class ExportCandidate:
    """One visible result row and its safe default-selection decision."""

    number: int
    sweep_id: str
    shot_id: str
    status: AnalysisStatus
    current_revision: bool
    available_methods: tuple[SummaryMethod, ...]
    selected_by_default: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ExportCandidateSnapshot:
    """Read-only candidate projection; it never starts analysis or export."""

    folder_key: str
    shot_ids: tuple[str, ...]
    candidates: tuple[ExportCandidate, ...]

    @property
    def default_candidate_count(self) -> int:
        return sum(candidate.selected_by_default for candidate in self.candidates)

    @property
    def warning_count(self) -> int:
        return len(self.candidates) - self.default_candidate_count

    @property
    def default_selection(self) -> ExportSelection:
        selected = tuple(
            candidate.sweep_id
            for candidate in self.candidates
            if candidate.selected_by_default
        )
        available_methods = {
            method
            for candidate in self.candidates
            if candidate.selected_by_default
            for method in candidate.available_methods
        }
        methods = tuple(
            method for method in SummaryMethod if method in available_methods
        )
        return ExportSelection(
            folder_key=self.folder_key,
            shot_ids=self.shot_ids,
            sweep_ids=selected,
            methods=methods,
            variants=(ExportDataVariant.RAW, ExportDataVariant.FILTERED),
        )


def _validate_unique(
    name: str,
    values: tuple[object, ...],
) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must be unique")


def _validate_unique_non_empty(
    name: str,
    values: tuple[str, ...],
    *,
    required: bool = False,
) -> None:
    if required and not values:
        raise ValueError(f"{name} requires at least one value")
    if any(not value.strip() for value in values):
        raise ValueError(f"{name} cannot contain an empty value")
    _validate_unique(name, values)
