from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QSplitter, QTabWidget

from probe_app.analysis import SavitzkyGolaySettings
from probe_app.application.state import LoadStatus, SweepRunStatus
from probe_app.application.use_cases import SweepSplitResult
from probe_app.domain.errors import RoleAssignmentStoreError
from probe_app.domain.models.analysis_result import AnalysisStage, AnalysisStatus
from probe_app.domain.models.series_role import (
    AssignedSeries,
    SeriesRole,
    SeriesRoleAssignments,
    SignalTransform,
)
from probe_app.domain.services import AssignmentApplyScope
from probe_app.domain.services.sweep_splitter import LegacySweepSplitParameters
from probe_app.ui.main_window import MainWindow
from tests.conftest import write_panta_series


def test_level1_window_starts(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert window.windowTitle() == "Probe Analizer — Rawデータブラウザ"
    assert window.centralWidget() is not None
    assert window._workspace_tabs.currentIndex() == 0  # noqa: SLF001
    assert [  # noqa: SLF001
        window._workspace_tabs.tabText(index)
        for index in range(window._workspace_tabs.count())
    ] == ["データ確認", "解析", "サマリー", "Export"]
    assert window._details_tabs.tabText(0) == "Sweep分割"  # noqa: SLF001
    assert window._details_tabs.tabText(1) == "Sweep一覧"  # noqa: SLF001
    assert window._details_tabs.tabText(2) == "Raw情報"  # noqa: SLF001
    assert window._details_tabs.count() == 3  # noqa: SLF001
    assert window._sweep_iv_plot.analysis_enabled is False  # noqa: SLF001
    assert window._analysis_sweep_iv_plot.analysis_enabled is True  # noqa: SLF001
    assert "Sweep未選択" in window._analysis_workspace.context_text  # noqa: SLF001
    assert "未作成" in window._analysis_workspace.revision_text  # noqa: SLF001
    assert "未実行" in window._analysis_workspace.stage_text(  # noqa: SLF001
        AnalysisStage.PREPROCESSING
    )
    assert "未実行" in window._analysis_workspace.stage_text(  # noqa: SLF001
        AnalysisStage.POTENTIAL
    )
    assert window._workspace_tabs.widget(2) is window._summary_workspace  # noqa: SLF001
    assert window._workspace_tabs.widget(3) is window._export_workspace  # noqa: SLF001
    assert window._summary_workspace.row_count == 0  # noqa: SLF001
    assert "shot未選択" in window._summary_workspace.context_text  # noqa: SLF001
    assert "表示だけでは解析を再計算しません" in (  # noqa: SLF001
        window._summary_workspace.policy_text  # noqa: SLF001
    )
    assert window._export_workspace.candidate_count == 0  # noqa: SLF001
    assert "shot未選択" in window._export_workspace.scope_text  # noqa: SLF001
    assert "解析値を変更・再計算しません" in (  # noqa: SLF001
        window._export_workspace.policy_text  # noqa: SLF001
    )
    assert window._export_workspace.renderer_constructed  # noqa: SLF001
    assert window._sweep_iv_plot.parent() is not window._details_tabs  # noqa: SLF001
    assert window._raw_plot.parent() is window._lower_workspace  # noqa: SLF001
    assert window._raw_plot.parent() is not window._details_tabs  # noqa: SLF001
    assert isinstance(window._details_tabs, QTabWidget)  # noqa: SLF001
    assert isinstance(window._lower_workspace, QSplitter)  # noqa: SLF001
    assert (  # noqa: SLF001
        window._lower_workspace.orientation() is Qt.Orientation.Horizontal
    )
    assert window._lower_workspace.widget(0) is window._raw_plot  # noqa: SLF001
    assert window._lower_workspace.widget(1) is window._data_controls  # noqa: SLF001
    assert window._details_tabs.parent() is window._data_controls  # noqa: SLF001
    assert (  # noqa: SLF001
        window._previous_sweep_button.parent() is window._sweep_navigation_bar
    )
    assert window._next_sweep_button.parent() is window._sweep_navigation_bar  # noqa: SLF001
    assert window._previous_sweep_button.text() == "← 前のSweep"  # noqa: SLF001
    assert window._next_sweep_button.text() == "次のSweep →"  # noqa: SLF001

    raw_width, controls_width = window._lower_workspace.sizes()  # noqa: SLF001
    assert raw_width > controls_width
    assert 1.5 <= raw_width / controls_width <= 2.5

    selection_width, workspace_width = window._main_splitter.sizes()  # noqa: SLF001
    assert selection_width < workspace_width
    assert selection_width / (selection_width + workspace_width) < 0.2

    for index in range(window._details_tabs.count()):  # noqa: SLF001
        window._details_tabs.setCurrentIndex(index)  # noqa: SLF001
        assert window._raw_plot.isVisibleTo(window)  # noqa: SLF001

    preprocessing_before = window._preprocessing_panel.result  # noqa: SLF001
    for index in range(window._workspace_tabs.count()):  # noqa: SLF001
        window._workspace_tabs.setCurrentIndex(index)  # noqa: SLF001
    assert window._preprocessing_panel.result is preprocessing_before  # noqa: SLF001
    assert "Sweep未選択" in window._analysis_workspace.context_text  # noqa: SLF001


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
    first._sweep_panel.set_auto_run_enabled(False)  # noqa: SLF001
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


class _RecordingAssignmentStore:
    def __init__(
        self,
        initial: dict[str, SeriesRoleAssignments] | None = None,
    ) -> None:
        self.values = dict(initial or {})

    def load(self, folder: Path, shot_id: str) -> SeriesRoleAssignments:
        return self.values.get(shot_id, SeriesRoleAssignments())

    def save(
        self,
        folder: Path,
        shot_id: str,
        assignments: SeriesRoleAssignments,
    ) -> None:
        self.values[shot_id] = assignments


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


def test_role_assignments_apply_to_all_matching_shots_without_overwriting_skips(
    qtbot: object,
    tmp_path: Path,
) -> None:
    measurement_folder = tmp_path / "measurements"
    for shot_id in ("shot-001", "shot-002"):
        write_panta_series(measurement_folder / shot_id, "current-channel")
        write_panta_series(measurement_folder / shot_id, "voltage-channel")
    write_panta_series(measurement_folder / "shot-003", "current-channel")
    existing_skipped = SeriesRoleAssignments(
        (
            AssignedSeries(
                role=SeriesRole.CURRENT,
                series_id="shot-003/current-channel",
                transform=SignalTransform(
                    scale=0.25,
                    sign=1.0,
                    output_unit="A",
                ),
            ),
        )
    )
    store = _RecordingAssignmentStore({"shot-003": existing_skipped})
    window = MainWindow(
        settings=QSettings(
            str(tmp_path / "settings.ini"),
            QSettings.Format.IniFormat,
        ),
        assignment_store=store,
    )
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window._sweep_panel.set_auto_run_enabled(False)  # noqa: SLF001
    window.open_folder(measurement_folder)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._state.status is LoadStatus.READY  # noqa: SLF001
        and window._load_task is None,  # noqa: SLF001
        timeout=3_000,
    )

    window._role_panel.select_series(  # noqa: SLF001
        SeriesRole.CURRENT,
        "shot-001/current-channel",
    )
    window._role_panel.select_series(  # noqa: SLF001
        SeriesRole.SWEEP_VOLTAGE,
        "shot-001/voltage-channel",
    )
    window._role_panel.set_apply_scope(AssignmentApplyScope.ALL)  # noqa: SLF001
    window._role_panel._apply_button.click()  # noqa: SLF001

    shot_two = store.values["shot-002"]
    assert (
        shot_two.for_role(SeriesRole.CURRENT).series_id  # type: ignore[union-attr]
        == "shot-002/current-channel"
    )
    assert (
        shot_two.for_role(SeriesRole.SWEEP_VOLTAGE).series_id  # type: ignore[union-attr]
        == "shot-002/voltage-channel"
    )
    assert store.values["shot-003"] == existing_skipped
    persistence_message = window._role_panel._persistence_status.text()  # noqa: SLF001
    assert "2 shotへ一括適用" in persistence_message
    assert "shot-003" in persistence_message
    assert "変更していません" in persistence_message


def test_complete_role_assignments_start_sweep_split_automatically(
    qtbot: object,
    tmp_path: Path,
) -> None:
    measurement_folder = tmp_path / "measurements"
    write_panta_series(
        measurement_folder / "shot-001",
        "current",
        samples=np.arange(32, dtype=np.int16),
        resolution=1.0,
        offset=0.0,
        time_resolution=0.01,
        time_offset=0.0,
    )
    write_panta_series(
        measurement_folder / "shot-001",
        "voltage",
        samples=np.tile(
            np.asarray([-3, -1, 1, 3, 3, 1, -1, -3], dtype=np.int16),
            4,
        ),
        resolution=1.0,
        offset=0.0,
        time_resolution=0.01,
        time_offset=0.0,
    )
    window = MainWindow(
        settings=QSettings(
            str(tmp_path / "settings.ini"),
            QSettings.Format.IniFormat,
        )
    )
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window._sweep_panel.set_parameters(  # noqa: SLF001
        LegacySweepSplitParameters(
            points_per_cycle=8,
            sample_start=0,
            sample_stop=32,
        )
    )
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

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._state.sweep_status is SweepRunStatus.SUCCEEDED  # noqa: SLF001
        and window._sweep_task is None,  # noqa: SLF001
        timeout=3_000,
    )
    assert len(window._state.sweeps) == 6  # noqa: SLF001


def test_level2_window_runs_sweep_split_and_discards_stale_result(
    qtbot: object,
    tmp_path: Path,
) -> None:
    measurement_folder = tmp_path / "measurements"
    current_samples = np.arange(32, dtype=np.int16)
    voltage_samples = np.tile(
        np.asarray([-3, -1, 1, 3, 3, 1, -1, -3], dtype=np.int16),
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
    window._sweep_panel.set_auto_run_enabled(False)  # noqa: SLF001
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
        LegacySweepSplitParameters(
            points_per_cycle=8,
            sample_start=0,
            sample_stop=32,
        )
    )
    window._preprocessing_panel.set_settings(  # noqa: SLF001
        SavitzkyGolaySettings(window_length=3, polyorder=2)
    )

    window._sweep_panel._run_button.click()  # noqa: SLF001
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._state.sweep_status is SweepRunStatus.SUCCEEDED  # noqa: SLF001
        and window._sweep_task is None,  # noqa: SLF001
        timeout=3_000,
    )

    sweep_count: int = len(window._state.sweeps)  # noqa: SLF001
    assert sweep_count == 6
    assert len(window._state.sweep_exclusions) == 1  # noqa: SLF001
    assert window._sweep_browser.sweep_count == 6  # noqa: SLF001
    assert window._sweep_browser.exclusion_count == 1  # noqa: SLF001
    exclusion_item = window._sweep_browser._issues_tree.topLevelItem(0)  # noqa: SLF001
    assert exclusion_item.text(0) == "24–31"
    assert exclusion_item.text(3) == "末尾の周期合わせ"
    assert window._sweep_browser.selected_sweep == window._state.sweeps[0]  # noqa: SLF001
    assert (  # noqa: SLF001
        window._state.selected_sweep_id == window._state.sweeps[0].sweep_id
    )
    first_sweep_item = window._sweep_browser._tree.topLevelItem(0)  # noqa: SLF001
    assert first_sweep_item.text(0) == "1"
    assert first_sweep_item.text(1) == "↑ 上昇"
    assert first_sweep_item.text(4) == "4"
    assert window._raw_plot.highlighted_sweep == window._state.sweeps[0]  # noqa: SLF001
    assert window._sweep_iv_plot.selected_sweep == window._state.sweeps[0]  # noqa: SLF001
    assert (  # noqa: SLF001
        window._preprocessing_panel.selected_sweep_id
        == window._state.sweeps[0].sweep_id
    )
    assert window._preprocessing_panel.result is None  # noqa: SLF001
    assert window._sweep_iv_plot.preprocessed is None  # noqa: SLF001
    assert window._analysis_sweep_iv_plot.preprocessed is None  # noqa: SLF001
    assert (
        window._state.sweeps[0].sweep_id  # noqa: SLF001
        in window._analysis_workspace.context_text  # noqa: SLF001
    )
    assert "前処理は未実行" in window._analysis_workspace.revision_text  # noqa: SLF001
    assert "未実行" in window._analysis_workspace.stage_text(  # noqa: SLF001
        AnalysisStage.PREPROCESSING
    )
    window._preprocessing_panel._run_button.click()  # noqa: SLF001
    assert window._preprocessing_panel.result is not None  # noqa: SLF001
    assert window._analysis_sweep_iv_plot.preprocessed is not None  # noqa: SLF001
    first_record = window._state.analysis_results.latest_for_sweep(  # noqa: SLF001
        window._state.sweeps[0].sweep_id  # noqa: SLF001
    )
    assert first_record is not None
    assert first_record.status in (AnalysisStatus.VALID, AnalysisStatus.REVIEW)
    assert first_record.revision.preprocessing.polyorder == 2
    assert (
        first_record.revision.cache_key[:10]
        in window._analysis_workspace.revision_text  # noqa: SLF001
    )
    assert (
        "完了" in window._analysis_workspace.stage_text(AnalysisStage.PREPROCESSING)  # noqa: SLF001
        or "要確認"
        in window._analysis_workspace.stage_text(AnalysisStage.PREPROCESSING)  # noqa: SLF001
    )
    original_sweeps = window._state.sweeps  # noqa: SLF001
    original_sweep_generation = window._sweep_generation  # noqa: SLF001
    original_iv_sweep = window._sweep_iv_plot.selected_sweep  # noqa: SLF001
    original_preprocessed = window._analysis_sweep_iv_plot.preprocessed  # noqa: SLF001
    selected_before_preview = window._state.selected_sweep  # noqa: SLF001
    assert selected_before_preview is not None
    assert window._raw_plot.displayed_series_id == "shot-001/current"  # noqa: SLF001

    window._sweep_panel.set_current_time_offset_s(0.02)  # noqa: SLF001

    assert window._state.sweeps is original_sweeps  # noqa: SLF001
    assert window._sweep_generation == original_sweep_generation  # noqa: SLF001
    assert window._sweep_task is None  # noqa: SLF001
    assert window._sweep_iv_plot.selected_sweep is original_iv_sweep  # noqa: SLF001
    assert window._analysis_sweep_iv_plot.preprocessed is original_preprocessed  # noqa: SLF001
    assert selected_before_preview.current_time_offset_s == 0.0
    assert window._raw_plot.preview_current_time_offset_s == 0.02  # noqa: SLF001
    assert window._raw_plot.highlighted_interval_ms == pytest.approx(  # noqa: SLF001
        (
            (float(selected_before_preview.time_s[0]) + 0.02) * 1_000.0,
            (float(selected_before_preview.time_s[-1]) + 0.02) * 1_000.0,
        )
    )
    assert "未適用" in window._raw_plot.highlight_description  # noqa: SLF001
    assert "未適用" in window._sweep_panel.offset_status_text  # noqa: SLF001

    window._sweep_panel.set_current_time_offset_s(0.0)  # noqa: SLF001
    assert window._raw_plot.preview_current_time_offset_s is None  # noqa: SLF001

    window._preprocessing_panel.set_settings(  # noqa: SLF001
        SavitzkyGolaySettings(window_length=3, polyorder=1)
    )
    window._preprocessing_panel._run_button.click()  # noqa: SLF001
    assert window._state.sweeps is original_sweeps  # noqa: SLF001
    assert window._sweep_generation == original_sweep_generation  # noqa: SLF001
    assert window._sweep_task is None  # noqa: SLF001
    assert window._preprocessing_panel.result is not None  # noqa: SLF001
    assert window._preprocessing_panel.result.polyorder == 1  # noqa: SLF001
    revised_record = window._state.analysis_results.latest_for_sweep(  # noqa: SLF001
        window._state.sweeps[0].sweep_id  # noqa: SLF001
    )
    assert revised_record is not None
    assert revised_record.revision.preprocessing.polyorder == 1
    assert revised_record.revision.cache_key != first_record.revision.cache_key
    assert not window._previous_sweep_action.isEnabled()  # noqa: SLF001
    assert window._next_sweep_action.isEnabled()  # noqa: SLF001
    assert not window._previous_sweep_button.isEnabled()  # noqa: SLF001
    assert window._next_sweep_button.isEnabled()  # noqa: SLF001
    assert (  # noqa: SLF001
        window._previous_sweep_action.shortcut().toString() == "Alt+Left"
    )
    assert window._next_sweep_action.shortcut().toString() == "Alt+Right"  # noqa: SLF001

    second_sweep = window._state.sweeps[1]  # noqa: SLF001
    qtbot.mouseClick(  # type: ignore[attr-defined]
        window._next_sweep_button,  # noqa: SLF001
        Qt.MouseButton.LeftButton,
    )
    assert window._sweep_browser.selected_sweep == second_sweep  # noqa: SLF001
    assert window._state.selected_sweep == second_sweep  # noqa: SLF001
    assert window._raw_plot.highlighted_sweep == second_sweep  # noqa: SLF001
    assert window._sweep_iv_plot.selected_sweep == second_sweep  # noqa: SLF001
    assert window._analysis_sweep_iv_plot.selected_sweep == second_sweep  # noqa: SLF001
    assert window._preprocessing_panel.selected_sweep_id == second_sweep.sweep_id  # noqa: SLF001
    assert window._preprocessing_panel.result is None  # noqa: SLF001
    assert window._sweep_iv_plot.preprocessed is None  # noqa: SLF001
    assert window._analysis_sweep_iv_plot.preprocessed is None  # noqa: SLF001
    window._preprocessing_panel._run_button.click()  # noqa: SLF001
    assert window._preprocessing_panel.result is not None  # noqa: SLF001
    assert window._analysis_sweep_iv_plot.preprocessed is not None  # noqa: SLF001
    assert window._previous_sweep_action.isEnabled()  # noqa: SLF001
    assert window._next_sweep_action.isEnabled()  # noqa: SLF001
    assert window._previous_sweep_button.isEnabled()  # noqa: SLF001
    assert window._next_sweep_button.isEnabled()  # noqa: SLF001
    assert window._summary_workspace.row_count == sweep_count  # noqa: SLF001
    assert (  # noqa: SLF001
        window._summary_workspace.selected_sweep_id == second_sweep.sweep_id
    )
    assert window._summary_workspace.status_text(  # noqa: SLF001
        AnalysisStatus.NOT_RUN
    ).endswith(str(sweep_count))
    summary_index = window._workspace_tabs.indexOf(  # noqa: SLF001
        window._summary_workspace  # noqa: SLF001
    )
    analysis_index = window._workspace_tabs.indexOf(  # noqa: SLF001
        window._analysis_workspace  # noqa: SLF001
    )
    window._workspace_tabs.setCurrentIndex(summary_index)  # noqa: SLF001
    qtbot.mouseClick(  # type: ignore[attr-defined]
        window._summary_workspace._open_analysis,  # noqa: SLF001
        Qt.MouseButton.LeftButton,
    )
    assert window._workspace_tabs.currentIndex() == analysis_index  # noqa: SLF001
    assert window._state.selected_sweep == second_sweep  # noqa: SLF001
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
    last_sweep = window._state.sweeps[-1]  # noqa: SLF001
    assert window._sweep_browser.select_sweep(last_sweep.sweep_id)  # noqa: SLF001
    assert window._raw_plot.highlighted_sweep == last_sweep  # noqa: SLF001
    assert window._sweep_iv_plot.selected_sweep == last_sweep  # noqa: SLF001
    assert window._previous_sweep_action.isEnabled()  # noqa: SLF001
    assert not window._next_sweep_action.isEnabled()  # noqa: SLF001
    assert window._previous_sweep_button.isEnabled()  # noqa: SLF001
    assert not window._next_sweep_button.isEnabled()  # noqa: SLF001
    window._next_sweep_action.trigger()  # noqa: SLF001
    assert window._sweep_browser.selected_sweep == last_sweep  # noqa: SLF001

    qtbot.mouseClick(  # type: ignore[attr-defined]
        window._previous_sweep_button,  # noqa: SLF001
        Qt.MouseButton.LeftButton,
    )
    penultimate_sweep = window._state.sweeps[-2]  # noqa: SLF001
    assert window._sweep_browser.selected_sweep == penultimate_sweep  # noqa: SLF001
    assert window._raw_plot.highlighted_sweep == penultimate_sweep  # noqa: SLF001
    assert window._sweep_iv_plot.selected_sweep == penultimate_sweep  # noqa: SLF001

    stale_generation = window._sweep_generation  # noqa: SLF001
    stale_result = SweepSplitResult(
        sweeps=window._state.sweeps,  # noqa: SLF001
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        interpolated_current=False,
        parameters=LegacySweepSplitParameters(
            points_per_cycle=8,
            sample_start=0,
            sample_stop=32,
        ),
    )
    voltage_descriptor = window._state.catalog.find("shot-001/voltage")  # type: ignore[union-attr]  # noqa: E501, SLF001
    assert voltage_descriptor is not None

    window._load_series(voltage_descriptor)  # noqa: SLF001
    assert window._state.sweeps == ()  # noqa: SLF001
    assert window._state.sweep_exclusions == ()  # noqa: SLF001
    assert window._state.selected_sweep_id is None  # noqa: SLF001
    assert window._sweep_browser.sweep_count == 0  # noqa: SLF001
    assert window._sweep_browser.exclusion_count == 0  # noqa: SLF001
    assert window._raw_plot.highlighted_sweep is None  # noqa: SLF001
    assert window._sweep_iv_plot.selected_sweep is None  # noqa: SLF001
    assert window._analysis_sweep_iv_plot.selected_sweep is None  # noqa: SLF001
    assert window._preprocessing_panel.selected_sweep_id is None  # noqa: SLF001
    assert window._preprocessing_panel.result is None  # noqa: SLF001
    assert not window._previous_sweep_action.isEnabled()  # noqa: SLF001
    assert not window._next_sweep_action.isEnabled()  # noqa: SLF001
    assert not window._previous_sweep_button.isEnabled()  # noqa: SLF001
    assert not window._next_sweep_button.isEnabled()  # noqa: SLF001
    window._sweep_split_succeeded(stale_generation, stale_result)  # noqa: SLF001
    assert window._state.sweeps == ()  # noqa: SLF001
    assert window._sweep_browser.sweep_count == 0  # noqa: SLF001
