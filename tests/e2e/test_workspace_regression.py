from __future__ import annotations

import gc
import os
import time
import tracemalloc
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

import probe_app.ui.main_window as main_window_module
from probe_app.application.queries import build_export_candidates
from probe_app.application.state import AppState, LoadStatus, SweepRunStatus
from probe_app.domain.models import (
    AnalysisStatus,
    AssignedSeries,
    ExportCandidateSnapshot,
    FolderCatalog,
    RawSeries,
    RawSeriesDescriptor,
    SeriesRole,
    SeriesRoleAssignments,
    SummaryRow,
    SummaryScope,
    SummaryScopeKind,
    SummarySnapshot,
    Sweep,
    SweepDirection,
    legacy_current_transform,
    legacy_sweep_voltage_transform,
)
from probe_app.ui.main_window import MainWindow
from probe_app.ui.widgets import ExportWorkspace, SummaryWorkspace


class _CountingThreadPool:
    def __init__(self) -> None:
        self.start_count = 0

    def start(self, task: object) -> None:
        self.start_count += 1


def test_one_hundred_workspace_switches_start_no_work_and_do_not_grow_memory(
    qtbot: object,
    monkeypatch: object,
) -> None:
    preprocessing_calls = 0

    def count_preprocessing(*args: object, **kwargs: object) -> None:
        nonlocal preprocessing_calls
        preprocessing_calls += 1

    monkeypatch.setattr(  # type: ignore[attr-defined]
        main_window_module,
        "preprocess_sweep",
        count_preprocessing,
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    pool = _CountingThreadPool()
    window._thread_pool = pool  # type: ignore[assignment]  # noqa: SLF001
    window.show()
    qtbot.wait(10)  # type: ignore[attr-defined]

    for index in range(window._workspace_tabs.count()):  # noqa: SLF001
        window._workspace_tabs.setCurrentIndex(index)  # noqa: SLF001
    window._workspace_tabs.setCurrentIndex(0)  # noqa: SLF001
    qtbot.wait(1)  # type: ignore[attr-defined]

    state_before = window._state  # noqa: SLF001
    generations_before = (
        window._scan_generation,  # noqa: SLF001
        window._load_generation,  # noqa: SLF001
        window._sweep_generation,  # noqa: SLF001
    )
    gc.collect()
    tracemalloc.start()
    memory_before = tracemalloc.take_snapshot()
    started = time.perf_counter()

    for switch_number in range(100):
        index = switch_number % window._workspace_tabs.count()  # noqa: SLF001
        window._workspace_tabs.setCurrentIndex(index)  # noqa: SLF001
    qtbot.wait(1)  # type: ignore[attr-defined]

    elapsed_s = time.perf_counter() - started
    gc.collect()
    memory_after = tracemalloc.take_snapshot()
    tracemalloc.stop()
    positive_growth = sum(
        max(stat.size_diff, 0)
        for stat in memory_after.compare_to(memory_before, "lineno")
    )

    assert pool.start_count == 0
    assert preprocessing_calls == 0
    assert window._state is state_before  # noqa: SLF001
    assert generations_before == (
        window._scan_generation,  # noqa: SLF001
        window._load_generation,  # noqa: SLF001
        window._sweep_generation,  # noqa: SLF001
    )
    assert window._scan_task is None  # noqa: SLF001
    assert window._load_task is None  # noqa: SLF001
    assert window._sweep_task is None  # noqa: SLF001
    assert elapsed_s < 1.0
    assert positive_growth < 2 * 1024 * 1024
    assert window._analysis_sweep_iv_plot.selected_sweep is None  # noqa: SLF001
    assert window._analysis_sweep_iv_plot.preprocessed is None  # noqa: SLF001
    assert not window._export_workspace.renderer_constructed  # noqa: SLF001


def test_shared_sweep_selection_is_consistent_in_all_workspaces(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    pool = _CountingThreadPool()
    window._thread_pool = pool  # type: ignore[assignment]  # noqa: SLF001
    first = _sweep(1)
    second = _sweep(2)
    window._state = AppState(  # noqa: SLF001
        status=LoadStatus.READY,
        folder=Path("/measurements"),
        role_assignment_shot_id="shot-001",
        role_assignments=_assignments(),
        sweep_status=SweepRunStatus.SUCCEEDED,
        sweeps=(first, second),
        selected_sweep_id=first.sweep_id,
        sweep_message="2 Sweepへ分割しました",
        message="ready",
    )

    window._render_sweep_panel()  # noqa: SLF001
    assert window._sweep_browser.select_sweep(second.sweep_id)  # noqa: SLF001

    assert window._state.selected_sweep_id == second.sweep_id  # noqa: SLF001
    assert window._sweep_iv_plot.selected_sweep == second  # noqa: SLF001
    assert window._analysis_sweep_iv_plot.selected_sweep == second  # noqa: SLF001
    assert window._summary_workspace.selected_sweep_id == second.sweep_id  # noqa: SLF001
    assert window._export_workspace.candidate_count == 2  # noqa: SLF001
    assert window._export_workspace.checked_candidate_count == 0  # noqa: SLF001

    for index in range(window._workspace_tabs.count()):  # noqa: SLF001
        window._workspace_tabs.setCurrentIndex(index)  # noqa: SLF001
        assert window._state.selected_sweep_id == second.sweep_id  # noqa: SLF001
    assert pool.start_count == 0


def test_large_summary_and_export_projection_remain_responsive(
    qtbot: object,
) -> None:
    rows = tuple(_summary_row(number) for number in range(1, 1_001))
    summary = SummarySnapshot(
        scope=SummaryScope(
            kind=SummaryScopeKind.CURRENT_SHOT,
            folder_key="/measurements",
            shot_ids=("shot-001",),
        ),
        rows=rows,
    )
    summary_workspace = SummaryWorkspace()
    export_workspace = ExportWorkspace()
    qtbot.addWidget(summary_workspace)  # type: ignore[attr-defined]
    qtbot.addWidget(export_workspace)  # type: ignore[attr-defined]

    started = time.perf_counter()
    summary_workspace.render_snapshot(summary)
    candidates: ExportCandidateSnapshot = build_export_candidates(summary)
    export_workspace.render_candidates(candidates)
    elapsed_s = time.perf_counter() - started

    assert summary_workspace.row_count == 1_000
    assert export_workspace.candidate_count == 1_000
    assert export_workspace.checked_candidate_count == 500
    assert elapsed_s < 2.5
    assert not export_workspace.renderer_constructed


def test_old_scan_and_series_load_generations_are_discarded(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    descriptor = RawSeriesDescriptor(
        series_id="shot-001/current",
        shot_id="shot-001",
        channel_id="current",
        header_path=tmp_path / "current.hdr",
        data_path=tmp_path / "current.dat",
        sample_count=3,
        value_unit="V",
        time_unit="s",
    )
    catalog = FolderCatalog(root=tmp_path, series=(descriptor,))
    series = RawSeries(
        descriptor=descriptor,
        time_s=np.asarray([0.0, 1e-6, 2e-6], dtype=np.float64),
        values=np.asarray([1.0, 2.0, 3.0], dtype=np.float64),
    )
    state_before = window._state  # noqa: SLF001
    window._scan_generation = 4  # noqa: SLF001
    window._load_generation = 7  # noqa: SLF001

    window._folder_loaded(3, catalog)  # noqa: SLF001
    window._series_loaded(6, series)  # noqa: SLF001

    assert window._state is state_before  # noqa: SLF001
    assert window._state.catalog is None  # noqa: SLF001
    assert window._raw_plot.displayed_series_id is None  # noqa: SLF001


def _assignments() -> SeriesRoleAssignments:
    return SeriesRoleAssignments(
        (
            AssignedSeries(
                role=SeriesRole.CURRENT,
                series_id="shot-001/current",
                transform=legacy_current_transform(sign=-1.0),
            ),
            AssignedSeries(
                role=SeriesRole.SWEEP_VOLTAGE,
                series_id="shot-001/voltage",
                transform=legacy_sweep_voltage_transform(),
            ),
        )
    )


def _sweep(number: int) -> Sweep:
    start = 200_000 + (number - 1) * 10
    stop = start + 10
    voltage = np.linspace(-50.0, 50.0, 10, dtype=np.float64)
    return Sweep(
        sweep_id=f"shot-001/voltage:{start}:{stop}",
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        source_start_index=start,
        source_stop_index=stop,
        direction=SweepDirection.UP if number % 2 else SweepDirection.DOWN,
        time_s=np.linspace(start * 1e-6, (stop - 1) * 1e-6, 10),
        voltage_v=voltage,
        current_a=voltage * 1e-6,
    )


def _summary_row(number: int) -> SummaryRow:
    usable = number % 2 == 1
    status = AnalysisStatus.VALID if usable else AnalysisStatus.STALE
    return SummaryRow(
        number=number,
        sweep_id=f"shot-001/voltage:{number}:{number + 1}",
        shot_id="shot-001",
        direction=SweepDirection.UP if usable else SweepDirection.DOWN,
        start_ms=float(number),
        stop_ms=float(number + 1),
        point_count=10_000,
        status=status,
        current_revision=usable,
        revision_key=str(number),
        message="" if usable else "解析設定が変更されました",
    )
