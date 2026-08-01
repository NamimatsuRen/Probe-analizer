from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from probe_app.application.queries import build_catalog_summary_snapshot
from probe_app.domain.models import (
    AnalysisCatalog,
    AnalysisStatus,
    ProbePosition,
    ProbePositionUnit,
    ShotAnalysisSnapshot,
    ShotMetadata,
    SummaryMethod,
    SummaryMethodValue,
    SummaryMetric,
    SummaryRow,
    SummaryScopeKind,
    SweepDirection,
)
from probe_app.infrastructure.persistence import QSettingsShotMetadataStore


def test_shot_metadata_store_round_trips_explicit_position(tmp_path: Path) -> None:
    folder = tmp_path / "measurements"
    folder.mkdir()
    settings_path = tmp_path / "settings.ini"
    settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
    store = QSettingsShotMetadataStore(settings)
    metadata = ShotMetadata(
        folder_key=str(folder.resolve()),
        shot_id="shot-002",
        position=ProbePosition(
            value=3.5,
            unit=ProbePositionUnit.CENTIMETER,
            label="edge",
        ),
        note="entered by operator",
    )

    store.save(folder, metadata)
    restored = QSettingsShotMetadataStore(
        QSettings(str(settings_path), QSettings.Format.IniFormat)
    ).load(folder, "shot-002")

    assert restored == metadata
    assert restored.position is not None
    assert restored.position.millimeters == 35.0


def test_missing_metadata_is_unset_and_never_inferred_from_shot_name(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "position_42mm"
    folder.mkdir()
    store = QSettingsShotMetadataStore(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )

    restored = store.load(folder, "shot-r-12.5mm")

    assert restored.position is None


def test_catalog_keeps_only_scalar_rows_and_aggregates_equal_weight_shots() -> None:
    folder_key = "/measurements"
    metadata_a = _metadata(folder_key, "shot-a", 10.0)
    metadata_b = _metadata(folder_key, "shot-b", 1.0, ProbePositionUnit.CENTIMETER)
    catalog = AnalysisCatalog(
        (
            ShotAnalysisSnapshot(
                folder_key,
                "shot-a",
                (_row("shot-a", 1, 1.0), _row("shot-a", 2, 3.0)),
                metadata_a,
            ),
                ShotAnalysisSnapshot(
                    folder_key,
                    "shot-b",
                    (_row("shot-b", 1, 4.0),),
                metadata_b,
            ),
        )
    )

    loaded = build_catalog_summary_snapshot(
        folder_key,
        catalog,
        SummaryScopeKind.LOADED_SHOTS,
    )
    position = build_catalog_summary_snapshot(
        folder_key,
        catalog,
        SummaryScopeKind.POSITION,
    )

    loaded_points = loaded.points_for(
        SummaryMetric.TI,
        SummaryMethod.FILTERED_LOG,
    )
    position_points = position.points_for(
        SummaryMetric.TI,
        SummaryMethod.FILTERED_LOG,
    )
    assert [point.mean for point in loaded_points] == [2.0, 4.0]
    assert len(position_points) == 1
    assert position_points[0].x_value == 10.0
    assert position_points[0].mean == 3.0
    assert position_points[0].count == 2
    assert position_points[0].sample_std == 2**0.5
    assert all(not hasattr(snapshot, "voltage_v") for snapshot in catalog.shots)
    assert all(not hasattr(snapshot, "current_a") for snapshot in catalog.shots)


def _metadata(
    folder_key: str,
    shot_id: str,
    value: float,
    unit: ProbePositionUnit = ProbePositionUnit.MILLIMETER,
) -> ShotMetadata:
    return ShotMetadata(
        folder_key=folder_key,
        shot_id=shot_id,
        position=ProbePosition(value=value, unit=unit),
    )


def _row(shot_id: str, number: int, ti_ev: float) -> SummaryRow:
    return SummaryRow(
        number=number,
        sweep_id=f"{shot_id}/sweep-{number}",
        shot_id=shot_id,
        direction=SweepDirection.UP,
        start_ms=float(number),
        stop_ms=float(number + 1),
        point_count=10,
        status=AnalysisStatus.VALID,
        current_revision=True,
        revision_key=f"revision-{number}",
        methods=(
            SummaryMethodValue(
                method=SummaryMethod.FILTERED_LOG,
                status=AnalysisStatus.VALID,
                ti_ev=ti_ev,
                phi_v=14.0 + number,
            ),
        ),
    )
