from __future__ import annotations

import numpy as np

from probe_app.domain.models import (
    AnalysisInputRevision,
    AnalysisStage,
    AnalysisStatus,
    MethodOutcome,
    PreprocessingRevision,
    SignalAssignmentRevision,
    StageResult,
    Sweep,
    SweepAnalysisRecord,
    SweepDirection,
    SweepSplitRevision,
)
from probe_app.ui.widgets import AnalysisWorkspace


def test_analysis_workspace_distinguishes_empty_and_not_run_states(
    qtbot: object,
) -> None:
    workspace = AnalysisWorkspace()
    qtbot.addWidget(workspace)  # type: ignore[attr-defined]

    workspace.render_state(None, None, empty_message="Sweep分割を実行してください")

    assert "Sweep未選択" in workspace.context_text
    assert "Sweep分割を実行" in workspace.context_text
    assert "未作成" in workspace.revision_text
    assert "未実行" in workspace.stage_text(AnalysisStage.PREPROCESSING)
    assert "未実行" in workspace.stage_text(AnalysisStage.POTENTIAL)

    sweep = _sweep()
    workspace.render_state(sweep, None)

    assert sweep.sweep_id in workspace.context_text
    assert "上昇" in workspace.context_text
    assert "前処理は未実行" in workspace.revision_text
    assert "タブを切り替えただけでは計算しません" in workspace.impact_text


def test_analysis_workspace_shows_revision_stage_and_stale_reason(
    qtbot: object,
) -> None:
    workspace = AnalysisWorkspace()
    qtbot.addWidget(workspace)  # type: ignore[attr-defined]
    sweep = _sweep()
    revision = _revision(sweep.sweep_id)
    record = SweepAnalysisRecord.running(revision).with_stage_result(
        StageResult(
            stage=AnalysisStage.PREPROCESSING,
            status=AnalysisStatus.REVIEW,
            methods=(
                MethodOutcome(
                    method_id="savitzky_golay",
                    status=AnalysisStatus.REVIEW,
                    message="電圧刻みを確認してください",
                ),
            ),
            message="電圧刻みを確認してください",
        )
    )

    workspace.render_state(sweep, record)

    assert revision.cache_key[:10] in workspace.revision_text
    assert "要確認" in workspace.revision_text
    assert "要確認" in workspace.stage_text(AnalysisStage.PREPROCESSING)
    assert "未実行" in workspace.stage_text(AnalysisStage.SATURATION)

    stale = record.mark_stale_from(
        AnalysisStage.PREPROCESSING,
        "SG設定が変更されました",
    )
    workspace.render_state(sweep, stale)

    assert "再計算必要" in workspace.revision_text
    assert "再計算必要" in workspace.stage_text(AnalysisStage.PREPROCESSING)
    assert "SG設定が変更" in workspace.impact_text


def _sweep() -> Sweep:
    voltage_v = np.linspace(-2.0, 2.0, 9, dtype=np.float64)
    return Sweep(
        sweep_id="shot-001/voltage:200000:200009",
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        source_start_index=200_000,
        source_stop_index=200_009,
        direction=SweepDirection.UP,
        time_s=np.linspace(0.2, 0.200008, 9, dtype=np.float64),
        voltage_v=voltage_v,
        current_a=voltage_v**2,
    )


def _revision(sweep_id: str) -> AnalysisInputRevision:
    return AnalysisInputRevision(
        folder_key="/measurements/20211216",
        shot_id="shot-001",
        sweep_id=sweep_id,
        current=SignalAssignmentRevision(
            series_id="shot-001/current",
            scale=0.05,
            sign=-1.0,
            output_unit="A",
        ),
        sweep_voltage=SignalAssignmentRevision(
            series_id="shot-001/voltage",
            scale=100.0,
            sign=1.0,
            output_unit="V",
        ),
        split=SweepSplitRevision(
            points_per_cycle=20_000,
            sample_start=200_000,
            sample_stop=500_000,
            current_time_offset_s=0.0,
        ),
        preprocessing=PreprocessingRevision(window_length=501, polyorder=3),
        generation_id=1,
    )
