from __future__ import annotations

from dataclasses import replace

from probe_app.application.state import AnalysisResultStore
from probe_app.domain.models import (
    AnalysisInputRevision,
    AnalysisStage,
    AnalysisStatus,
    MethodOutcome,
    PreprocessingRevision,
    SignalAssignmentRevision,
    StageResult,
    SweepAnalysisRecord,
    SweepSplitRevision,
)


def test_revision_cache_key_is_stable_and_covers_analysis_inputs() -> None:
    revision = _revision()

    assert revision.cache_key == _revision().cache_key
    assert revision.cache_key != replace(
        revision,
        preprocessing=PreprocessingRevision(window_length=101, polyorder=3),
    ).cache_key
    assert revision.cache_key != replace(
        revision,
        split=replace(revision.split, current_time_offset_s=0.0005),
    ).cache_key
    assert revision.cache_key != replace(revision, generation_id=8).cache_key


def test_stage_can_retain_success_when_another_method_fails() -> None:
    stage = StageResult(
        stage=AnalysisStage.POTENTIAL,
        status=AnalysisStatus.REVIEW,
        methods=(
            MethodOutcome("derivative_peak", AnalysisStatus.VALID),
            MethodOutcome(
                "log_intersection",
                AnalysisStatus.ERROR,
                message="交点を求められません",
            ),
        ),
    )
    record = SweepAnalysisRecord.running(_revision()).with_stage_result(stage)

    assert stage.partial_success
    assert record.partial_success
    assert record.stage_result(AnalysisStage.POTENTIAL) == stage


def test_invalidation_only_marks_changed_stage_and_downstream_stale() -> None:
    record = SweepAnalysisRecord(
        revision=_revision(),
        status=AnalysisStatus.VALID,
        stages=(
            _stage(AnalysisStage.PREPROCESSING),
            _stage(AnalysisStage.POTENTIAL),
            _stage(AnalysisStage.SATURATION),
            _stage(AnalysisStage.TEMPERATURE),
            _stage(AnalysisStage.QUALITY),
        ),
    )

    stale = record.mark_stale_from(
        AnalysisStage.SATURATION,
        "電子飽和域のfit範囲が変更されました",
    )

    assert stale.status is AnalysisStatus.STALE
    assert stale.stage_result(AnalysisStage.PREPROCESSING).status is AnalysisStatus.VALID
    assert stale.stage_result(AnalysisStage.POTENTIAL).status is AnalysisStatus.VALID
    for stage in (
        AnalysisStage.SATURATION,
        AnalysisStage.TEMPERATURE,
        AnalysisStage.QUALITY,
    ):
        assert stale.stage_result(stage).status is AnalysisStatus.STALE


def test_exclusion_is_distinct_from_bad_and_can_be_restored() -> None:
    record = SweepAnalysisRecord(
        revision=_revision(),
        status=AnalysisStatus.BAD,
        stages=(_stage(AnalysisStage.PREPROCESSING, AnalysisStatus.BAD),),
    )

    excluded = record.exclude("放電由来の異常波形")

    assert excluded.status is AnalysisStatus.EXCLUDED
    assert excluded.exclusion_reason == "放電由来の異常波形"
    restored = excluded.restore()
    assert restored.status is AnalysisStatus.REVIEW
    assert restored.exclusion_reason == ""


def test_store_rejects_late_result_from_old_revision() -> None:
    old_revision = _revision(generation_id=3)
    current_revision = _revision(generation_id=4)
    late_record = SweepAnalysisRecord(
        revision=old_revision,
        status=AnalysisStatus.VALID,
    )

    store, accepted = AnalysisResultStore().put_if_current(
        late_record,
        current_revision,
    )

    assert not accepted
    assert store.records == ()


def test_store_only_exposes_usable_result_for_matching_revision() -> None:
    valid_revision = _revision(generation_id=5)
    stale_revision = _revision(generation_id=6)
    store = AnalysisResultStore().put(
        SweepAnalysisRecord(
            revision=valid_revision,
            status=AnalysisStatus.REVIEW,
        )
    )
    store = store.put(
        SweepAnalysisRecord(
            revision=stale_revision,
            status=AnalysisStatus.STALE,
        )
    )

    assert store.accepted_current(valid_revision) is not None
    assert store.accepted_current(stale_revision) is None
    assert store.latest_for_sweep("shot-a/voltage:200000:210000") is not None


def _stage(
    stage: AnalysisStage,
    status: AnalysisStatus = AnalysisStatus.VALID,
) -> StageResult:
    return StageResult(
        stage=stage,
        status=status,
        methods=(MethodOutcome(f"{stage.value}_method", status),),
    )


def _revision(*, generation_id: int = 7) -> AnalysisInputRevision:
    return AnalysisInputRevision(
        folder_key="/measurements/20211216",
        shot_id="shot-a",
        sweep_id="shot-a/voltage:200000:210000",
        current=SignalAssignmentRevision(
            series_id="shot-a/current",
            scale=0.05,
            sign=-1.0,
            output_unit="A",
        ),
        sweep_voltage=SignalAssignmentRevision(
            series_id="shot-a/voltage",
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
        preprocessing=PreprocessingRevision(
            window_length=501,
            polyorder=3,
        ),
        generation_id=generation_id,
    )
