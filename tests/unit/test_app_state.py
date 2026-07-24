from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from probe_app.application.state import AppState, LoadStatus, SweepRunStatus
from probe_app.domain.models import (
    AssignedSeries,
    FolderCatalog,
    SeriesRole,
    SeriesRoleAssignments,
    Sweep,
    SweepDirection,
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


def test_folder_shot_series_and_sweep_selection_have_one_reset_chain(
    tmp_path: Path,
) -> None:
    for shot_id in ("shot-a", "shot-b"):
        write_panta_series(tmp_path / shot_id, "current")
        write_panta_series(tmp_path / shot_id, "voltage")
    catalog = FolderScanner().scan(tmp_path)
    state = AppState().apply_catalog(catalog)
    shot_a_assignments = SeriesRoleAssignments(
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
    state = state.set_role_assignments("shot-a", shot_a_assignments)
    first = _sweep("first", 0)
    second = _sweep("second", 4)
    state = state.start_sweep_split().apply_sweep_result(
        (first, second),
        interpolated_current=False,
    )

    assert state.selected_sweep_id == first.sweep_id
    assert state.selected_sweep == first
    state = state.select_sweep(second.sweep_id)
    assert state.selected_sweep == second
    with pytest.raises(ValueError, match="unknown sweep_id"):
        state.select_sweep("missing")

    series_changed = state.select_series("shot-a/voltage")
    assert series_changed.selected_series_id == "shot-a/voltage"
    assert series_changed.selected_sweep_id is None
    assert series_changed.sweeps == ()

    shot_b_assignments = SeriesRoleAssignments(
        (
            AssignedSeries(
                role=SeriesRole.CURRENT,
                series_id="shot-b/current",
                transform=legacy_current_transform(sign=-1.0),
            ),
            AssignedSeries(
                role=SeriesRole.SWEEP_VOLTAGE,
                series_id="shot-b/voltage",
                transform=legacy_sweep_voltage_transform(),
            ),
        )
    )
    shot_changed = state.set_role_assignments("shot-b", shot_b_assignments)
    assert shot_changed.role_assignment_shot_id == "shot-b"
    assert shot_changed.selected_sweep_id is None
    assert shot_changed.sweeps == ()

    folder_changed = state.start_loading(tmp_path / "other-folder")
    assert folder_changed.folder == tmp_path / "other-folder"
    assert folder_changed.selected_series_id is None
    assert folder_changed.role_assignment_shot_id is None
    assert folder_changed.selected_sweep_id is None
    assert folder_changed.sweeps == ()


def _sweep(sweep_id: str, start: int) -> Sweep:
    return Sweep(
        sweep_id=sweep_id,
        current_series_id="shot-a/current",
        voltage_series_id="shot-a/voltage",
        source_start_index=start,
        source_stop_index=start + 4,
        direction=SweepDirection.UP,
        time_s=np.arange(start, start + 4, dtype=np.float64) * 0.01,
        voltage_v=np.arange(4, dtype=np.float64),
        current_a=np.arange(4, dtype=np.float64),
    )
