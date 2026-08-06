from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from probe_app.domain.models.catalog import FolderCatalog
from probe_app.domain.models.raw_series import RawSeriesDescriptor

SERIES_ID_ROLE = int(Qt.ItemDataRole.UserRole)


class DataBrowser(QWidget):
    series_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._descriptors: dict[str, RawSeriesDescriptor] = {}

        self._guidance = QLabel("はじめに、上部の青い「フォルダを開く」を押してください。")
        self._guidance.setObjectName("dataBrowserGuidance")
        self._guidance.setWordWrap(True)
        self._guidance.setStyleSheet(
            "background: #eef4ff; color: #173b6c; padding: 7px;"
            " border: 1px solid #b7cdf5; border-radius: 4px; font-weight: 600;"
        )

        self._folder_label = QLabel("フォルダ未選択")
        self._folder_label.setWordWrap(True)
        self._folder_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._tree = QTreeWidget()
        self._tree.setObjectName("dataSeriesTree")
        self._tree.setHeaderLabels(["測定データ", "点数", "単位"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.itemSelectionChanged.connect(self._emit_selection)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QLabel("データ選択"))
        layout.addWidget(self._guidance)
        layout.addWidget(self._folder_label)
        layout.addWidget(self._tree, 1)

    def clear_catalog(self, folder_text: str = "フォルダ未選択") -> None:
        self._descriptors.clear()
        self._tree.clear()
        self._folder_label.setText(folder_text)
        self._guidance.setText(
            "はじめに、上部の青い「フォルダを開く」を押してください。"
            if folder_text == "フォルダ未選択"
            else "フォルダを読み込んでいます。完了までそのままお待ちください。"
        )

    def set_catalog(
        self,
        catalog: FolderCatalog,
        *,
        selected_series_id: str | None = None,
    ) -> RawSeriesDescriptor | None:
        self.clear_catalog(str(catalog.root))
        self._guidance.setText(
            "shot名の▶を開いて系列を選び、役割設定とI–Vを確認してください。"
            "shotは見通しを良くするため初期状態では閉じています。"
        )
        self._descriptors = {item.series_id: item for item in catalog.series}

        first_item: QTreeWidgetItem | None = None
        selected_item: QTreeWidgetItem | None = None
        for shot_id in catalog.shots:
            shot_item = QTreeWidgetItem([shot_id])
            shot_item.setFlags(shot_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._tree.addTopLevelItem(shot_item)
            for descriptor in catalog.series_for_shot(shot_id):
                series_item = QTreeWidgetItem(
                    [
                        descriptor.display_name,
                        f"{descriptor.sample_count:,}",
                        descriptor.value_unit or "—",
                    ]
                )
                series_item.setData(0, SERIES_ID_ROLE, descriptor.series_id)
                series_item.setToolTip(0, descriptor.series_id)
                shot_item.addChild(series_item)
                if first_item is None:
                    first_item = series_item
                if descriptor.series_id == selected_series_id:
                    selected_item = series_item
            shot_item.setExpanded(False)

        self._tree.resizeColumnToContents(0)
        if first_item is None:
            return None
        target_item = selected_item or first_item
        self._tree.setCurrentItem(target_item)
        return self._descriptors.get(target_item.data(0, SERIES_ID_ROLE))

    def _emit_selection(self) -> None:
        item: QTreeWidgetItem | None = self._tree.currentItem()
        if item is None:
            return
        series_id = item.data(0, SERIES_ID_ROLE)
        descriptor = self._descriptors.get(series_id)
        if descriptor is not None:
            self.series_selected.emit(descriptor)
