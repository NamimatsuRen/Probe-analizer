from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from probe_app.domain.models.shot_metadata import (
    ProbePosition,
    ProbePositionUnit,
    ShotMetadata,
)


class ShotMetadataEditor(QWidget):
    """Small editor for explicit shot metadata; no file-name inference is used."""

    metadata_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("shotMetadataEditor")
        self._items: dict[str, ShotMetadata] = {}

        self._shot = QComboBox()
        self._shot.setObjectName("shotMetadataShot")
        self._shot.currentTextChanged.connect(self._shot_changed)

        self._position = QLineEdit()
        self._position.setObjectName("shotMetadataPosition")
        self._position.setPlaceholderText("未設定")

        self._unit = QComboBox()
        self._unit.setObjectName("shotMetadataUnit")
        for unit in ProbePositionUnit:
            self._unit.addItem(unit.value, unit)

        self._label = QLineEdit()
        self._label.setObjectName("shotMetadataLabel")
        self._label.setPlaceholderText("例: r/a=0.35（任意）")

        self._save = QPushButton("位置を保存")
        self._save.setObjectName("saveShotMetadata")
        self._save.clicked.connect(self._save_requested)
        self._clear = QPushButton("位置を未設定に戻す")
        self._clear.setObjectName("clearShotMetadata")
        self._clear.clicked.connect(self._clear_requested)

        self._feedback = QLabel()
        self._feedback.setObjectName("shotMetadataFeedback")
        self._feedback.setWordWrap(True)

        position_row = QHBoxLayout()
        position_row.addWidget(self._position, 2)
        position_row.addWidget(self._unit, 1)

        actions = QHBoxLayout()
        actions.addWidget(self._save)
        actions.addWidget(self._clear)

        form = QFormLayout(self)
        form.setContentsMargins(6, 4, 6, 4)
        form.addRow("shot", self._shot)
        form.addRow("プローブ位置", position_row)
        form.addRow("表示ラベル", self._label)
        form.addRow(actions)
        form.addRow(self._feedback)

    @property
    def feedback_text(self) -> str:
        return self._feedback.text()

    def render_metadata(
        self,
        items: tuple[ShotMetadata, ...],
        *,
        selected_shot_id: str | None = None,
    ) -> None:
        self._items = {item.shot_id: item for item in items}
        self._shot.blockSignals(True)
        self._shot.clear()
        self._shot.addItems(tuple(self._items))
        if selected_shot_id in self._items:
            self._shot.setCurrentText(selected_shot_id)
        self._shot.blockSignals(False)
        self._shot_changed(self._shot.currentText())
        enabled = bool(items)
        for widget in (
            self._shot,
            self._position,
            self._unit,
            self._label,
            self._save,
            self._clear,
        ):
            widget.setEnabled(enabled)

    def show_error(self, message: str) -> None:
        self._feedback.setText(message)
        self._feedback.setStyleSheet("color: #b42318;")

    def show_saved(self, message: str = "位置metadataを保存しました") -> None:
        self._feedback.setText(message)
        self._feedback.setStyleSheet("color: #067647;")

    def _shot_changed(self, shot_id: str) -> None:
        metadata = self._items.get(shot_id)
        position = metadata.position if metadata is not None else None
        self._position.setText("" if position is None else f"{position.value:g}")
        self._label.setText("" if position is None else position.label)
        if position is not None:
            index = self._unit.findData(position.unit)
            if index >= 0:
                self._unit.setCurrentIndex(index)
        self._feedback.clear()

    def _save_requested(self) -> None:
        shot_id = self._shot.currentText()
        current = self._items.get(shot_id)
        if current is None:
            return
        try:
            value = float(self._position.text().strip())
            raw_unit = self._unit.currentData()
            try:
                unit = ProbePositionUnit(raw_unit)
            except (TypeError, ValueError):
                raise ValueError("位置の単位を選択してください") from None
            position = ProbePosition(
                value=value,
                unit=unit,
                label=self._label.text().strip(),
            )
        except ValueError as error:
            self.show_error(f"位置を保存できません: {error}")
            return
        metadata = ShotMetadata(
            folder_key=current.folder_key,
            shot_id=current.shot_id,
            position=position,
            note=current.note,
        )
        self.metadata_changed.emit(metadata)

    def _clear_requested(self) -> None:
        shot_id = self._shot.currentText()
        current = self._items.get(shot_id)
        if current is None:
            return
        self.metadata_changed.emit(
            ShotMetadata(
                folder_key=current.folder_key,
                shot_id=current.shot_id,
                note=current.note,
            )
        )
