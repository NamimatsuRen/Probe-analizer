from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from probe_app.application.state.app_state import LoadStatus


class StatusPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._message = QLabel("フォルダを選択してください")
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(120)
        self._progress.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(self._message, 1)
        layout.addWidget(self._progress)

    def set_status(self, status: LoadStatus, message: str, *, details: str = "") -> None:
        self._message.setText(message)
        self._message.setToolTip(details)
        self._progress.setVisible(status is LoadStatus.LOADING)
