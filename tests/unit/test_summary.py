from __future__ import annotations

from dataclasses import replace

import numpy as np

from probe_app.application.queries import build_summary_snapshot
from probe_app.application.state import AnalysisResultStore
from probe_app.domain.models import (
    AnalysisInputRevision,
    AnalysisStage,
    AnalysisStatus,
    MethodOutcome,
    PreprocessingRevision,
    SignalAssignmentRevision,
    StageResult,
    SummaryMethod,
    SummaryScope,
    SummaryScopeKind,
    Sweep,
    SweepAnalysisRecord,
    SweepDirection,
    SweepSplitRevision,
)


def test_summary_keeps_not_run_old_revision_and_current_results_visible() -> None:
    sweeps = tuple(_sweep(index) for index in range(4))
    revisions = {
        sweep.sweep_id: _revision(sweep.sweep_id, generation_id=5)
        for sweep in sweeps
    }

    preprocessing_only = SweepAnalysisRecord.running(
        revisions[sweeps[0].sweep_id]
    ).with_stage_result(
        StageResult(
            stage=AnalysisStage.PREPROCESSING,
            status=AnalysisStatus.VALID,
            methods=(MethodOutcome("savitzky_golay", AnalysisStatus.VALID),),
        )
    )
    completed = SweepAnalysisRecord.running(
        revisions[sweeps[1].sweep_id]
    ).with_stage_result(
        StageResult(
            stage=AnalysisStage.POTENTIAL,
            status=AnalysisStatus.VALID,
            methods=(
                MethodOutcome(
                    SummaryMethod.FILTERED_LOG,
                    AnalysisStatus.VALID,
                    metrics=(("phi_v", 14.2),),
                ),
                MethodOutcome(
                    SummaryMethod.RAW_DERIVATIVE,
                    AnalysisStatus.REVIEW,
                    metrics=(("phi_v", 14.5),),
                ),
            ),
        )
    ).with_stage_result(
        StageResult(
            stage=AnalysisStage.TEMPERATURE,
            status=AnalysisStatus.REVIEW,
            methods=(
                MethodOutcome(
                    SummaryMethod.FILTERED_LOG,
                    AnalysisStatus.VALID,
                    metrics=(("k_per_v", 0.05), ("ti_ev", 1.8)),
                ),
                MethodOutcome(
                    SummaryMethod.RAW_DERIVATIVE,
                    AnalysisStatus.REVIEW,
                    metrics=(("k_per_v", 0.05), ("ti_ev", 2.1)),
                ),
            ),
            message="2方式の差を確認してください",
        )
    )
    old_revision = replace(
        revisions[sweeps[2].sweep_id],
        generation_id=4,
    )
    old_record = SweepAnalysisRecord(
        revision=old_revision,
        status=AnalysisStatus.VALID,
        message="旧設定の結果",
    )
    excluded = SweepAnalysisRecord(
        revision=revisions[sweeps[3].sweep_id],
        status=AnalysisStatus.REVIEW,
    ).exclude("放電由来の異常波形")

    store = AnalysisResultStore()
    for record in (preprocessing_only, completed, old_record, excluded):
        store = store.put(record)

    snapshot = build_summary_snapshot(
        SummaryScope(
            kind=SummaryScopeKind.CURRENT_SHOT,
            folder_key="/measurements",
            shot_ids=("shot-001",),
        ),
        sweeps,
        store,
        current_revisions=revisions,
    )

    assert len(snapshot.rows) == 4
    assert snapshot.rows[0].status is AnalysisStatus.NOT_RUN
    assert "preprocessing" in snapshot.rows[0].message
    assert snapshot.rows[1].status is AnalysisStatus.REVIEW
    assert snapshot.rows[1].ti_value_count == 2
    assert snapshot.rows[1].phi_value_count == 2
    assert snapshot.rows[2].status is AnalysisStatus.STALE
    assert not snapshot.rows[2].current_revision
    assert snapshot.rows[3].status is AnalysisStatus.EXCLUDED
    assert snapshot.rows[3].exclusion_reason == "放電由来の異常波形"
    assert snapshot.aggregate_row_count == 1
    assert dict(snapshot.status_counts)[AnalysisStatus.NOT_RUN] == 1
    assert dict(snapshot.status_counts)[AnalysisStatus.STALE] == 1
    assert dict(snapshot.status_counts)[AnalysisStatus.EXCLUDED] == 1


def test_summary_query_does_not_mutate_result_store() -> None:
    sweep = _sweep(0)
    revision = _revision(sweep.sweep_id, generation_id=2)
    store = AnalysisResultStore().put(
        SweepAnalysisRecord(revision=revision, status=AnalysisStatus.STALE)
    )

    before = store.records
    build_summary_snapshot(
        SummaryScope(
            kind=SummaryScopeKind.CURRENT_SHOT,
            folder_key="/measurements",
            shot_ids=("shot-001",),
        ),
        (sweep,),
        store,
        current_revisions={sweep.sweep_id: revision},
    )

    assert store.records is before


def _sweep(index: int) -> Sweep:
    start = 200_000 + index * 10
    stop = start + 10
    voltage = np.linspace(-50.0, 50.0, 10, dtype=np.float64)
    return Sweep(
        sweep_id=f"shot-001/voltage:{start}:{stop}",
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        source_start_index=start,
        source_stop_index=stop,
        direction=(
            SweepDirection.UP if index % 2 == 0 else SweepDirection.DOWN
        ),
        time_s=np.linspace(
            0.2 + index * 0.01,
            0.2 + index * 0.01 + 9e-6,
            10,
            dtype=np.float64,
        ),
        voltage_v=voltage,
        current_a=voltage * 1e-6,
    )


def _revision(sweep_id: str, *, generation_id: int) -> AnalysisInputRevision:
    return AnalysisInputRevision(
        folder_key="/measurements",
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
            points_per_cycle=20,
            sample_start=200_000,
            sample_stop=500_000,
            current_time_offset_s=0.0,
        ),
        preprocessing=PreprocessingRevision(window_length=9, polyorder=3),
        fit_settings=(("k_source", "shot中央値"),),
        generation_id=generation_id,
    )

