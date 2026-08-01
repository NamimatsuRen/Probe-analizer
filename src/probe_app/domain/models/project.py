from __future__ import annotations

from dataclasses import dataclass, replace

from probe_app.domain.models.analysis_catalog import (
    AnalysisCatalog,
    ShotAnalysisSnapshot,
)
from probe_app.domain.models.analysis_result import (
    SweepAnalysisRecord,
    SweepSplitRevision,
)
from probe_app.domain.models.audit import AuditTrail
from probe_app.domain.models.series_role import SeriesRoleAssignments
from probe_app.domain.models.shot_metadata import ShotMetadata

PROJECT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ProjectShotSettings:
    shot_id: str
    assignments: SeriesRoleAssignments
    split: SweepSplitRevision | None = None

    def __post_init__(self) -> None:
        if not self.shot_id.strip():
            raise ValueError("project shot_id cannot be empty")


@dataclass(frozen=True, slots=True)
class ProjectDocument:
    code_version: str
    saved_at_utc: str
    folder_key: str
    shot_settings: tuple[ProjectShotSettings, ...]
    shot_metadata: tuple[ShotMetadata, ...]
    analysis_catalog: AnalysisCatalog
    analysis_records: tuple[SweepAnalysisRecord, ...]
    audit_trail: AuditTrail
    selected_series_id: str | None = None
    selected_shot_id: str | None = None
    selected_sweep_id: str | None = None
    schema_version: int = PROJECT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PROJECT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported project schema version: {self.schema_version}"
            )
        if not self.code_version.strip() or not self.folder_key.strip():
            raise ValueError("project code_version and folder_key cannot be empty")
        shot_ids = tuple(item.shot_id for item in self.shot_settings)
        if len(shot_ids) != len(set(shot_ids)):
            raise ValueError("project shot settings must be unique")
        metadata_ids = tuple(item.shot_id for item in self.shot_metadata)
        if len(metadata_ids) != len(set(metadata_ids)):
            raise ValueError("project shot metadata must be unique")


def relink_project(document: ProjectDocument, folder_key: str) -> ProjectDocument:
    """Relink portable metadata while leaving raw samples outside the project."""

    if not folder_key.strip():
        raise ValueError("relinked folder cannot be empty")
    metadata = tuple(replace(item, folder_key=folder_key) for item in document.shot_metadata)
    catalog = AnalysisCatalog(
        tuple(
            ShotAnalysisSnapshot(
                folder_key=folder_key,
                shot_id=item.shot_id,
                rows=item.rows,
                metadata=replace(item.metadata, folder_key=folder_key),
            )
            for item in document.analysis_catalog.shots
        )
    )
    records = tuple(
        replace(
            record,
            revision=replace(record.revision, folder_key=folder_key),
        )
        for record in document.analysis_records
    )
    return replace(
        document,
        folder_key=folder_key,
        shot_metadata=metadata,
        analysis_catalog=catalog,
        analysis_records=records,
    )
