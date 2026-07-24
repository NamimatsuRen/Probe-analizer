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
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from probe_app.application.state.app_state import AppState, LoadStatus
from probe_app.domain.models.catalog import FolderCatalog
from probe_app.domain.models.raw_series import RawSeries, RawSeriesDescriptor
from probe_app.ui.widgets import DataBrowser, MetadataPanel, RawPlot, StatusPanel
from probe_app.ui.workers import FolderScanTask, SeriesLoadTask

LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Probe Analizer — Rawデータブラウザ")
        self.resize(1280, 760)

        self._state = AppState()
        self._settings = QSettings("NamimatsuRen", "ProbeAnalizer")
        self._thread_pool = QThreadPool.globalInstance()
        self._scan_generation = 0
        self._load_generation = 0
        self._scan_task: FolderScanTask | None = None
        self._load_task: SeriesLoadTask | None = None

        self._data_browser = DataBrowser()
        self._raw_plot = RawPlot()
        self._metadata = MetadataPanel()
        self._status = StatusPanel()
        self._build_layout()
        self._build_toolbar()
        self._data_browser.series_selected.connect(self._load_series)
        self._render_state()

    def _build_layout(self) -> None:
        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(self._raw_plot)
        right.addWidget(self._metadata)
        right.setStretchFactor(0, 5)
        right.setStretchFactor(1, 1)

        content = QSplitter(Qt.Orientation.Horizontal)
        content.addWidget(self._data_browser)
        content.addWidget(right)
        content.setStretchFactor(0, 1)
        content.setStretchFactor(1, 4)
        content.setSizes([300, 980])

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
        generation = self._scan_generation
        self._state = self._state.start_loading(folder)
        self._settings.setValue("recentFolder", str(folder))
        self._data_browser.clear_catalog(str(folder))
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
        if self._state.catalog is not None:
            self._state = self._state.select_series(descriptor_object.series_id)

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
        self._cancel_tasks()
        self._scan_generation += 1
        self._load_generation += 1
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

    def _render_state(self) -> None:
        details = ""
        if self._state.catalog is not None and self._state.catalog.problems:
            details = "\n".join(
                f"{problem.path.name}: {problem.message}"
                for problem in self._state.catalog.problems
            )
        self._status.set_status(self._state.status, self._state.message, details=details)
        self._render_actions()

    def _render_actions(self) -> None:
        busy = self._scan_task is not None or self._load_task is not None
        self._reload_action.setEnabled(self._state.folder is not None and not busy)
        self._cancel_action.setEnabled(busy)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._cancel_tasks()
        super().closeEvent(event)
