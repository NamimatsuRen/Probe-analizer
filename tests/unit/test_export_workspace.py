from __future__ import annotations

from probe_app.domain.models import (
    AnalysisStatus,
    ExportCandidate,
    ExportCandidateSnapshot,
    SummaryMethod,
)
from probe_app.ui.widgets import ExportWorkspace


def test_export_workspace_is_read_only_and_warns_about_non_default_rows(
    qtbot: object,
) -> None:
    workspace = ExportWorkspace()
    qtbot.addWidget(workspace)  # type: ignore[attr-defined]
    snapshot = ExportCandidateSnapshot(
        folder_key="/measurements",
        shot_ids=("shot-001",),
        candidates=(
            ExportCandidate(
                number=1,
                sweep_id="shot-001/v:1:2",
                shot_id="shot-001",
                status=AnalysisStatus.VALID,
                current_revision=True,
                available_methods=(SummaryMethod.FILTERED_LOG,),
                selected_by_default=True,
                reason="現在のRevisionと一致する有効な解析結果",
            ),
            ExportCandidate(
                number=2,
                sweep_id="shot-001/v:2:3",
                shot_id="shot-001",
                status=AnalysisStatus.STALE,
                current_revision=False,
                available_methods=(),
                selected_by_default=False,
                reason="SG設定が変更されました",
            ),
        ),
    )

    workspace.render_candidates(snapshot)

    assert workspace.candidate_count == 2
    assert workspace.checked_candidate_count == 1
    assert "shot-001" in workspace.scope_text
    assert "初期選択 1 / 2" in workspace.count_text
    assert "注意 1" in workspace.count_text
    assert "解析値を変更・再計算しません" in workspace.policy_text
    assert not workspace.renderer_constructed


def test_export_workspace_distinguishes_missing_scope(qtbot: object) -> None:
    workspace = ExportWorkspace()
    qtbot.addWidget(workspace)  # type: ignore[attr-defined]

    workspace.render_candidates(None, empty_message="Sweep分割が必要です")

    assert workspace.candidate_count == 0
    assert "shot未選択" in workspace.scope_text
    assert "Sweep分割が必要" in workspace.scope_text
