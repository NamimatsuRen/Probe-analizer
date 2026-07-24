from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings

from probe_app.application.state import LoadStatus
from probe_app.domain.errors import RoleAssignmentStoreError
from probe_app.domain.models.series_role import SeriesRole, SeriesRoleAssignments
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


def test_role_assignments_are_saved_and_restored(qtbot: object, tmp_path: Path) -> None:
    measurement_folder = tmp_path / "measurements"
    write_panta_series(measurement_folder / "shot-001", "channel-i")
    write_panta_series(measurement_folder / "shot-001", "channel-v")
    settings_path = tmp_path / "settings.ini"

    first = MainWindow(
        settings=QSettings(str(settings_path), QSettings.Format.IniFormat)
    )
    qtbot.addWidget(first)  # type: ignore[attr-defined]
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
