from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtCore import QSettings

from probe_app.application.state import LoadStatus, SweepRunStatus
from probe_app.application.use_cases import SweepSplitResult
from probe_app.domain.errors import RoleAssignmentStoreError
from probe_app.domain.models.series_role import SeriesRole, SeriesRoleAssignments
from probe_app.domain.services.sweep_splitter import LegacySweepSplitParameters
from probe_app.ui.main_window import MainWindow
from tests.conftest import write_panta_series


def test_level1_window_starts(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.windowTitle() == "Probe Analizer — Rawデータブラウザ"
    assert window.centralWidget() is not None


def test_level1_window_loads_folder_and_first_series(qtbot: object, tmp_path: Path) -> None:
    write_panta_series(tmp_path / "shot-001", "3_3_01")
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window.open_folder(tmp_path)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._state.status is LoadStatus.READY  # noqa: SLF001
        and window._load_task is None,  # noqa: SLF001
        timeout=3_000,
    )

    assert window._state.selected_series_id == "shot-001/3_3_01"  # noqa: SLF001


def test_role_assignments_are_saved_and_restored(qtbot: object, tmp_path: Path) -> None:
    measurement_folder = tmp_path / "measurements"
    write_panta_series(measurement_folder / "shot-001", "channel-i")
    write_panta_series(measurement_folder / "shot-001", "channel-v")
    settings_path = tmp_path / "settings.ini"

    first = MainWindow(
        settings=QSettings(str(settings_path), QSettings.Format.IniFormat)
    )
    qtbot.addWidget(first)  # type: ignore[attr-defined]
    first.open_folder(measurement_folder)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: first._state.status is LoadStatus.READY  # noqa: SLF001
        and first._load_task is None,  # noqa: SLF001
        timeout=3_000,
    )
    first._role_panel.select_series(  # noqa: SLF001
        SeriesRole.CURRENT,
        "shot-001/channel-i",
    )
    first._role_panel.select_series(  # noqa: SLF001
        SeriesRole.SWEEP_VOLTAGE,
        "shot-001/channel-v",
    )
    assert first._state.role_assignments.is_complete  # noqa: SLF001

    restored = MainWindow(
        settings=QSettings(str(settings_path), QSettings.Format.IniFormat)
    )
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    restored.open_folder(measurement_folder)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: restored._state.status is LoadStatus.READY  # noqa: SLF001
        and restored._load_task is None,  # noqa: SLF001
        timeout=3_000,
    )

    assert restored._state.role_assignments.is_complete  # noqa: SLF001
    assert (  # noqa: SLF001
        restored._role_panel.series_id_for_role(SeriesRole.CURRENT)
        == "shot-001/channel-i"
    )
    assert (  # noqa: SLF001
        restored._role_panel.series_id_for_role(SeriesRole.SWEEP_VOLTAGE)
        == "shot-001/channel-v"
    )


class _FailingLoadStore:
    def load(self, folder: Path, shot_id: str) -> SeriesRoleAssignments:
        raise RoleAssignmentStoreError("load failed")

    def save(
        self,
        folder: Path,
        shot_id: str,
        assignments: SeriesRoleAssignments,
    ) -> None:
        return


class _FailingSaveStore:
    def load(self, folder: Path, shot_id: str) -> SeriesRoleAssignments:
        return SeriesRoleAssignments()

    def save(
        self,
        folder: Path,
        shot_id: str,
        assignments: SeriesRoleAssignments,
    ) -> None:
        raise RoleAssignmentStoreError("save failed")


def test_assignment_store_failure_does_not_block_raw_view(
    qtbot: object,
    tmp_path: Path,
) -> None:
    write_panta_series(tmp_path / "shot-001", "channel-i")
    window = MainWindow(assignment_store=_FailingLoadStore())
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window.open_folder(tmp_path)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._state.status is LoadStatus.READY  # noqa: SLF001
        and window._load_task is None,  # noqa: SLF001
        timeout=3_000,
    )

    assert window._state.selected_series_id == "shot-001/channel-i"  # noqa: SLF001
    assert "Raw表示は継続" in window._role_panel._persistence_status.text()  # noqa: SLF001


def test_assignment_save_failure_does_not_block_raw_view(
    qtbot: object,
    tmp_path: Path,
) -> None:
    write_panta_series(tmp_path / "shot-001", "channel-i")
    window = MainWindow(assignment_store=_FailingSaveStore())
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.open_folder(tmp_path)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._state.status is LoadStatus.READY  # noqa: SLF001
        and window._load_task is None,  # noqa: SLF001
        timeout=3_000,
    )

    window._role_panel.select_series(  # noqa: SLF001
        SeriesRole.CURRENT,
        "shot-001/channel-i",
    )

    assert window._state.status is LoadStatus.READY  # noqa: SLF001
    assert "Raw表示はそのまま" in window._role_panel._persistence_status.text()  # noqa: SLF001


def test_level2_window_runs_sweep_split_and_discards_stale_result(
    qtbot: object,
    tmp_path: Path,
) -> None:
    measurement_folder = tmp_path / "measurements"
    current_samples = np.arange(32, dtype=np.int16)
    voltage_samples = np.tile(
        np.asarray([-3, -2, -1, 0, 1, 2, 3, 2], dtype=np.int16),
        4,
    )
    write_panta_series(
        measurement_folder / "shot-001",
        "current",
        samples=current_samples,
        resolution=1.0,
        offset=0.0,
        time_resolution=0.01,
        time_offset=0.0,
    )
    write_panta_series(
        measurement_folder / "shot-001",
        "voltage",
        samples=voltage_samples,
        resolution=1.0,
        offset=0.0,
        time_resolution=0.01,
        time_offset=0.0,
    )
    window = MainWindow(
        settings=QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.open_folder(measurement_folder)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._state.status is LoadStatus.READY  # noqa: SLF001
        and window._load_task is None,  # noqa: SLF001
        timeout=3_000,
    )
    window._role_panel.select_series(  # noqa: SLF001
        SeriesRole.CURRENT,
        "shot-001/current",
    )
    window._role_panel.select_series(  # noqa: SLF001
        SeriesRole.SWEEP_VOLTAGE,
        "shot-001/voltage",
    )
    window._sweep_panel.set_parameters(  # noqa: SLF001
        LegacySweepSplitParameters(points_per_cycle=8)
    )

    window._sweep_panel._run_button.click()  # noqa: SLF001
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._state.sweep_status is SweepRunStatus.SUCCEEDED  # noqa: SLF001
        and window._sweep_task is None,  # noqa: SLF001
        timeout=3_000,
    )

    sweep_count: int = len(window._state.sweeps)  # noqa: SLF001
    assert sweep_count == 6
    assert window._sweep_browser.sweep_count == 6  # noqa: SLF001
    assert window._sweep_browser.selected_sweep == window._state.sweeps[0]  # noqa: SLF001
    first_sweep_item = window._sweep_browser._tree.topLevelItem(0)  # noqa: SLF001
    assert first_sweep_item.text(0) == "1"
    assert first_sweep_item.text(1) == "↑ 上昇"
    assert first_sweep_item.text(4) == "4"
    assert window._raw_plot.highlighted_sweep == window._state.sweeps[0]  # noqa: SLF001
    assert window._sweep_iv_plot.selected_sweep == window._state.sweeps[0]  # noqa: SLF001

    second_sweep = window._state.sweeps[1]  # noqa: SLF001
    assert window._sweep_browser.select_sweep(second_sweep.sweep_id)  # noqa: SLF001
    assert window._raw_plot.highlighted_sweep == second_sweep  # noqa: SLF001
    assert window._sweep_iv_plot.selected_sweep == second_sweep  # noqa: SLF001
    np.testing.assert_allclose(  # noqa: SLF001
        window._sweep_iv_plot.displayed_voltage_v,
        second_sweep.iv_voltage_v,
    )
    np.testing.assert_allclose(  # noqa: SLF001
        window._sweep_iv_plot.displayed_current_a,
        second_sweep.iv_current_a,
    )
    assert window._raw_plot.highlighted_interval_s == (  # noqa: SLF001
        float(second_sweep.time_s[0]),
        float(second_sweep.time_s[-1]),
    )
    assert second_sweep.voltage_series_id in window._raw_plot.highlight_description  # noqa: SLF001
    assert (
        f"sample {second_sweep.source_start_index:,}"
        in window._raw_plot.highlight_description  # noqa: SLF001
    )
    stale_generation = window._sweep_generation  # noqa: SLF001
    stale_result = SweepSplitResult(
        sweeps=window._state.sweeps,  # noqa: SLF001
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        interpolated_current=False,
        parameters=LegacySweepSplitParameters(points_per_cycle=8),
    )
    voltage_descriptor = window._state.catalog.find("shot-001/voltage")  # type: ignore[union-attr]  # noqa: E501, SLF001
    assert voltage_descriptor is not None

    window._load_series(voltage_descriptor)  # noqa: SLF001
    assert window._state.sweeps == ()  # noqa: SLF001
    assert window._sweep_browser.sweep_count == 0  # noqa: SLF001
    assert window._raw_plot.highlighted_sweep is None  # noqa: SLF001
    assert window._sweep_iv_plot.selected_sweep is None  # noqa: SLF001
    window._sweep_split_succeeded(stale_generation, stale_result)  # noqa: SLF001
    assert window._state.sweeps == ()  # noqa: SLF001
    assert window._sweep_browser.sweep_count == 0  # noqa: SLF001
