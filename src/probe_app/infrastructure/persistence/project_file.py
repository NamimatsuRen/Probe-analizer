from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from probe_app.domain.models.analysis_catalog import (
    AnalysisCatalog,
    ShotAnalysisSnapshot,
)
from probe_app.domain.models.analysis_result import (
    AnalysisInputRevision,
    AnalysisStage,
    AnalysisStatus,
    MethodOutcome,
    PreprocessingRevision,
    SignalAssignmentRevision,
    StageResult,
    SweepAnalysisRecord,
    SweepSplitRevision,
)
from probe_app.domain.models.audit import (
    AuditAction,
    AuditEvent,
    AuditTrail,
)
from probe_app.domain.models.project import (
    PROJECT_SCHEMA_VERSION,
    ProjectDocument,
    ProjectShotSettings,
)
from probe_app.domain.models.series_role import (
    AssignedSeries,
    SeriesRole,
    SeriesRoleAssignments,
    SignalTransform,
)
from probe_app.domain.models.shot_metadata import (
    ProbePosition,
    ProbePositionUnit,
    ShotMetadata,
)
from probe_app.domain.models.summary import (
    SummaryMethod,
    SummaryMethodValue,
    SummaryRow,
)
from probe_app.domain.models.sweep import SweepDirection

MAX_PROJECT_BYTES = 100 * 1024 * 1024


class ProjectFileError(RuntimeError):
    pass


class ProjectFileStore:
    """Portable JSON project persistence with an atomic replace boundary."""

    def save(self, path: Path, document: ProjectDocument) -> None:
        target = path.expanduser().resolve(strict=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(
            asdict(document),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                stream.write(encoded)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, target)
        except OSError as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise ProjectFileError(f"projectを保存できません: {error}") from error

    def load(self, path: Path) -> ProjectDocument:
        source = path.expanduser().resolve(strict=True)
        try:
            if source.stat().st_size > MAX_PROJECT_BYTES:
                raise ProjectFileError("projectファイルが100 MiBを超えています")
            payload = json.loads(source.read_text(encoding="utf-8"))
            return _decode_project(_migrate_project(_mapping(payload)))
        except ProjectFileError:
            raise
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            raise ProjectFileError(f"projectを読み込めません: {error}") from error


def _migrate_project(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade known historical schemas without mutating the decoded JSON."""

    migrated = dict(data)
    schema_version = int(migrated.get("schema_version", 0))
    if schema_version > PROJECT_SCHEMA_VERSION:
        raise ProjectFileError(
            f"未対応のproject schemaです: {schema_version}"
        )
    if schema_version == 0:
        migrated.setdefault("shot_metadata", [])
        migrated.setdefault("audit_trail", {"events": []})
        migrated.setdefault("selected_series_id", None)
        migrated.setdefault("selected_shot_id", None)
        migrated.setdefault("selected_sweep_id", None)
        migrated["schema_version"] = 1
        schema_version = 1
    if schema_version != PROJECT_SCHEMA_VERSION:
        raise ProjectFileError(
            f"未対応のproject schemaです: {schema_version}"
        )
    return migrated


def _decode_project(data: dict[str, Any]) -> ProjectDocument:
    schema_version = int(data["schema_version"])
    if schema_version != PROJECT_SCHEMA_VERSION:
        raise ProjectFileError(
            f"未対応のproject schemaです: {schema_version}"
        )
    return ProjectDocument(
        schema_version=schema_version,
        code_version=str(data["code_version"]),
        saved_at_utc=str(data["saved_at_utc"]),
        folder_key=str(data["folder_key"]),
        shot_settings=tuple(
            _decode_shot_settings(_mapping(item))
            for item in _sequence(data.get("shot_settings", []))
        ),
        shot_metadata=tuple(
            _decode_metadata(_mapping(item))
            for item in _sequence(data.get("shot_metadata", []))
        ),
        analysis_catalog=_decode_catalog(_mapping(data["analysis_catalog"])),
        analysis_records=tuple(
            _decode_record(_mapping(item))
            for item in _sequence(data.get("analysis_records", []))
        ),
        audit_trail=_decode_audit(_mapping(data["audit_trail"])),
        selected_series_id=_optional_string(data.get("selected_series_id")),
        selected_shot_id=_optional_string(data.get("selected_shot_id")),
        selected_sweep_id=_optional_string(data.get("selected_sweep_id")),
    )


def _decode_shot_settings(data: dict[str, Any]) -> ProjectShotSettings:
    split_data = data.get("split")
    return ProjectShotSettings(
        shot_id=str(data["shot_id"]),
        assignments=_decode_assignments(_mapping(data["assignments"])),
        split=(
            _decode_split(_mapping(split_data))
            if split_data is not None
            else None
        ),
    )


def _decode_assignments(data: dict[str, Any]) -> SeriesRoleAssignments:
    return SeriesRoleAssignments(
        tuple(
            AssignedSeries(
                role=SeriesRole(item_data["role"]),
                series_id=str(item_data["series_id"]),
                transform=SignalTransform(
                    scale=float(transform["scale"]),
                    sign=float(transform["sign"]),
                    output_unit=str(transform["output_unit"]),
                ),
            )
            for item in _sequence(data.get("items", []))
            for item_data in (_mapping(item),)
            for transform in (_mapping(item_data["transform"]),)
        )
    )


def _decode_metadata(data: dict[str, Any]) -> ShotMetadata:
    position_data = data.get("position")
    position = None
    if position_data is not None:
        item = _mapping(position_data)
        position = ProbePosition(
            value=float(item["value"]),
            unit=ProbePositionUnit(item["unit"]),
            label=str(item.get("label", "")),
        )
    return ShotMetadata(
        folder_key=str(data["folder_key"]),
        shot_id=str(data["shot_id"]),
        position=position,
        note=str(data.get("note", "")),
    )


def _decode_catalog(data: dict[str, Any]) -> AnalysisCatalog:
    return AnalysisCatalog(
        tuple(
            ShotAnalysisSnapshot(
                folder_key=str(item_data["folder_key"]),
                shot_id=str(item_data["shot_id"]),
                rows=tuple(
                    _decode_summary_row(_mapping(row))
                    for row in _sequence(item_data.get("rows", []))
                ),
                metadata=_decode_metadata(_mapping(item_data["metadata"])),
            )
            for item in _sequence(data.get("shots", []))
            for item_data in (_mapping(item),)
        )
    )


def _decode_summary_row(data: dict[str, Any]) -> SummaryRow:
    return SummaryRow(
        number=int(data["number"]),
        sweep_id=str(data["sweep_id"]),
        shot_id=str(data["shot_id"]),
        direction=SweepDirection(data["direction"]),
        start_ms=float(data["start_ms"]),
        stop_ms=float(data["stop_ms"]),
        point_count=int(data["point_count"]),
        status=AnalysisStatus(data["status"]),
        current_revision=bool(data["current_revision"]),
        revision_key=str(data.get("revision_key", "")),
        message=str(data.get("message", "")),
        exclusion_reason=str(data.get("exclusion_reason", "")),
        methods=tuple(
            _decode_summary_method(_mapping(item))
            for item in _sequence(data.get("methods", []))
        ),
    )


def _decode_summary_method(data: dict[str, Any]) -> SummaryMethodValue:
    return SummaryMethodValue(
        method=SummaryMethod(data["method"]),
        status=AnalysisStatus(data["status"]),
        phi_status=_optional_status(data.get("phi_status")),
        ti_status=_optional_status(data.get("ti_status")),
        phi_v=_optional_float(data.get("phi_v")),
        ti_ev=_optional_float(data.get("ti_ev")),
        k_per_v=_optional_float(data.get("k_per_v")),
        k_source=str(data.get("k_source", "")),
        message=str(data.get("message", "")),
    )


def _decode_record(data: dict[str, Any]) -> SweepAnalysisRecord:
    previous = data.get("status_before_exclusion")
    return SweepAnalysisRecord(
        revision=_decode_revision(_mapping(data["revision"])),
        status=AnalysisStatus(data["status"]),
        stages=tuple(
            _decode_stage(_mapping(item))
            for item in _sequence(data.get("stages", []))
        ),
        message=str(data.get("message", "")),
        exclusion_reason=str(data.get("exclusion_reason", "")),
        status_before_exclusion=(
            AnalysisStatus(previous) if previous is not None else None
        ),
        message_before_exclusion=str(data.get("message_before_exclusion", "")),
    )


def _decode_revision(data: dict[str, Any]) -> AnalysisInputRevision:
    return AnalysisInputRevision(
        folder_key=str(data["folder_key"]),
        shot_id=str(data["shot_id"]),
        sweep_id=str(data["sweep_id"]),
        current=_decode_signal(_mapping(data["current"])),
        sweep_voltage=_decode_signal(_mapping(data["sweep_voltage"])),
        split=_decode_split(_mapping(data["split"])),
        preprocessing=PreprocessingRevision(
            window_length=int(_mapping(data["preprocessing"])["window_length"]),
            polyorder=int(_mapping(data["preprocessing"])["polyorder"]),
        ),
        fit_settings=tuple(
            (str(item[0]), str(item[1]))
            for item in _sequence(data.get("fit_settings", []))
            if isinstance(item, (list, tuple)) and len(item) == 2
        ),
        algorithm_version=str(data.get("algorithm_version", "level3-sg-v1")),
        schema_version=int(data.get("schema_version", 1)),
        generation_id=int(data.get("generation_id", 0)),
    )


def _decode_signal(data: dict[str, Any]) -> SignalAssignmentRevision:
    return SignalAssignmentRevision(
        series_id=str(data["series_id"]),
        scale=float(data["scale"]),
        sign=float(data["sign"]),
        output_unit=str(data["output_unit"]),
    )


def _decode_split(data: dict[str, Any]) -> SweepSplitRevision:
    stop = data.get("sample_stop")
    return SweepSplitRevision(
        points_per_cycle=int(data["points_per_cycle"]),
        sample_start=int(data["sample_start"]),
        sample_stop=int(stop) if stop is not None else None,
        current_time_offset_s=float(data["current_time_offset_s"]),
    )


def _decode_stage(data: dict[str, Any]) -> StageResult:
    return StageResult(
        stage=AnalysisStage(data["stage"]),
        status=AnalysisStatus(data["status"]),
        methods=tuple(
            _decode_outcome(_mapping(item))
            for item in _sequence(data.get("methods", []))
        ),
        message=str(data.get("message", "")),
    )


def _decode_outcome(data: dict[str, Any]) -> MethodOutcome:
    return MethodOutcome(
        method_id=str(data["method_id"]),
        status=AnalysisStatus(data["status"]),
        message=str(data.get("message", "")),
        selected_candidate_id=_optional_string(data.get("selected_candidate_id")),
        manual_override=bool(data.get("manual_override", False)),
        metrics=tuple(
            (str(item[0]), float(item[1]))
            for item in _sequence(data.get("metrics", []))
            if isinstance(item, (list, tuple)) and len(item) == 2
        ),
    )


def _decode_audit(data: dict[str, Any]) -> AuditTrail:
    return AuditTrail(
        tuple(
            AuditEvent(
                event_id=str(item_data["event_id"]),
                timestamp_utc=str(item_data["timestamp_utc"]),
                action=AuditAction(item_data["action"]),
                subject_id=str(item_data["subject_id"]),
                operator=str(item_data["operator"]),
                details=tuple(
                    (str(detail[0]), str(detail[1]))
                    for detail in _sequence(item_data.get("details", []))
                    if isinstance(detail, (list, tuple)) and len(detail) == 2
                ),
            )
            for item in _sequence(data.get("events", []))
            for item_data in (_mapping(item),)
        )
    )


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("expected a JSON object")
    return {str(key): item for key, item in value.items()}


def _sequence(value: object) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError("expected a JSON array")
    return value


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: object) -> float | None:
    return None if value is None else float(str(value))


def _optional_status(value: object) -> AnalysisStatus | None:
    return None if value is None else AnalysisStatus(str(value))
