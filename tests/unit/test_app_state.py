from __future__ import annotations

from pathlib import Path

import pytest

from probe_app.application.state import AppState, LoadStatus, SweepRunStatus
from probe_app.domain.models import (
    AssignedSeries,
    FolderCatalog,
    SeriesRole,
    SeriesRoleAssignments,
    legacy_current_transform,
    legacy_sweep_voltage_transform,
)
from probe_app.infrastructure.readers.folder_scanner import FolderScanner
from tests.conftest import write_panta_series


def test_loading_empty_and_ready_transitions(tmp_path: Path) -> None:
    state = AppState().start_loading(tmp_path)
    assert state.status is LoadStatus.LOADING

    empty = state.apply_catalog(FolderCatalog(root=tmp_path, series=()))
    assert empty.status is LoadStatus.EMPTY

    write_panta_series(tmp_path, "3_3_01")
    catalog = FolderScanner().scan(tmp_path)
    ready = state.apply_catalog(catalog)
    assert ready.status is LoadStatus.READY
    assert ready.selected_series_id == catalog.series[0].series_id


def test_selection_rejects_unknown_series(tmp_path: Path) -> None:
    state = AppState().apply_catalog(FolderCatalog(root=tmp_path, series=()))

    with pytest.raises(ValueError, match="unknown series_id"):
        state.select_series("missing")


def test_role_assignments_are_limited_to_one_shot(tmp_path: Path) -> None:
    write_panta_series(tmp_path / "shot-a", "current")
    write_panta_series(tmp_path / "shot-a", "voltage")
    write_panta_series(tmp_path / "shot-b", "current")
    state = AppState().apply_catalog(FolderScanner().scan(tmp_path))
    assignment = AssignedSeries(
        role=SeriesRole.CURRENT,
        series_id="shot-a/current",
        transform=legacy_current_transform(sign=-1.0),
    )

    updated = state.set_role_assignments(
        "shot-a",
        SeriesRoleAssignments((assignment,)),
    )

    assert updated.role_assignment_shot_id == "shot-a"
    assert updated.role_assignments.for_role(SeriesRole.CURRENT) == assignment

    wrong_shot = AssignedSeries(
        role=SeriesRole.CURRENT,
        series_id="shot-b/current",
        transform=legacy_current_transform(sign=-1.0),
    )
    with pytest.raises(ValueError, match="outside shot"):
        state.set_role_assignments(
            "shot-a",
            SeriesRoleAssignments((wrong_shot,)),
        )


def test_sweep_run_state_is_invalidated_when_series_changes(tmp_path: Path) -> None:
    write_panta_series(tmp_path / "shot-a", "current")
    write_panta_series(tmp_path / "shot-a", "voltage")
    state = AppState().apply_catalog(FolderScanner().scan(tmp_path))
    assignments = SeriesRoleAssignments(
        (
            AssignedSeries(
                role=SeriesRole.CURRENT,
                series_id="shot-a/current",
                transform=legacy_current_transform(sign=-1.0),
            ),
            AssignedSeries(
                role=SeriesRole.SWEEP_VOLTAGE,
                series_id="shot-a/voltage",
                transform=legacy_sweep_voltage_transform(),
            ),
        )
    )
    state = state.set_role_assignments("shot-a", assignments)
    assert state.sweep_status is SweepRunStatus.READY

    running = state.start_sweep_split()
    cancelled = running.cancel_sweep_split()
    assert cancelled.sweep_status is SweepRunStatus.CANCELLED
    assert cancelled.role_assignments == assignments

    complete = running.apply_sweep_result((), interpolated_current=False)
    assert complete.sweep_status is SweepRunStatus.SUCCEEDED

    changed = complete.select_series("shot-a/voltage")
    assert changed.sweep_status is SweepRunStatus.READY
    assert changed.sweeps == ()
