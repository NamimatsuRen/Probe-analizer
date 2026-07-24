from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from probe_app.application.state import LoadStatus
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
