from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThreadPool
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
    PreprocessingError,
    SavitzkyGolaySettings,
    preprocess_sweep,
)
from probe_app.application.ports import RoleAssignmentStore
from probe_app.application.state import AppState, LoadStatus
from probe_app.application.use_cases import SweepSplitRequest, SweepSplitResult
from probe_app.domain.errors import RoleAssignmentStoreError
from probe_app.domain.models.catalog import FolderCatalog
from probe_app.domain.models.raw_series import RawSeries, RawSeriesDescriptor
from probe_app.domain.models.series_role import SeriesRole, SeriesRoleAssignments
from probe_app.domain.models.sweep import Sweep
from probe_app.infrastructure.persistence import QSettingsRoleAssignmentStore
from probe_app.ui.widgets import (
    DataBrowser,
    MetadataPanel,
    PreprocessingPanel,
    RawPlot,
    RoleAssignmentPanel,
    StatusPanel,
    SweepBrowser,
    SweepIVPlot,
    SweepSplitPanel,
)
from probe_app.ui.workers import FolderScanTask, SeriesLoadTask, SweepSplitTask

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        settings: QSettings | None = None,
        assignment_store: RoleAssignmentStore | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Probe Analizer — Rawデータブラウザ")
        self.resize(1280, 760)

        self._state = AppState()
        self._settings = (
            settings if settings is not None else QSettings("NamimatsuRen", "ProbeAnalizer")
        )
        self._assignment_store = (
            assignment_store
            if assignment_store is not None
            else QSettingsRoleAssignmentStore(self._settings)
        )
        self._thread_pool = QThreadPool.globalInstance()
        self._scan_generation = 0
        self._load_generation = 0
        self._sweep_generation = 0
        self._scan_task: FolderScanTask | None = None
        self._load_task: SeriesLoadTask | None = None
        self._sweep_task: SweepSplitTask | None = None

        self._data_browser = DataBrowser()
        self._role_panel = RoleAssignmentPanel()
        self._raw_plot = RawPlot()
        self._metadata = MetadataPanel()
        self._sweep_panel = SweepSplitPanel()
        self._sweep_browser = SweepBrowser()
        self._sweep_iv_plot = SweepIVPlot()
        self._preprocessing_panel = PreprocessingPanel()
        self._details_tabs = QTabWidget()
        self._status = StatusPanel()
        self._build_layout()
        self._build_toolbar()
        self._data_browser.series_selected.connect(self._load_series)
        self._role_panel.assignments_changed.connect(self._role_assignments_changed)
        self._sweep_panel.run_requested.connect(self._start_sweep_split)
        self._sweep_panel.cancel_requested.connect(self._cancel_sweep_split)
        self._sweep_browser.sweep_selected.connect(self._sweep_selected)
        self._preprocessing_panel.run_requested.connect(
            self._preprocessing_requested
        )
        self._render_state()

    def _build_layout(self) -> None:
        left = QSplitter(Qt.Orientation.Vertical)
        left.addWidget(self._data_browser)
        left.addWidget(self._role_panel)
        left.setStretchFactor(0, 3)
        left.setStretchFactor(1, 2)
        left.setSizes([450, 310])

        self._analysis_workspace = QSplitter(Qt.Orientation.Vertical)
        self._analysis_workspace.setObjectName("analysisWorkspace")
        self._sweep_iv_plot.setObjectName("primaryIVPlot")
        self._raw_plot.setObjectName("secondaryRawPlot")
        self._details_tabs.setObjectName("analysisControlTabs")
        self._details_tabs.addTab(self._sweep_panel, "Sweep分割")
        self._details_tabs.addTab(self._sweep_browser, "Sweep一覧")
        self._details_tabs.addTab(self._preprocessing_panel, "平滑化・微分")
        self._details_tabs.addTab(self._metadata, "Raw情報")

        self._lower_workspace = QSplitter(Qt.Orientation.Horizontal)
        self._lower_workspace.setObjectName("rawAndControlWorkspace")
        self._lower_workspace.setChildrenCollapsible(False)
        self._lower_workspace.addWidget(self._raw_plot)
        self._lower_workspace.addWidget(self._details_tabs)
        self._lower_workspace.setStretchFactor(0, 2)
        self._lower_workspace.setStretchFactor(1, 1)
        self._lower_workspace.setSizes([640, 320])

        self._analysis_workspace.addWidget(self._sweep_iv_plot)
        self._analysis_workspace.addWidget(self._lower_workspace)
        self._analysis_workspace.setStretchFactor(0, 5)
        self._analysis_workspace.setStretchFactor(1, 2)
        self._analysis_workspace.setSizes([520, 240])

        content = QSplitter(Qt.Orientation.Horizontal)
        content.addWidget(left)
        content.addWidget(self._analysis_workspace)
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

    def _role_assignments_changed(self, assignments_object: object) -> None:
        if not isinstance(assignments_object, SeriesRoleAssignments):
            return
        shot_id = self._state.role_assignment_shot_id
        folder = self._state.folder
        if shot_id is None or folder is None:
            return

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
            return
        suffix = "（未割当あり）" if not assignments_object.is_complete else ""
        self._role_panel.set_persistence_status(f"設定を保存しました{suffix}")

    def _start_sweep_split(self) -> None:
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
            self._apply_preprocessing(
                selected_sweep,
                self._preprocessing_panel.settings(),
            )
            self._render_actions()

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
            result = preprocess_sweep(sweep, settings)
        except (PreprocessingError, ValueError) as error:
            LOGGER.info("Sweep preprocessing failed for %s: %s", sweep.sweep_id, error)
            self._sweep_iv_plot.clear_preprocessing("dI/dV — 設定を確認してください")
            self._preprocessing_panel.show_error(sweep.sweep_id, str(error))
            return
        self._sweep_iv_plot.show_preprocessing(result)
        self._preprocessing_panel.show_result(result)

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
        if self._sweep_task is not None:
            self._cancel_sweep_split()
            return
        self._cancel_tasks()
        self._scan_generation += 1
        self._load_generation += 1
        self._sweep_generation += 1
        self._state = self._state.cancel()
        self._raw_plot.clear_plot("読み込みをキャンセルしました")
        self._render_state()

    def _cancel_tasks(self) -> None:
        if self._scan_task is not None:
            self._scan_task.cancel()
            self._scan_task = None
        if self._load_task is not None:
            self._load_task.cancel()
            self._load_task = None
        if self._sweep_task is not None:
            self._sweep_task.cancel()
            self._sweep_task = None

    def _invalidate_sweep_task(self) -> None:
        if self._sweep_task is not None:
            self._sweep_task.cancel()
            self._sweep_task = None
        self._sweep_generation += 1

    def _cancel_sweep_split(self) -> None:
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
            preprocessed = self._preprocessing_panel.result
            if preprocessed is None or preprocessed.sweep_id != selected_sweep.sweep_id:
                self._apply_preprocessing(
                    selected_sweep,
                    self._preprocessing_panel.settings(),
                )
            elif self._sweep_iv_plot.preprocessed is not preprocessed:
                self._sweep_iv_plot.show_preprocessing(preprocessed)
        else:
            self._raw_plot.clear_sweep_highlight()
            self._sweep_iv_plot.clear_plot(self._state.sweep_message)
            self._preprocessing_panel.clear(self._state.sweep_message)
        self._render_actions()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._cancel_tasks()
        super().closeEvent(event)
