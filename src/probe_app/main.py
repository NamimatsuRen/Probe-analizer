from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import TracebackType

from PySide6.QtWidgets import QApplication, QMessageBox

from probe_app.ui.main_window import MainWindow


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
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Probe Analizer")
    app.setOrganizationName("NamimatsuRen")

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
