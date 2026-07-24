from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from probe_app.domain.errors import RoleAssignmentStoreError
from probe_app.domain.models.series_role import (
    AssignedSeries,
    SeriesRole,
    SeriesRoleAssignments,
    legacy_current_transform,
    legacy_sweep_voltage_transform,
)
from probe_app.infrastructure.persistence import QSettingsRoleAssignmentStore


def _settings(path: Path) -> QSettings:
    return QSettings(str(path), QSettings.Format.IniFormat)


def test_round_trips_assignments_outside_measurement_folder(tmp_path: Path) -> None:
    measurement_folder = tmp_path / "measurements"
    measurement_folder.mkdir()
    settings_path = tmp_path / "app-preferences.ini"
    store = QSettingsRoleAssignmentStore(_settings(settings_path))
    assignments = SeriesRoleAssignments(
        (
            AssignedSeries(
                SeriesRole.CURRENT,
                "shot-a/channel-i",
                legacy_current_transform(sign=-1.0),
            ),
            AssignedSeries(
                SeriesRole.SWEEP_VOLTAGE,
                "shot-a/channel-v",
                legacy_sweep_voltage_transform(),
            ),
        )
    )

    store.save(measurement_folder, "shot-a", assignments)
    restored = QSettingsRoleAssignmentStore(_settings(settings_path)).load(
        measurement_folder,
        "shot-a",
    )

    assert restored == assignments
    assert list(measurement_folder.iterdir()) == []


def test_folder_and_shot_form_separate_namespaces(tmp_path: Path) -> None:
    store = QSettingsRoleAssignmentStore(_settings(tmp_path / "settings.ini"))
    assignment = SeriesRoleAssignments(
        (
            AssignedSeries(
                SeriesRole.CURRENT,
                "shot-a/channel-i",
                legacy_current_transform(sign=1.0),
            ),
        )
    )

    store.save(tmp_path / "folder-a", "shot-a", assignment)

    assert store.load(tmp_path / "folder-a", "shot-a") == assignment
    assert store.load(tmp_path / "folder-a", "shot-b") == SeriesRoleAssignments()
    assert store.load(tmp_path / "folder-b", "shot-a") == SeriesRoleAssignments()


@pytest.mark.parametrize("shot_id", ["shot-a", "nested/shot-a"])
def test_empty_assignment_is_a_valid_saved_state(tmp_path: Path, shot_id: str) -> None:
    store = QSettingsRoleAssignmentStore(_settings(tmp_path / "settings.ini"))

    store.save(tmp_path / "folder", shot_id, SeriesRoleAssignments())

    assert store.load(tmp_path / "folder", shot_id) == SeriesRoleAssignments()


def test_corrupt_saved_transform_reports_a_store_error(tmp_path: Path) -> None:
    settings = _settings(tmp_path / "settings.ini")
    store = QSettingsRoleAssignmentStore(settings)
    folder = tmp_path / "folder"
    assignment = SeriesRoleAssignments(
        (
            AssignedSeries(
                SeriesRole.CURRENT,
                "shot-a/channel-i",
                legacy_current_transform(sign=-1.0),
            ),
        )
    )
    store.save(folder, "shot-a", assignment)
    group = store._group_key(folder, "shot-a")  # noqa: SLF001
    settings.setValue(f"{group}/current/scale", "not-a-number")

    with pytest.raises(RoleAssignmentStoreError, match="読み込めません"):
        store.load(folder, "shot-a")
