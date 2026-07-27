from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from probe_app.domain.models.catalog import FolderCatalog
from probe_app.domain.models.series_role import SeriesRole, SeriesRoleAssignments
from probe_app.domain.services import AssignmentApplyScope
from probe_app.infrastructure.readers.folder_scanner import FolderScanner
from probe_app.ui.widgets.role_assignment_panel import RoleAssignmentPanel
from tests.conftest import write_panta_series


def _catalog(tmp_path: Path) -> FolderCatalog:
    write_panta_series(tmp_path / "shot-a", "channel-i")
    write_panta_series(tmp_path / "shot-a", "channel-v")
    write_panta_series(tmp_path / "shot-b", "other")
    return FolderScanner().scan(tmp_path)


def test_lists_only_series_from_the_active_shot(qtbot: object, tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    panel = RoleAssignmentPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]

    panel.set_context(
        "shot-a",
        catalog.series_for_shot("shot-a"),
        SeriesRoleAssignments(),
    )

    panel.select_series(SeriesRole.CURRENT, "shot-a/channel-i")
    panel.select_series(SeriesRole.SWEEP_VOLTAGE, "shot-a/channel-v")
    assert panel.assignments().is_complete
    with pytest.raises(ValueError, match="not available"):
        panel.select_series(SeriesRole.CURRENT, "shot-b/other")


def test_same_series_cannot_fill_both_roles(qtbot: object, tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    panel = RoleAssignmentPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_context(
        "shot-a",
        catalog.series_for_shot("shot-a"),
        SeriesRoleAssignments(),
    )

    panel.select_series(SeriesRole.CURRENT, "shot-a/channel-i")
    panel.select_series(SeriesRole.SWEEP_VOLTAGE, "shot-a/channel-i")

    assert panel.series_id_for_role(SeriesRole.CURRENT) is None
    assert panel.series_id_for_role(SeriesRole.SWEEP_VOLTAGE) == "shot-a/channel-i"


def test_complete_assignments_can_request_a_selected_bulk_scope(
    qtbot: object,
    tmp_path: Path,
) -> None:
    catalog = _catalog(tmp_path)
    panel = RoleAssignmentPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_context(
        "shot-a",
        catalog.series_for_shot("shot-a"),
        SeriesRoleAssignments(),
    )
    assert not panel.bulk_apply_enabled

    panel.select_series(SeriesRole.CURRENT, "shot-a/channel-i")
    panel.select_series(SeriesRole.SWEEP_VOLTAGE, "shot-a/channel-v")
    panel.set_apply_scope(AssignmentApplyScope.REMAINING)

    assert panel.bulk_apply_enabled
    with qtbot.waitSignal(  # type: ignore[attr-defined]
        panel.bulk_apply_requested,
        timeout=1_000,
    ) as blocker:
        panel._apply_button.click()  # noqa: SLF001

    assert blocker.args == [AssignmentApplyScope.REMAINING]
