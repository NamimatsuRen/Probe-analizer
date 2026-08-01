from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest

from probe_app.domain.models import (
    AnalysisCatalog,
    AnalysisInputRevision,
    AnalysisStatus,
    AssignedSeries,
    AuditAction,
    AuditEvent,
    AuditTrail,
    PreprocessingRevision,
    ProbePosition,
    ProbePositionUnit,
    ProjectDocument,
    ProjectShotSettings,
    SeriesRole,
    SeriesRoleAssignments,
    ShotAnalysisSnapshot,
    ShotMetadata,
    SignalAssignmentRevision,
    SignalTransform,
    SummaryMethod,
    SummaryMethodValue,
    SummaryRow,
    SweepAnalysisRecord,
    SweepDirection,
    SweepSplitRevision,
    relink_project,
)
from probe_app.infrastructure.persistence import ProjectFileError, ProjectFileStore


def test_project_file_round_trip_preserves_results_metadata_and_audit(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path / "measurement")
    target = tmp_path / "analysis.probe-project.json"

    ProjectFileStore().save(target, document)
    restored = ProjectFileStore().load(target)

    assert restored == document
    assert target.read_text(encoding="utf-8").endswith("\n")
    assert "voltage_v" not in target.read_text(encoding="utf-8")
    assert "current_a" not in target.read_text(encoding="utf-8")


def test_atomic_save_keeps_previous_project_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "analysis.probe-project.json"
    target.write_text("previous", encoding="utf-8")

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("simulated disk failure")

    monkeypatch.setattr(
        "probe_app.infrastructure.persistence.project_file.os.replace",
        fail_replace,
    )

    with pytest.raises(ProjectFileError, match="simulated disk failure"):
        ProjectFileStore().save(target, _document(tmp_path / "measurement"))

    assert target.read_text(encoding="utf-8") == "previous"
    assert not tuple(tmp_path.glob(".*.tmp"))


def test_project_loader_rejects_future_schema(tmp_path: Path) -> None:
    target = tmp_path / "future.probe-project.json"
    payload = json.loads(json.dumps({"schema_version": 999}))
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectFileError, match="未対応"):
        ProjectFileStore().load(target)


def test_project_loader_migrates_schema_zero(tmp_path: Path) -> None:
    target = tmp_path / "legacy.probe-project.json"
    payload = asdict(_document(tmp_path / "measurement"))
    payload["schema_version"] = 0
    payload.pop("shot_metadata")
    payload.pop("audit_trail")
    target.write_text(json.dumps(payload), encoding="utf-8")

    restored = ProjectFileStore().load(target)

    assert restored.schema_version == 1
    assert restored.shot_metadata == ()
    assert restored.audit_trail.events == ()
    assert restored.analysis_records


def test_relink_updates_all_folder_bound_identities(tmp_path: Path) -> None:
    document = _document(tmp_path / "old")
    relinked = relink_project(document, str((tmp_path / "new").resolve()))

    assert relinked.folder_key.endswith("/new")
    assert all(
        item.folder_key == relinked.folder_key
        for item in relinked.analysis_catalog.shots
    )
    assert all(
        record.revision.folder_key == relinked.folder_key
        for record in relinked.analysis_records
    )


def _document(folder: Path) -> ProjectDocument:
    folder_key = str(folder.resolve())
    split = SweepSplitRevision(
        points_per_cycle=20_000,
        sample_start=200_000,
        sample_stop=500_000,
        current_time_offset_s=0.00025,
    )
    assignments = SeriesRoleAssignments(
        (
            AssignedSeries(
                SeriesRole.CURRENT,
                "shot-001/current",
                SignalTransform(0.05, -1.0, "A"),
            ),
            AssignedSeries(
                SeriesRole.SWEEP_VOLTAGE,
                "shot-001/voltage",
                SignalTransform(100.0, 1.0, "V"),
            ),
        )
    )
    metadata = ShotMetadata(
        folder_key=folder_key,
        shot_id="shot-001",
        position=ProbePosition(12.5, ProbePositionUnit.MILLIMETER, "edge"),
    )
    row = SummaryRow(
        number=1,
        sweep_id="shot-001/voltage:200000:210000",
        shot_id="shot-001",
        direction=SweepDirection.UP,
        start_ms=200.0,
        stop_ms=210.0,
        point_count=10_000,
        status=AnalysisStatus.VALID,
        current_revision=True,
        revision_key="revision",
        methods=(
            SummaryMethodValue(
                SummaryMethod.FILTERED_LOG,
                AnalysisStatus.VALID,
                phi_v=14.5,
                ti_ev=1.8,
            ),
        ),
    )
    revision = AnalysisInputRevision(
        folder_key=folder_key,
        shot_id="shot-001",
        sweep_id=row.sweep_id,
        current=SignalAssignmentRevision("shot-001/current", 0.05, -1.0, "A"),
        sweep_voltage=SignalAssignmentRevision(
            "shot-001/voltage", 100.0, 1.0, "V"
        ),
        split=split,
        preprocessing=PreprocessingRevision(501, 3),
    )
    event = AuditEvent.create(
        AuditAction.EXCLUDE,
        row.sweep_id,
        details=(("reason", "noise"),),
        timestamp=datetime(2026, 8, 2, tzinfo=UTC),
    )
    return ProjectDocument(
        code_version="0.8.0",
        saved_at_utc="2026-08-02T00:00:00Z",
        folder_key=folder_key,
        shot_settings=(ProjectShotSettings("shot-001", assignments, split),),
        shot_metadata=(metadata,),
        analysis_catalog=AnalysisCatalog(
            (ShotAnalysisSnapshot(folder_key, "shot-001", (row,), metadata),)
        ),
        analysis_records=(
            SweepAnalysisRecord(revision=revision, status=AnalysisStatus.VALID),
        ),
        audit_trail=AuditTrail((event,)),
        selected_series_id="shot-001/current",
        selected_shot_id="shot-001",
        selected_sweep_id=row.sweep_id,
    )
