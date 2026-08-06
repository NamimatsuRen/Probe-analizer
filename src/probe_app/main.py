from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import TracebackType

from PySide6.QtWidgets import QApplication, QMessageBox

from probe_app.ui.main_window import MainWindow


def _interaction_stylesheet() -> str:
    """Make actionable controls visibly hoverable and pressable on every OS."""

    return """
        QPushButton, QToolButton {
            border: 1px solid #98a2b3;
            border-radius: 5px;
            padding: 5px 9px;
            background: #f8fafc;
            color: #173b6c;
        }
        QPushButton:hover, QToolButton:hover {
            background: #dbeafe;
            border-color: #2563eb;
            color: #173b6c;
        }
        QPushButton:pressed, QToolButton:pressed {
            background: #93c5fd;
            border-color: #1d4ed8;
            color: #102a56;
        }
        QPushButton:disabled, QToolButton:disabled {
            background: #eaecf0;
            border-color: #d0d5dd;
            color: #98a2b3;
        }
        QToolButton#primaryOpenFolderButton,
        QPushButton#runSweepSplit,
        QPushButton#runPreprocessing,
        QPushButton#runLevel4To6Analysis,
        QPushButton#exportPreviewButton,
        QPushButton#exportRenderButton {
            background: #2563eb;
            border-color: #1d4ed8;
            color: white;
            font-weight: 700;
        }
        QToolButton#primaryOpenFolderButton:hover,
        QPushButton#runSweepSplit:hover,
        QPushButton#runPreprocessing:hover,
        QPushButton#runLevel4To6Analysis:hover,
        QPushButton#exportPreviewButton:hover,
        QPushButton#exportRenderButton:hover {
            background: #1d4ed8;
            border-color: #1e40af;
            color: white;
        }
        QToolButton#primaryOpenFolderButton:pressed,
        QPushButton#runSweepSplit:pressed,
        QPushButton#runPreprocessing:pressed,
        QPushButton#runLevel4To6Analysis:pressed,
        QPushButton#exportPreviewButton:pressed,
        QPushButton#exportRenderButton:pressed {
            background: #1e3a8a;
            border-color: #172554;
            color: white;
        }
        QToolButton#primaryOpenFolderButton:disabled,
        QPushButton#runSweepSplit:disabled,
        QPushButton#runPreprocessing:disabled,
        QPushButton#runLevel4To6Analysis:disabled,
        QPushButton#exportPreviewButton:disabled,
        QPushButton#exportRenderButton:disabled {
            background: #eaecf0;
            border-color: #d0d5dd;
            color: #98a2b3;
        }
        QTreeWidget#dataSeriesTree::item:selected {
            background: #e4e7ec;
            color: #101828;
        }
        QTreeWidget#dataSeriesTree::item:hover {
            background: #dbeafe;
            color: #173b6c;
        }
        QTreeWidget#dataSeriesTree::item:selected:hover {
            background: #bfdbfe;
            color: #102a56;
        }
    """


def _configure_logging() -> Path:
    log_dir = Path.home() / ".probe-analizer" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "probe-analizer.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return log_path


def main() -> int:
    log_path = _configure_logging()
    existing_app = QApplication.instance()
    app = existing_app if isinstance(existing_app, QApplication) else QApplication(sys.argv)
    app.setApplicationName("Probe Analizer")
    app.setOrganizationName("NamimatsuRen")
    app.setStyleSheet(_interaction_stylesheet())

    def handle_exception(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback_object: TracebackType | None,
    ) -> None:
        logging.getLogger(__name__).exception(
            "Unhandled exception",
            exc_info=(exception_type, exception, traceback_object),
        )
        QMessageBox.critical(
            None,
            "予期しないエラー",
            f"アプリで問題が発生しました。\nログ: {log_path}",
        )

    sys.excepthook = handle_exception
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
