from __future__ import annotations

from PySide6.QtCore import Qt

from probe_app.domain.models import (
    AnalysisStatus,
    SummaryMethod,
    SummaryMethodValue,
    SummaryRow,
    SummaryScope,
    SummaryScopeKind,
    SummarySnapshot,
    SweepDirection,
)
from probe_app.ui.widgets import SummaryWorkspace


def test_summary_workspace_shows_scope_denominator_and_all_status_counts(
    qtbot: object,
) -> None:
    workspace = SummaryWorkspace()
    qtbot.addWidget(workspace)  # type: ignore[attr-defined]
    snapshot = _snapshot()

    workspace.render_snapshot(
        snapshot,
        selected_sweep_id="shot-001/voltage:10:20",
    )

    assert workspace.row_count == 2
    assert "shot-001" in workspace.context_text
    assert "現在のRevisionのみ" in workspace.context_text
    assert "1 / 2 Sweep" in workspace.denominator_text
    assert "有効" in workspace.status_text(AnalysisStatus.VALID)
    assert workspace.status_text(AnalysisStatus.VALID).endswith("1")
    assert workspace.status_text(AnalysisStatus.STALE).endswith("1")
    assert "表示だけでは解析を再計算しません" in workspace.policy_text


def test_summary_workspace_selection_and_drill_down_share_sweep_id(
    qtbot: object,
) -> None:
    workspace = SummaryWorkspace()
    qtbot.addWidget(workspace)  # type: ignore[attr-defined]
    workspace.render_snapshot(_snapshot())

    with qtbot.waitSignal(workspace.sweep_selected) as selected:  # type: ignore[attr-defined]
        workspace._tree.setCurrentItem(workspace._tree.topLevelItem(1))  # noqa: SLF001

    assert selected.args == ["shot-001/voltage:20:30"]
    assert workspace.selected_sweep_id == "shot-001/voltage:20:30"

    with qtbot.waitSignal(workspace.open_analysis_requested) as opened:  # type: ignore[attr-defined]
        qtbot.mouseClick(  # type: ignore[attr-defined]
            workspace._open_analysis,  # noqa: SLF001
            Qt.MouseButton.LeftButton,
        )

    assert opened.args == ["shot-001/voltage:20:30"]


def _snapshot() -> SummarySnapshot:
    scope = SummaryScope(
        kind=SummaryScopeKind.CURRENT_SHOT,
        folder_key="/measurements",
        shot_ids=("shot-001",),
    )
    return SummarySnapshot(
        scope=scope,
        rows=(
            SummaryRow(
                number=1,
                sweep_id="shot-001/voltage:10:20",
                shot_id="shot-001",
                direction=SweepDirection.UP,
                start_ms=200.0,
                stop_ms=210.0,
                point_count=10,
                status=AnalysisStatus.VALID,
                current_revision=True,
                revision_key="a" * 64,
                methods=(
                    SummaryMethodValue(
                        method=SummaryMethod.FILTERED_LOG,
                        status=AnalysisStatus.VALID,
                        phi_v=14.2,
                        ti_ev=1.8,
                    ),
                ),
            ),
            SummaryRow(
                number=2,
                sweep_id="shot-001/voltage:20:30",
                shot_id="shot-001",
                direction=SweepDirection.DOWN,
                start_ms=210.0,
                stop_ms=220.0,
                point_count=10,
                status=AnalysisStatus.STALE,
                current_revision=False,
                revision_key="b" * 64,
                message="SG設定が変更されました",
            ),
        ),
    )

