from __future__ import annotations

import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt

from probe_app.domain.models import (
    AnalysisStatus,
    ProbePosition,
    ProbePositionUnit,
    ShotMetadata,
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
    assert workspace.average_row_count == 4
    assert workspace.ti_plot_point_count == 1
    assert workspace.phi_plot_point_count == 1
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


def test_summary_workspace_requires_reason_and_requests_exclusion(
    qtbot: object,
) -> None:
    workspace = SummaryWorkspace()
    qtbot.addWidget(workspace)  # type: ignore[attr-defined]
    workspace.render_snapshot(
        _snapshot(),
        selected_sweep_id="shot-001/voltage:10:20",
    )

    qtbot.mouseClick(  # type: ignore[attr-defined]
        workspace._exclude,  # noqa: SLF001
        Qt.MouseButton.LeftButton,
    )

    assert "除外理由を入力" in workspace.exclusion_feedback_text

    workspace._exclusion_reason.setText("放電由来の異常波形")  # noqa: SLF001
    with qtbot.waitSignal(workspace.exclusion_requested) as excluded:  # type: ignore[attr-defined]
        qtbot.mouseClick(  # type: ignore[attr-defined]
            workspace._exclude,  # noqa: SLF001
            Qt.MouseButton.LeftButton,
        )

    assert excluded.args == [
        "shot-001/voltage:10:20",
        "放電由来の異常波形",
    ]


def test_summary_workspace_requests_restore_for_excluded_current_result(
    qtbot: object,
) -> None:
    workspace = SummaryWorkspace()
    qtbot.addWidget(workspace)  # type: ignore[attr-defined]
    snapshot = _snapshot()
    excluded_row = replace(
        snapshot.rows[0],
        status=AnalysisStatus.EXCLUDED,
        exclusion_reason="ノイズ混入",
    )
    workspace.render_snapshot(
        replace(snapshot, rows=(excluded_row, snapshot.rows[1])),
        selected_sweep_id=excluded_row.sweep_id,
    )

    assert "ノイズ混入" in workspace.exclusion_feedback_text
    with qtbot.waitSignal(workspace.restore_requested) as restored:  # type: ignore[attr-defined]
        qtbot.mouseClick(  # type: ignore[attr-defined]
            workspace._restore,  # noqa: SLF001
            Qt.MouseButton.LeftButton,
        )

    assert restored.args == [excluded_row.sweep_id]


def test_summary_workspace_emits_scope_and_explicit_metadata_changes(
    qtbot: object,
) -> None:
    workspace = SummaryWorkspace()
    qtbot.addWidget(workspace)  # type: ignore[attr-defined]
    metadata = ShotMetadata(
        folder_key="/measurements",
        shot_id="shot-001",
        position=ProbePosition(2.5, ProbePositionUnit.MILLIMETER),
    )
    workspace.render_snapshot(_snapshot(), shot_metadata=(metadata,))

    with qtbot.waitSignal(workspace.scope_changed) as scope_changed:  # type: ignore[attr-defined]
        workspace._scope.setCurrentIndex(1)  # noqa: SLF001

    assert scope_changed.args == [SummaryScopeKind.LOADED_SHOTS]

    workspace._scope.setCurrentIndex(0)  # noqa: SLF001
    workspace._metadata_editor._position.setText("3.25")  # noqa: SLF001
    with qtbot.waitSignal(workspace.shot_metadata_changed) as changed:  # type: ignore[attr-defined]
        qtbot.mouseClick(  # type: ignore[attr-defined]
            workspace._metadata_editor._save,  # noqa: SLF001
            Qt.MouseButton.LeftButton,
        )

    saved = changed.args[0]
    assert isinstance(saved, ShotMetadata)
    assert saved.position is not None
    assert saved.position.value == 3.25


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
