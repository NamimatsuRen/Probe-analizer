from __future__ import annotations

import logging
import math
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from probe_app.analysis import (
    AnalysisSettings,
    PreprocessedSweep,
    PreprocessingError,
    SavitzkyGolaySettings,
    analyze_preprocessed,
    preprocess_sweep,
)
from probe_app.application.ports import RoleAssignmentStore, ShotMetadataStore
from probe_app.application.queries import (
    build_catalog_summary_snapshot,
    build_export_candidates,
    build_summary_snapshot,
)
from probe_app.application.state import AppState, LoadStatus
from probe_app.application.use_cases import SweepSplitRequest, SweepSplitResult
from probe_app.domain.errors import RoleAssignmentStoreError
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
from probe_app.domain.models.catalog import FolderCatalog
from probe_app.domain.models.raw_series import RawSeries, RawSeriesDescriptor
from probe_app.domain.models.series_role import SeriesRole, SeriesRoleAssignments
from probe_app.domain.models.shot_metadata import ShotMetadata
from probe_app.domain.models.summary import SummaryScope, SummaryScopeKind
from probe_app.domain.models.sweep import Sweep
from probe_app.domain.services import (
    AssignmentApplyScope,
    propagate_role_assignments,
)
from probe_app.infrastructure.persistence import (
    QSettingsRoleAssignmentStore,
    QSettingsShotMetadataStore,
)
from probe_app.ui.widgets import (
    AnalysisWorkspace,
    DataBrowser,
    ExportWorkspace,
    MetadataPanel,
    RawPlot,
    RoleAssignmentPanel,
    StatusPanel,
    SummaryWorkspace,
    SweepBrowser,
    SweepIVPlot,
    SweepSplitPanel,
)
from probe_app.ui.workers import (
    AnalysisBatchInput,
    AnalysisBatchOutput,
    AnalysisBatchTask,
    FolderScanTask,
    SeriesLoadTask,
    SweepSplitTask,
)

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        settings: QSettings | None = None,
        assignment_store: RoleAssignmentStore | None = None,
        shot_metadata_store: ShotMetadataStore | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Probe Analizer — Rawデータブラウザ")
        self.resize(1440, 800)

        self._state = AppState()
        self._settings = (
            settings if settings is not None else QSettings("NamimatsuRen", "ProbeAnalizer")
        )
        self._assignment_store = (
            assignment_store
            if assignment_store is not None
            else QSettingsRoleAssignmentStore(self._settings)
        )
        self._shot_metadata_store = (
            shot_metadata_store
            if shot_metadata_store is not None
            else QSettingsShotMetadataStore(self._settings)
        )
        self._analysis_catalog = AnalysisCatalog()
        self._thread_pool = QThreadPool.globalInstance()
        self._scan_generation = 0
        self._load_generation = 0
        self._sweep_generation = 0
        self._analysis_generation = 0
        self._scan_task: FolderScanTask | None = None
        self._load_task: SeriesLoadTask | None = None
        self._sweep_task: SweepSplitTask | None = None
        self._analysis_task: AnalysisBatchTask | None = None
        self._analysis_batch_total = 0
        self._auto_sweep_shot_id: str | None = None
        self._auto_sweep_timer = QTimer(self)
        self._auto_sweep_timer.setSingleShot(True)
        self._auto_sweep_timer.setInterval(400)

        self._data_browser = DataBrowser()
        self._role_panel = RoleAssignmentPanel()
        self._raw_plot = RawPlot()
        self._metadata = MetadataPanel()
        self._sweep_panel = SweepSplitPanel()
        auto_sweep = self._settings.value("autoSweepSplit", True, type=bool)
        self._sweep_panel.set_auto_run_enabled(bool(auto_sweep))
        self._sweep_browser = SweepBrowser()
        self._sweep_iv_plot = SweepIVPlot(analysis_enabled=False)
        self._analysis_workspace = AnalysisWorkspace()
        self._analysis_sweep_iv_plot = self._analysis_workspace.plot
        self._preprocessing_panel = self._analysis_workspace.preprocessing_panel
        self._fit_panel = self._analysis_workspace.fit_panel
        self._summary_workspace = SummaryWorkspace()
        self._export_workspace = ExportWorkspace()
        self._details_tabs = QTabWidget()
        self._workspace_tabs = QTabWidget()
        self._status = StatusPanel()
        self._build_layout()
        self._build_toolbar()
        self._data_browser.series_selected.connect(self._load_series)
        self._role_panel.assignments_changed.connect(self._role_assignments_changed)
        self._role_panel.bulk_apply_requested.connect(
            self._bulk_apply_role_assignments
        )
        self._sweep_panel.run_requested.connect(self._start_sweep_split)
        self._sweep_panel.cancel_requested.connect(self._cancel_sweep_split)
        self._sweep_panel.auto_run_changed.connect(
            self._auto_sweep_setting_changed
        )
        self._sweep_panel.current_time_offset_preview_changed.connect(
            self._current_time_offset_preview_changed
        )
        self._auto_sweep_timer.timeout.connect(self._run_scheduled_sweep_split)
        self._sweep_browser.sweep_selected.connect(self._sweep_selected)
        self._preprocessing_panel.run_requested.connect(
            self._preprocessing_requested
        )
        self._fit_panel.run_requested.connect(self._full_analysis_requested)
        self._fit_panel.run_all_requested.connect(
            self._full_shot_analysis_requested
        )
        self._fit_panel.cancel_all_requested.connect(
            self._cancel_full_shot_analysis
        )
        self._summary_workspace.sweep_selected.connect(
            self._summary_sweep_selected
        )
        self._summary_workspace.open_analysis_requested.connect(
            self._open_summary_sweep_in_analysis
        )
        self._summary_workspace.exclusion_requested.connect(
            self._exclude_summary_sweep
        )
        self._summary_workspace.restore_requested.connect(
            self._restore_summary_sweep
        )
        self._summary_workspace.scope_changed.connect(
            self._summary_scope_changed
        )
        self._summary_workspace.shot_metadata_changed.connect(
            self._shot_metadata_changed
        )
        self._render_state()

    def _build_layout(self) -> None:
        left = QSplitter(Qt.Orientation.Vertical)
        left.addWidget(self._data_browser)
        left.addWidget(self._role_panel)
        left.setStretchFactor(0, 3)
        left.setStretchFactor(1, 2)
        left.setSizes([450, 310])

        self._data_workspace = QSplitter(Qt.Orientation.Vertical)
        self._data_workspace.setObjectName("dataConfirmationWorkspace")
        self._sweep_iv_plot.setObjectName("primaryIVPlot")
        self._raw_plot.setObjectName("secondaryRawPlot")
        self._details_tabs.setObjectName("dataConfirmationControlTabs")
        self._details_tabs.addTab(self._sweep_panel, "Sweep分割")
        self._details_tabs.addTab(self._sweep_browser, "Sweep一覧")
        self._details_tabs.addTab(self._metadata, "Raw情報")

        self._lower_workspace = QSplitter(Qt.Orientation.Horizontal)
        self._lower_workspace.setObjectName("rawAndControlWorkspace")
        self._lower_workspace.setChildrenCollapsible(False)
        self._lower_workspace.addWidget(self._raw_plot)
        self._lower_workspace.addWidget(self._details_tabs)
        self._lower_workspace.setStretchFactor(0, 2)
        self._lower_workspace.setStretchFactor(1, 1)
        self._lower_workspace.setSizes([640, 320])

        self._data_workspace.addWidget(self._sweep_iv_plot)
        self._data_workspace.addWidget(self._lower_workspace)
        self._data_workspace.setStretchFactor(0, 5)
        self._data_workspace.setStretchFactor(1, 2)
        self._data_workspace.setSizes([520, 240])

        self._workspace_tabs.setObjectName("primaryWorkspaceTabs")
        self._workspace_tabs.addTab(self._data_workspace, "データ確認")
        self._workspace_tabs.addTab(self._analysis_workspace, "解析")
        self._workspace_tabs.addTab(self._summary_workspace, "サマリー")
        self._workspace_tabs.addTab(self._export_workspace, "Export")
        self._workspace_tabs.setCurrentIndex(0)

        content = QSplitter(Qt.Orientation.Horizontal)
        content.addWidget(left)
        content.addWidget(self._workspace_tabs)
        content.setStretchFactor(0, 1)
        content.setStretchFactor(1, 4)
        content.setSizes([360, 920])

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content, 1)
        layout.addWidget(self._status)
        self.setCentralWidget(root)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("ファイル")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._open_action = QAction("フォルダを開く", self)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_action.triggered.connect(self._choose_folder)
        toolbar.addAction(self._open_action)

        self._reload_action = QAction("再読込", self)
        self._reload_action.setShortcut(QKeySequence.StandardKey.Refresh)
        self._reload_action.triggered.connect(self._reload_folder)
        toolbar.addAction(self._reload_action)

        self._cancel_action = QAction("キャンセル", self)
        self._cancel_action.setShortcut(QKeySequence("Esc"))
        self._cancel_action.triggered.connect(self._cancel_work)
        toolbar.addAction(self._cancel_action)

        toolbar.addSeparator()

        self._previous_sweep_action = QAction("前のSweep", self)
        self._previous_sweep_action.setShortcut(QKeySequence("Alt+Left"))
        self._previous_sweep_action.setStatusTip("1つ前のSweepを表示します")
        self._previous_sweep_action.triggered.connect(
            self._sweep_browser.select_previous
        )
        toolbar.addAction(self._previous_sweep_action)

        self._next_sweep_action = QAction("次のSweep", self)
        self._next_sweep_action.setShortcut(QKeySequence("Alt+Right"))
        self._next_sweep_action.setStatusTip("1つ次のSweepを表示します")
        self._next_sweep_action.triggered.connect(self._sweep_browser.select_next)
        toolbar.addAction(self._next_sweep_action)

    def _choose_folder(self) -> None:
        initial_value = self._settings.value("recentFolder", str(Path.home()), type=str)
        initial = str(initial_value)
        selected = QFileDialog.getExistingDirectory(
            self,
            "測定データのフォルダを選択",
            initial,
            QFileDialog.Option.ShowDirsOnly,
        )
        if selected:
            self.open_folder(Path(selected))

    def _reload_folder(self) -> None:
        if self._state.folder is not None:
            self.open_folder(self._state.folder)

    def open_folder(self, folder: Path) -> None:
        folder_key = str(folder.resolve())
        self._analysis_catalog = self._analysis_catalog.clear_other_folders(
            folder_key
        )
        self._cancel_tasks()
        self._scan_generation += 1
        self._load_generation += 1
        self._sweep_generation += 1
        generation = self._scan_generation
        self._state = self._state.start_loading(folder)
        self._settings.setValue("recentFolder", str(folder))
        self._data_browser.clear_catalog(str(folder))
        self._role_panel.clear_context()
        self._raw_plot.clear_plot("フォルダを走査しています…")
        self._metadata.clear()
        self._render_state()

        task = FolderScanTask(generation, folder)
        task.signals.succeeded.connect(self._folder_loaded)
        task.signals.failed.connect(self._folder_failed)
        task.signals.cancelled.connect(self._folder_cancelled)
        self._scan_task = task
        self._thread_pool.start(task)

    def _folder_loaded(self, generation: int, catalog_object: object) -> None:
        if generation != self._scan_generation or not isinstance(catalog_object, FolderCatalog):
            return
        self._scan_task = None
        self._state = self._state.apply_catalog(catalog_object)
        self._render_state()

        if catalog_object.is_empty:
            self._role_panel.clear_context()
            self._raw_plot.clear_plot("対応する測定データがありません")
            return
        self._data_browser.set_catalog(catalog_object)

    def _folder_failed(self, generation: int, message: str, details: str) -> None:
        if generation != self._scan_generation:
            return
        LOGGER.error("Folder scan failed: %s\n%s", message, details)
        self._scan_task = None
        self._state = self._state.fail(
            "フォルダを読み込めませんでした。場所とアクセス権を確認してください。"
        )
        self._status.set_status(LoadStatus.ERROR, self._state.message, details=message)
        self._raw_plot.clear_plot("読込エラー")
        QMessageBox.warning(
            self,
            "フォルダを読み込めません",
            f"{message}\n\n別のフォルダを選ぶか、アクセス権を確認してください。",
        )
        self._render_actions()

    def _folder_cancelled(self, generation: int) -> None:
        if generation != self._scan_generation:
            return
        self._scan_task = None
        self._state = self._state.cancel()
        self._render_state()
        self._raw_plot.clear_plot("読み込みをキャンセルしました")

    def _load_series(self, descriptor_object: object) -> None:
        if not isinstance(descriptor_object, RawSeriesDescriptor):
            return
        self._cancel_scheduled_sweep_split()
        self._invalidate_sweep_task()
        if self._state.catalog is not None:
            self._state = self._state.select_series(descriptor_object.series_id)
            self._activate_role_shot(descriptor_object.shot_id)
            self._render_sweep_panel()

        if self._load_task is not None:
            self._load_task.cancel()
        self._load_generation += 1
        generation = self._load_generation
        self._metadata.show_loading(descriptor_object)
        self._raw_plot.clear_plot(f"{descriptor_object.display_name} を読み込んでいます…")
        self._status.set_status(
            LoadStatus.LOADING,
            f"{descriptor_object.display_name} を読み込んでいます…",
        )
        self._render_actions()

        task = SeriesLoadTask(generation, descriptor_object)
        task.signals.succeeded.connect(self._series_loaded)
        task.signals.failed.connect(self._series_failed)
        task.signals.cancelled.connect(self._series_cancelled)
        self._load_task = task
        self._thread_pool.start(task)

    def _activate_role_shot(self, shot_id: str) -> None:
        catalog = self._state.catalog
        folder = self._state.folder
        if catalog is None or folder is None:
            self._role_panel.clear_context()
            return
        if self._state.role_assignment_shot_id == shot_id:
            if self._state.role_assignments.is_complete:
                self._schedule_auto_sweep_split(shot_id)
            return

        descriptors = catalog.series_for_shot(shot_id)
        warning = ""
        try:
            assignments = self._assignment_store.load(folder, shot_id)
        except RoleAssignmentStoreError as error:
            LOGGER.warning("Role assignment load failed: %s", error)
            assignments = SeriesRoleAssignments()
            warning = "保存済み設定を読み込めませんでした。Raw表示は継続できます。"

        valid_ids = {descriptor.series_id for descriptor in descriptors}
        valid_items = tuple(
            assignment
            for assignment in assignments.items
            if assignment.series_id in valid_ids
        )
        if len(valid_items) != len(assignments.items):
            assignments = SeriesRoleAssignments(valid_items)
            warning = "保存済み設定の一部が現在のフォルダにないため未割当にしました。"

        self._state = self._state.set_role_assignments(shot_id, assignments)
        self._role_panel.set_context(shot_id, descriptors, assignments)
        self._render_sweep_panel()
        if warning:
            self._role_panel.set_persistence_status(warning, error=True)
        elif assignments.items:
            self._role_panel.set_persistence_status("保存済み設定を復元しました")
        else:
            self._role_panel.set_persistence_status("役割を選択してください")
        if assignments.is_complete:
            self._schedule_auto_sweep_split(shot_id)

    def _role_assignments_changed(self, assignments_object: object) -> None:
        if not isinstance(assignments_object, SeriesRoleAssignments):
            return
        shot_id = self._state.role_assignment_shot_id
        folder = self._state.folder
        if shot_id is None or folder is None:
            return

        self._cancel_scheduled_sweep_split()
        self._invalidate_sweep_task()
        self._state = self._state.set_role_assignments(shot_id, assignments_object)
        self._render_sweep_panel()
        try:
            self._assignment_store.save(folder, shot_id, assignments_object)
        except RoleAssignmentStoreError as error:
            LOGGER.warning("Role assignment save failed: %s", error)
            self._role_panel.set_persistence_status(
                "設定を保存できませんでした。Raw表示はそのまま利用できます。",
                error=True,
            )
            if assignments_object.is_complete:
                self._schedule_auto_sweep_split(shot_id)
            return
        suffix = "（未割当あり）" if not assignments_object.is_complete else ""
        self._role_panel.set_persistence_status(f"設定を保存しました{suffix}")
        if assignments_object.is_complete:
            self._schedule_auto_sweep_split(shot_id)

    def _bulk_apply_role_assignments(self, scope_object: object) -> None:
        if not isinstance(scope_object, AssignmentApplyScope):
            return
        catalog = self._state.catalog
        folder = self._state.folder
        shot_id = self._state.role_assignment_shot_id
        assignments = self._state.role_assignments
        if (
            catalog is None
            or folder is None
            or shot_id is None
            or not assignments.is_complete
        ):
            self._role_panel.set_persistence_status(
                "currentとsweep voltageを選択してから一括適用してください。",
                error=True,
            )
            return

        try:
            result = propagate_role_assignments(
                catalog,
                shot_id,
                assignments,
                scope_object,
            )
        except ValueError as error:
            self._role_panel.set_persistence_status(str(error), error=True)
            return

        save_failures: list[str] = []
        saved_count = 0
        for target in result.assignments:
            try:
                self._assignment_store.save(
                    folder,
                    target.shot_id,
                    target.assignments,
                )
            except RoleAssignmentStoreError as error:
                LOGGER.warning(
                    "Bulk role assignment save failed for %s: %s",
                    target.shot_id,
                    error,
                )
                save_failures.append(
                    f"{target.shot_id}: 設定を保存できませんでした"
                )
                continue
            saved_count += 1

        skipped = [
            f"{failure.shot_id}: {failure.reason}"
            for failure in result.failures
        ]
        skipped.extend(save_failures)
        if skipped:
            message = (
                f"{saved_count} shotへ一括適用しました。"
                f"{len(skipped)} shotは変更していません。\n"
                + "\n".join(skipped)
            )
        else:
            message = f"{saved_count} shotへ一括適用しました"
        self._role_panel.set_persistence_status(message, error=bool(skipped))
        self._schedule_auto_sweep_split(shot_id)

    def _auto_sweep_setting_changed(self, enabled: bool) -> None:
        self._settings.setValue("autoSweepSplit", enabled)
        if not enabled:
            self._cancel_scheduled_sweep_split()
            return
        shot_id = self._state.role_assignment_shot_id
        if shot_id is not None and self._state.role_assignments.is_complete:
            self._schedule_auto_sweep_split(shot_id)

    def _schedule_auto_sweep_split(self, shot_id: str) -> None:
        if (
            not self._sweep_panel.auto_run_enabled
            or self._sweep_task is not None
            or self._state.role_assignment_shot_id != shot_id
            or not self._state.role_assignments.is_complete
        ):
            return
        self._auto_sweep_shot_id = shot_id
        self._auto_sweep_timer.start()
        self._render_actions()

    def _cancel_scheduled_sweep_split(self) -> None:
        self._auto_sweep_timer.stop()
        self._auto_sweep_shot_id = None

    def _run_scheduled_sweep_split(self) -> None:
        shot_id = self._auto_sweep_shot_id
        self._auto_sweep_shot_id = None
        if (
            shot_id is None
            or not self._sweep_panel.auto_run_enabled
            or self._state.role_assignment_shot_id != shot_id
            or not self._state.role_assignments.is_complete
            or self._sweep_task is not None
        ):
            self._render_actions()
            return
        self._start_sweep_split()

    def _start_sweep_split(self) -> None:
        self._cancel_scheduled_sweep_split()
        catalog = self._state.catalog
        assignments = self._state.role_assignments
        if catalog is None or not assignments.is_complete:
            self._state = self._state.fail_sweep_split(
                "currentとsweep voltageの両方を選択してください"
            )
            self._render_sweep_panel()
            return

        current_assignment = assignments.for_role(SeriesRole.CURRENT)
        voltage_assignment = assignments.for_role(SeriesRole.SWEEP_VOLTAGE)
        if current_assignment is None or voltage_assignment is None:
            return
        current_descriptor = catalog.find(current_assignment.series_id)
        voltage_descriptor = catalog.find(voltage_assignment.series_id)
        if current_descriptor is None or voltage_descriptor is None:
            self._state = self._state.fail_sweep_split(
                "割り当てた系列が現在のフォルダにありません",
                details="フォルダを再読込して役割を設定し直してください。",
            )
            self._render_sweep_panel()
            return

        try:
            request = SweepSplitRequest(
                current_descriptor=current_descriptor,
                voltage_descriptor=voltage_descriptor,
                assignments=assignments,
                parameters=self._sweep_panel.parameters(),
                current_time_offset_s=self._sweep_panel.current_time_offset_s(),
            )
        except ValueError as error:
            self._state = self._state.fail_sweep_split(
                "Sweep分割の入力を準備できません",
                details=str(error),
            )
            self._render_sweep_panel()
            return

        self._sweep_panel.clear_applied_current_time_offset()
        self._invalidate_sweep_task()
        generation = self._sweep_generation
        self._state = self._state.start_sweep_split()
        self._render_sweep_panel()
        self._status.set_status(LoadStatus.LOADING, self._state.sweep_message)
        self._render_actions()

        task = SweepSplitTask(generation, request)
        task.signals.succeeded.connect(self._sweep_split_succeeded)
        task.signals.failed.connect(self._sweep_split_failed)
        task.signals.cancelled.connect(self._sweep_split_cancelled)
        self._sweep_task = task
        self._thread_pool.start(task)

    def _sweep_split_succeeded(self, generation: int, result_object: object) -> None:
        if (
            generation != self._sweep_generation
            or not isinstance(result_object, SweepSplitResult)
        ):
            return
        self._sweep_task = None
        self._raw_plot.clear_current_time_offset_preview()
        self._sweep_panel.mark_current_time_offset_applied(
            result_object.current_time_offset_s
        )
        self._state = self._state.apply_sweep_result(
            result_object.sweeps,
            interpolated_current=result_object.interpolated_current,
            exclusions=result_object.exclusions,
        )
        interpolation = (
            "currentをSweep電圧の時間軸へ補間しました"
            if result_object.interpolated_current
            else "2系列の時間軸は一致しています"
        )
        offset_ms = result_object.current_time_offset_s * 1_000.0
        offset_description = (
            f"current時間補正: {offset_ms:+.6f} ms"
            "（+: 後ろのcurrentを参照）"
        )
        self._render_sweep_panel(details=f"{interpolation} / {offset_description}")
        self._status.set_status(self._state.status, self._state.sweep_message)
        self._render_actions()

    def _sweep_split_failed(self, generation: int, message: str, details: str) -> None:
        if generation != self._sweep_generation:
            return
        LOGGER.error("Sweep split failed: %s\n%s", message, details)
        self._sweep_task = None
        self._state = self._state.fail_sweep_split(
            "Sweepへ分割できませんでした。周期点数とsample範囲を確認してください。",
            details=message,
        )
        self._render_sweep_panel()
        self._status.set_status(
            self._state.status,
            self._state.sweep_message,
            details=message,
        )
        self._render_actions()

    def _sweep_split_cancelled(self, generation: int) -> None:
        if generation != self._sweep_generation:
            return
        self._sweep_task = None
        self._state = self._state.cancel_sweep_split()
        self._render_sweep_panel()
        self._status.set_status(self._state.status, self._state.sweep_message)
        self._render_actions()

    def _series_loaded(self, generation: int, series_object: object) -> None:
        if generation != self._load_generation or not isinstance(series_object, RawSeries):
            return
        self._load_task = None
        self._raw_plot.show_series(series_object)
        self._metadata.show_series(series_object)
        self._status.set_status(
            self._state.status,
            f"{series_object.descriptor.display_name}: {series_object.point_count:,} 点",
        )
        self._render_actions()

    def _sweep_selected(self, sweep_object: object) -> None:
        if isinstance(sweep_object, Sweep):
            self._state = self._state.select_sweep(sweep_object.sweep_id)
            selected_sweep = self._state.selected_sweep
            if selected_sweep is None:
                return
            self._raw_plot.highlight_sweep(selected_sweep)
            self._sweep_iv_plot.show_sweep(selected_sweep)
            self._analysis_sweep_iv_plot.show_sweep(selected_sweep)
            self._preprocessing_panel.select_sweep(selected_sweep.sweep_id)
            self._fit_panel.select_sweep(selected_sweep.sweep_id)
            self._render_analysis_workspace()
            self._render_actions()

    def _summary_sweep_selected(self, sweep_id: str) -> None:
        if not any(sweep.sweep_id == sweep_id for sweep in self._state.sweeps):
            return
        if self._state.selected_sweep_id == sweep_id:
            return
        sweep = next(
            sweep for sweep in self._state.sweeps if sweep.sweep_id == sweep_id
        )
        self._sweep_selected(sweep)

    def _open_summary_sweep_in_analysis(self, sweep_id: str) -> None:
        self._summary_sweep_selected(sweep_id)
        index = self._workspace_tabs.indexOf(self._analysis_workspace)
        if index >= 0:
            self._workspace_tabs.setCurrentIndex(index)

    def _exclude_summary_sweep(self, sweep_id: str, reason: str) -> None:
        revision = self._summary_action_revision(sweep_id)
        if revision is None:
            return
        try:
            self._state = self._state.exclude_analysis(revision, reason)
        except ValueError as error:
            self._summary_workspace.show_exclusion_error(str(error))
            return
        self._render_analysis_workspace()

    def _restore_summary_sweep(self, sweep_id: str) -> None:
        revision = self._summary_action_revision(sweep_id)
        if revision is None:
            return
        try:
            self._state = self._state.restore_analysis(revision)
        except ValueError as error:
            self._summary_workspace.show_exclusion_error(str(error))
            return
        self._render_analysis_workspace()

    def _summary_action_revision(
        self,
        sweep_id: str,
    ) -> AnalysisInputRevision | None:
        sweep = next(
            (item for item in self._state.sweeps if item.sweep_id == sweep_id),
            None,
        )
        if sweep is None:
            self._summary_workspace.show_exclusion_error(
                "対象Sweepが現在のshotにありません。"
            )
            return None
        try:
            return self._build_analysis_revision(
                sweep,
                self._preprocessing_panel.settings(),
            )
        except ValueError as error:
            self._summary_workspace.show_exclusion_error(str(error))
            return None

    def _current_time_offset_preview_changed(self, offset_s: float) -> None:
        selected_sweep = self._state.selected_sweep
        if selected_sweep is not None and math.isclose(
            offset_s,
            selected_sweep.current_time_offset_s,
            rel_tol=0.0,
            abs_tol=5e-10,
        ):
            self._raw_plot.clear_current_time_offset_preview()
            return
        self._raw_plot.preview_current_time_offset(offset_s)

    def _preprocessing_requested(self, settings_object: object) -> None:
        if not isinstance(settings_object, SavitzkyGolaySettings):
            return
        selected_sweep = self._state.selected_sweep
        if selected_sweep is None:
            self._preprocessing_panel.clear(
                "Sweepを選択してから前処理を実行してください"
            )
            return
        self._apply_preprocessing(selected_sweep, settings_object)

    def _apply_preprocessing(
        self,
        sweep: Sweep,
        settings: SavitzkyGolaySettings,
    ) -> None:
        try:
            revision = self._build_analysis_revision(sweep, settings)
        except ValueError as error:
            LOGGER.info("Analysis revision could not be built: %s", error)
            self._preprocessing_panel.show_error(sweep.sweep_id, str(error))
            return

        record = SweepAnalysisRecord.running(revision)
        self._state = self._state.record_analysis(record)
        self._fit_panel.invalidate(
            "前処理を再実行しています。後続解析は解析ボタンを押した時だけ更新します。"
        )
        self._render_analysis_workspace()
        try:
            result = preprocess_sweep(sweep, settings)
        except (PreprocessingError, ValueError) as error:
            LOGGER.info("Sweep preprocessing failed for %s: %s", sweep.sweep_id, error)
            failure = MethodOutcome(
                method_id="savitzky_golay",
                status=AnalysisStatus.ERROR,
                message=str(error),
            )
            record = record.with_stage_result(
                StageResult(
                    stage=AnalysisStage.PREPROCESSING,
                    status=AnalysisStatus.ERROR,
                    methods=(failure,),
                    message=str(error),
                )
            )
            self._state, _ = self._state.record_analysis_if_current(record, revision)
            self._analysis_sweep_iv_plot.clear_preprocessing(
                "dI/dV — 設定を確認してください"
            )
            self._preprocessing_panel.show_error(sweep.sweep_id, str(error))
            self._render_analysis_workspace()
            return

        status = (
            AnalysisStatus.REVIEW
            if result.spacing_warning
            else AnalysisStatus.VALID
        )
        outcome = MethodOutcome(
            method_id="savitzky_golay",
            status=status,
            message=result.spacing_warning,
            metrics=(
                (
                    "max_spacing_deviation_fraction",
                    result.max_spacing_deviation_fraction,
                ),
                ("polyorder", float(result.polyorder)),
                ("used_window_length", float(result.used_window_length)),
                ("voltage_step_v", result.voltage_step_v),
            ),
        )
        record = record.with_stage_result(
            StageResult(
                stage=AnalysisStage.PREPROCESSING,
                status=status,
                methods=(outcome,),
                message=result.spacing_warning,
            )
        )
        self._state, _ = self._state.record_analysis_if_current(record, revision)
        self._analysis_sweep_iv_plot.show_preprocessing(result)
        self._preprocessing_panel.show_result(result)
        self._render_analysis_workspace()

    def _full_analysis_requested(self, settings_object: object) -> None:
        if not isinstance(settings_object, AnalysisSettings):
            return
        sweep = self._state.selected_sweep
        if sweep is None:
            self._fit_panel.clear("Sweepを選択してから解析を実行してください")
            return
        try:
            preprocessing_settings = self._preprocessing_panel.settings()
            revision = self._build_analysis_revision(
                sweep,
                preprocessing_settings,
                settings_object,
            )
        except ValueError as error:
            self._fit_panel.show_error(sweep.sweep_id, str(error))
            return

        record = SweepAnalysisRecord.running(revision)
        self._state = self._state.record_analysis(record)
        self._render_analysis_workspace()
        try:
            preprocessed = preprocess_sweep(sweep, preprocessing_settings)
        except (PreprocessingError, ValueError) as error:
            message = str(error)
            failure = MethodOutcome(
                method_id="savitzky_golay",
                status=AnalysisStatus.ERROR,
                message=message,
            )
            record = record.with_stage_result(
                StageResult(
                    stage=AnalysisStage.PREPROCESSING,
                    status=AnalysisStatus.ERROR,
                    methods=(failure,),
                    message=message,
                )
            )
            self._state, _ = self._state.record_analysis_if_current(record, revision)
            self._preprocessing_panel.show_error(sweep.sweep_id, message)
            self._fit_panel.show_error(sweep.sweep_id, message)
            self._analysis_sweep_iv_plot.clear_preprocessing(
                "dI/dV — 前処理設定を確認してください"
            )
            self._render_analysis_workspace()
            return

        preprocessing_stage = self._preprocessing_stage(preprocessed)
        record = record.with_stage_result(preprocessing_stage)
        complete = analyze_preprocessed(preprocessed, settings_object)
        for index, stage_result in enumerate(complete.stage_results):
            record = record.with_stage_result(
                stage_result,
                overall_status=(
                    complete.status
                    if index == len(complete.stage_results) - 1
                    else None
                ),
            )
        self._state, _ = self._state.record_analysis_if_current(record, revision)
        self._preprocessing_panel.show_result(preprocessed)
        self._analysis_sweep_iv_plot.show_preprocessing(preprocessed)
        self._fit_panel.show_result(complete)
        self._analysis_sweep_iv_plot.show_analysis_result(complete)
        self._render_analysis_workspace()

    def _full_shot_analysis_requested(self, settings_object: object) -> None:
        if (
            not isinstance(settings_object, AnalysisSettings)
            or not self._state.sweeps
            or self._analysis_task is not None
        ):
            return
        try:
            preprocessing_settings = self._preprocessing_panel.settings()
            automatic_settings = replace(
                settings_object,
                potential=replace(
                    settings_object.potential,
                    selected_vf_candidate_id=None,
                    selected_phi_candidate_id=None,
                ),
            )
            inputs = tuple(
                AnalysisBatchInput(
                    sweep=sweep,
                    revision=self._build_analysis_revision(
                        sweep,
                        preprocessing_settings,
                        automatic_settings,
                    ),
                )
                for sweep in self._state.sweeps
            )
        except ValueError as error:
            selected = self._state.selected_sweep
            if selected is not None:
                self._fit_panel.show_error(selected.sweep_id, str(error))
            return

        self._analysis_generation += 1
        generation = self._analysis_generation
        self._analysis_batch_total = len(inputs)
        task = AnalysisBatchTask(
            generation,
            inputs,
            preprocessing_settings,
            automatic_settings,
        )
        task.signals.item_succeeded.connect(self._analysis_batch_item_succeeded)
        task.signals.failed.connect(self._analysis_batch_failed)
        task.signals.completed.connect(self._analysis_batch_completed)
        task.signals.cancelled.connect(self._analysis_batch_cancelled)
        self._analysis_task = task
        self._fit_panel.show_batch_progress(0, len(inputs))
        self._render_actions()
        self._thread_pool.start(task)

    def _analysis_batch_item_succeeded(
        self,
        generation: int,
        output_object: object,
        completed: int,
        total: int,
    ) -> None:
        if (
            generation != self._analysis_generation
            or not isinstance(output_object, AnalysisBatchOutput)
        ):
            return
        output = output_object
        try:
            self._state = self._state.record_analysis(output.record)
        except ValueError:
            return
        selected = self._state.selected_sweep
        if (
            selected is not None
            and selected.sweep_id == output.record.revision.sweep_id
            and output.complete is not None
        ):
            self._preprocessing_panel.show_result(output.complete.preprocessed)
            self._analysis_sweep_iv_plot.show_preprocessing(
                output.complete.preprocessed
            )
            self._fit_panel.show_result(output.complete)
            self._analysis_sweep_iv_plot.show_analysis_result(output.complete)
        self._fit_panel.show_batch_progress(
            completed,
            total,
            output.record.revision.sweep_id,
        )
        render_interval = max(1, total // 20)
        if completed == total or completed % render_interval == 0:
            self._render_summary_workspace()
            self._analysis_workspace.render_state(
                selected,
                (
                    self._state.analysis_results.latest_for_sweep(
                        selected.sweep_id
                    )
                    if selected is not None
                    else None
                ),
                empty_message=self._state.sweep_message,
            )

    def _analysis_batch_completed(self, generation: int, completed: int) -> None:
        if generation != self._analysis_generation:
            return
        total = self._analysis_batch_total
        self._analysis_task = None
        self._fit_panel.show_batch_finished(completed, total)
        self._render_analysis_workspace()
        self._render_actions()

    def _analysis_batch_cancelled(self, generation: int, completed: int) -> None:
        if generation != self._analysis_generation:
            return
        total = self._analysis_batch_total
        self._analysis_task = None
        self._fit_panel.show_batch_cancelled(completed, total)
        self._render_analysis_workspace()
        self._render_actions()

    def _analysis_batch_failed(
        self,
        generation: int,
        message: str,
        details: str,
    ) -> None:
        if generation != self._analysis_generation:
            return
        LOGGER.error("Shot analysis failed: %s\n%s", message, details)
        self._analysis_task = None
        selected = self._state.selected_sweep
        if selected is not None:
            self._fit_panel.show_error(selected.sweep_id, message)
        self._render_analysis_workspace()
        self._render_actions()

    def _cancel_full_shot_analysis(self) -> None:
        if self._analysis_task is not None:
            self._analysis_task.cancel()

    @staticmethod
    def _preprocessing_stage(result: PreprocessedSweep) -> StageResult:
        status = (
            AnalysisStatus.REVIEW
            if result.spacing_warning
            else AnalysisStatus.VALID
        )
        outcome = MethodOutcome(
            method_id="savitzky_golay",
            status=status,
            message=result.spacing_warning,
            metrics=(
                (
                    "max_spacing_deviation_fraction",
                    result.max_spacing_deviation_fraction,
                ),
                ("polyorder", float(result.polyorder)),
                ("used_window_length", float(result.used_window_length)),
                ("voltage_step_v", result.voltage_step_v),
            ),
        )
        return StageResult(
            stage=AnalysisStage.PREPROCESSING,
            status=status,
            methods=(outcome,),
            message=result.spacing_warning,
        )

    def _build_analysis_revision(
        self,
        sweep: Sweep,
        settings: SavitzkyGolaySettings,
        analysis_settings: AnalysisSettings | None = None,
    ) -> AnalysisInputRevision:
        folder = self._state.folder
        shot_id = self._state.role_assignment_shot_id
        current = self._state.role_assignments.for_role(SeriesRole.CURRENT)
        voltage = self._state.role_assignments.for_role(SeriesRole.SWEEP_VOLTAGE)
        if folder is None or shot_id is None or current is None or voltage is None:
            raise ValueError(
                "フォルダ・shot・current・sweep voltageの入力条件を確定できません"
            )
        split = self._sweep_panel.parameters()
        fit_settings = (
            analysis_settings
            if analysis_settings is not None
            else self._fit_panel.settings()
        )
        return AnalysisInputRevision(
            folder_key=str(folder.resolve()),
            shot_id=shot_id,
            sweep_id=sweep.sweep_id,
            current=SignalAssignmentRevision(
                series_id=current.series_id,
                scale=current.transform.scale,
                sign=current.transform.sign,
                output_unit=current.transform.output_unit,
            ),
            sweep_voltage=SignalAssignmentRevision(
                series_id=voltage.series_id,
                scale=voltage.transform.scale,
                sign=voltage.transform.sign,
                output_unit=voltage.transform.output_unit,
            ),
            split=SweepSplitRevision(
                points_per_cycle=split.points_per_cycle,
                sample_start=split.sample_start,
                sample_stop=split.sample_stop,
                current_time_offset_s=sweep.current_time_offset_s,
            ),
            preprocessing=PreprocessingRevision(
                window_length=settings.window_length,
                polyorder=settings.polyorder,
            ),
            fit_settings=fit_settings.as_revision_settings(),
            algorithm_version="level6-panta-v1",
            generation_id=self._sweep_generation,
        )

    def _series_failed(self, generation: int, message: str, details: str) -> None:
        if generation != self._load_generation:
            return
        LOGGER.error("Series load failed: %s\n%s", message, details)
        self._load_task = None
        self._raw_plot.clear_plot("この系列は表示できません")
        self._status.set_status(
            LoadStatus.ERROR,
            "系列を表示できません。別の系列を選択してください。",
            details=message,
        )
        self._render_actions()

    def _series_cancelled(self, generation: int) -> None:
        if generation != self._load_generation:
            return
        self._load_task = None
        self._status.set_status(self._state.status, self._state.message)
        self._render_actions()

    def _cancel_work(self) -> None:
        if self._analysis_task is not None:
            self._cancel_full_shot_analysis()
            return
        if self._sweep_task is not None:
            self._cancel_sweep_split()
            return
        self._cancel_tasks()
        self._scan_generation += 1
        self._load_generation += 1
        self._sweep_generation += 1
        self._analysis_generation += 1
        self._state = self._state.cancel()
        self._raw_plot.clear_plot("読み込みをキャンセルしました")
        self._render_state()

    def _cancel_tasks(self) -> None:
        self._cancel_scheduled_sweep_split()
        if self._scan_task is not None:
            self._scan_task.cancel()
            self._scan_task = None
        if self._load_task is not None:
            self._load_task.cancel()
            self._load_task = None
        if self._sweep_task is not None:
            self._sweep_task.cancel()
            self._sweep_task = None
        if self._analysis_task is not None:
            self._analysis_task.cancel()
            self._analysis_task = None
            self._analysis_generation += 1

    def _invalidate_sweep_task(self) -> None:
        if self._sweep_task is not None:
            self._sweep_task.cancel()
            self._sweep_task = None
        self._sweep_generation += 1

    def _cancel_sweep_split(self) -> None:
        self._cancel_scheduled_sweep_split()
        self._invalidate_sweep_task()
        self._state = self._state.cancel_sweep_split()
        self._render_sweep_panel()
        self._status.set_status(self._state.status, self._state.sweep_message)
        self._render_actions()

    def _render_state(self) -> None:
        details = ""
        if self._state.catalog is not None and self._state.catalog.problems:
            details = "\n".join(
                f"{problem.path.name}: {problem.message}"
                for problem in self._state.catalog.problems
            )
        self._status.set_status(self._state.status, self._state.message, details=details)
        self._render_sweep_panel()
        self._render_actions()

    def _render_actions(self) -> None:
        busy = (
            self._scan_task is not None
            or self._load_task is not None
            or self._sweep_task is not None
            or self._analysis_task is not None
            or self._auto_sweep_timer.isActive()
        )
        self._reload_action.setEnabled(self._state.folder is not None and not busy)
        self._cancel_action.setEnabled(busy)
        self._previous_sweep_action.setEnabled(
            not busy and self._sweep_browser.can_select_previous
        )
        self._next_sweep_action.setEnabled(
            not busy and self._sweep_browser.can_select_next
        )

    def _render_sweep_panel(self, *, details: str | None = None) -> None:
        self._sweep_panel.render_state(
            self._state.sweep_status,
            self._state.sweep_message,
            ready=(
                self._state.catalog is not None
                and self._state.role_assignments.is_complete
            ),
            details=self._state.sweep_error if details is None else details,
        )
        self._sweep_browser.render_state(
            self._state.sweep_status,
            self._state.sweeps,
            self._state.sweep_exclusions,
            self._state.sweep_message,
        )
        selected_sweep = self._state.selected_sweep
        if self._state.sweeps and selected_sweep is not None:
            browser_selection = self._sweep_browser.selected_sweep
            if (
                browser_selection is None
                or browser_selection.sweep_id != selected_sweep.sweep_id
            ):
                self._sweep_browser.select_sweep(selected_sweep.sweep_id)
            highlighted_sweep = self._raw_plot.highlighted_sweep
            if (
                highlighted_sweep is None
                or highlighted_sweep.sweep_id != selected_sweep.sweep_id
            ):
                self._raw_plot.highlight_sweep(selected_sweep)
            plotted_sweep = self._sweep_iv_plot.selected_sweep
            if plotted_sweep is None or plotted_sweep.sweep_id != selected_sweep.sweep_id:
                self._sweep_iv_plot.show_sweep(selected_sweep)
            analysis_sweep = self._analysis_sweep_iv_plot.selected_sweep
            if (
                analysis_sweep is None
                or analysis_sweep.sweep_id != selected_sweep.sweep_id
            ):
                self._analysis_sweep_iv_plot.show_sweep(selected_sweep)
            preprocessed = self._preprocessing_panel.result
            if preprocessed is None or preprocessed.sweep_id != selected_sweep.sweep_id:
                self._preprocessing_panel.select_sweep(selected_sweep.sweep_id)
                self._fit_panel.select_sweep(selected_sweep.sweep_id)
                self._analysis_sweep_iv_plot.clear_preprocessing(
                    "dI/dV — 前処理を実行してください"
                )
            elif self._analysis_sweep_iv_plot.preprocessed is not preprocessed:
                self._analysis_sweep_iv_plot.show_preprocessing(preprocessed)
        else:
            self._raw_plot.clear_sweep_highlight()
            self._sweep_iv_plot.clear_plot(self._state.sweep_message)
            self._analysis_sweep_iv_plot.clear_plot(self._state.sweep_message)
            self._preprocessing_panel.clear(self._state.sweep_message)
            self._fit_panel.clear(self._state.sweep_message)
        self._render_analysis_workspace()
        self._render_actions()

    def _render_analysis_workspace(self) -> None:
        selected_sweep = self._state.selected_sweep
        record = (
            self._state.analysis_results.latest_for_sweep(selected_sweep.sweep_id)
            if selected_sweep is not None
            else None
        )
        self._analysis_workspace.render_state(
            selected_sweep,
            record,
            empty_message=self._state.sweep_message,
        )
        self._render_summary_workspace()

    def _render_summary_workspace(self) -> None:
        folder = self._state.folder
        shot_id = self._state.role_assignment_shot_id
        if folder is None:
            self._summary_workspace.render_snapshot(
                None,
                empty_message=self._state.sweep_message,
            )
            self._export_workspace.render_candidates(
                None,
                empty_message=self._state.sweep_message,
            )
            return

        folder_key = str(folder.resolve())
        shot_metadata = self._summary_shot_metadata(folder)
        scope_kind = self._summary_workspace.selected_scope_kind
        if scope_kind is not SummaryScopeKind.CURRENT_SHOT:
            try:
                aggregate = build_catalog_summary_snapshot(
                    folder_key,
                    self._analysis_catalog,
                    scope_kind,
                )
            except ValueError as error:
                self._summary_workspace.render_aggregate(
                    None,
                    shot_metadata=shot_metadata,
                    empty_message=str(error),
                )
            else:
                self._summary_workspace.render_aggregate(
                    aggregate,
                    shot_metadata=shot_metadata,
                )
            return

        if shot_id is None or not self._state.sweeps:
            self._summary_workspace.render_snapshot(
                None,
                empty_message=self._state.sweep_message,
                shot_metadata=shot_metadata,
            )
            self._export_workspace.render_candidates(
                None,
                empty_message=self._state.sweep_message,
            )
            return

        current_revisions: dict[str, AnalysisInputRevision] = {}
        try:
            settings = self._preprocessing_panel.settings()
        except ValueError:
            settings = None
        if settings is not None:
            for sweep in self._state.sweeps:
                try:
                    current_revisions[sweep.sweep_id] = (
                        self._build_analysis_revision(sweep, settings)
                    )
                except ValueError:
                    break

        snapshot = build_summary_snapshot(
            SummaryScope(
                kind=SummaryScopeKind.CURRENT_SHOT,
                folder_key=folder_key,
                shot_ids=(shot_id,),
                current_revision_only=True,
            ),
            self._state.sweeps,
            self._state.analysis_results,
            current_revisions=current_revisions,
        )
        current_metadata = next(
            (
                metadata
                for metadata in shot_metadata
                if metadata.shot_id == shot_id
            ),
            ShotMetadata(folder_key=folder_key, shot_id=shot_id),
        )
        self._analysis_catalog = self._analysis_catalog.put(
            ShotAnalysisSnapshot.capture(snapshot, current_metadata)
        )
        self._summary_workspace.render_snapshot(
            snapshot,
            selected_sweep_id=self._state.selected_sweep_id,
            empty_message=self._state.sweep_message,
            shot_metadata=shot_metadata,
        )
        self._export_workspace.render_candidates(
            build_export_candidates(snapshot),
            empty_message=self._state.sweep_message,
        )

    def _summary_scope_changed(self, _scope: object) -> None:
        self._render_summary_workspace()

    def _summary_shot_metadata(
        self,
        folder: Path,
    ) -> tuple[ShotMetadata, ...]:
        catalog = self._state.catalog
        if catalog is None:
            return ()
        return tuple(
            self._shot_metadata_store.load(folder, shot_id)
            for shot_id in catalog.shots
        )

    def _shot_metadata_changed(self, metadata_object: object) -> None:
        folder = self._state.folder
        if folder is None or not isinstance(metadata_object, ShotMetadata):
            return
        folder_key = str(folder.resolve())
        if metadata_object.folder_key != folder_key:
            self._summary_workspace.show_metadata_error(
                "選択中フォルダとshot metadataが一致しません"
            )
            return
        try:
            self._shot_metadata_store.save(folder, metadata_object)
        except (OSError, ValueError) as error:
            LOGGER.warning("Shot metadata save failed: %s", error)
            self._summary_workspace.show_metadata_error(
                f"位置metadataを保存できませんでした: {error}"
            )
            return
        self._analysis_catalog = self._analysis_catalog.update_metadata(
            metadata_object
        )
        self._render_summary_workspace()
        self._summary_workspace.show_metadata_saved()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._cancel_tasks()
        super().closeEvent(event)
