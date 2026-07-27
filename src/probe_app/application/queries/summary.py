from __future__ import annotations

from collections.abc import Mapping

from probe_app.application.state.analysis_result_store import AnalysisResultStore
from probe_app.domain.models.analysis_result import (
    AnalysisInputRevision,
    AnalysisStage,
    AnalysisStatus,
    MethodOutcome,
    SweepAnalysisRecord,
)
from probe_app.domain.models.summary import (
    SUMMARY_METHOD_ORDER,
    SummaryMethod,
    SummaryMethodValue,
    SummaryRow,
    SummaryScope,
    SummarySnapshot,
)
from probe_app.domain.models.sweep import Sweep


def build_summary_snapshot(
    scope: SummaryScope,
    sweeps: tuple[Sweep, ...],
    store: AnalysisResultStore,
    *,
    current_revisions: Mapping[str, AnalysisInputRevision] | None = None,
) -> SummarySnapshot:
    """Project records for display without running or mutating analysis."""

    revision_map = current_revisions or {}
    rows = tuple(
        _build_row(
            number,
            sweep,
            store,
            expected_revision=revision_map.get(sweep.sweep_id),
            current_revision_only=scope.current_revision_only,
        )
        for number, sweep in enumerate(sweeps, start=1)
        if _shot_id_for_sweep(sweep) in scope.shot_ids
    )
    return SummarySnapshot(scope=scope, rows=rows)


def _build_row(
    number: int,
    sweep: Sweep,
    store: AnalysisResultStore,
    *,
    expected_revision: AnalysisInputRevision | None,
    current_revision_only: bool,
) -> SummaryRow:
    latest = store.latest_for_sweep(sweep.sweep_id)
    if current_revision_only:
        record = (
            store.get(expected_revision)
            if expected_revision is not None
            else None
        )
        current_revision = (
            record is not None and expected_revision is not None
        )
    else:
        record = latest
        current_revision = record is not None

    if record is None and latest is not None:
        status = AnalysisStatus.STALE
        message = latest.message or "現在の設定とは異なるRevisionの結果があります"
        revision_key = latest.revision.cache_key
        exclusion_reason = latest.exclusion_reason
        methods = _method_values(latest)
    elif record is None:
        status = AnalysisStatus.NOT_RUN
        message = "Phi・T_i解析は未実行です"
        revision_key = ""
        exclusion_reason = ""
        methods = _empty_method_values()
    else:
        status, message = _summary_status(record)
        revision_key = record.revision.cache_key
        exclusion_reason = record.exclusion_reason
        methods = _method_values(record)

    return SummaryRow(
        number=number,
        sweep_id=sweep.sweep_id,
        shot_id=_shot_id_for_sweep(sweep),
        direction=sweep.direction,
        start_ms=float(sweep.time_s[0]) * 1_000.0,
        stop_ms=float(sweep.time_s[-1]) * 1_000.0,
        point_count=sweep.point_count,
        status=status,
        current_revision=current_revision,
        revision_key=revision_key,
        message=message,
        exclusion_reason=exclusion_reason,
        methods=methods,
    )


def _summary_status(
    record: SweepAnalysisRecord,
) -> tuple[AnalysisStatus, str]:
    if record.status in (
        AnalysisStatus.RUNNING,
        AnalysisStatus.BAD,
        AnalysisStatus.ERROR,
        AnalysisStatus.STALE,
        AnalysisStatus.EXCLUDED,
    ):
        return record.status, record.message

    quality = record.stage_result(AnalysisStage.QUALITY)
    if quality is not None:
        return quality.status, quality.message or record.message
    temperature = record.stage_result(AnalysisStage.TEMPERATURE)
    if temperature is not None:
        return temperature.status, temperature.message or record.message

    completed_names = "、".join(stage.stage.value for stage in record.stages)
    suffix = f"（完了: {completed_names}）" if completed_names else ""
    return AnalysisStatus.NOT_RUN, f"Phi・T_i解析は未実行です{suffix}"


def _method_values(
    record: SweepAnalysisRecord,
) -> tuple[SummaryMethodValue, ...]:
    outcomes: dict[SummaryMethod, list[MethodOutcome]] = {
        method: [] for method in SUMMARY_METHOD_ORDER
    }
    for stage in record.stages:
        for outcome in stage.methods:
            try:
                method = SummaryMethod(outcome.method_id)
            except ValueError:
                continue
            outcomes[method].append(outcome)

    fit_settings = dict(record.revision.fit_settings)
    return tuple(
        _merge_method_values(
            method,
            outcomes[method],
            k_source=fit_settings.get("k_source", ""),
        )
        for method in SUMMARY_METHOD_ORDER
    )


def _merge_method_values(
    method: SummaryMethod,
    outcomes: list[MethodOutcome],
    *,
    k_source: str,
) -> SummaryMethodValue:
    if not outcomes:
        return SummaryMethodValue(
            method=method,
            status=AnalysisStatus.NOT_RUN,
            k_source=k_source,
        )
    metrics: dict[str, float] = {}
    for outcome in outcomes:
        metrics.update(outcome.metrics)
    final = outcomes[-1]
    return SummaryMethodValue(
        method=method,
        status=final.status,
        phi_v=metrics.get("phi_v"),
        ti_ev=metrics.get("ti_ev"),
        k_per_v=metrics.get("k_per_v"),
        k_source=k_source,
        message=final.message,
    )


def _empty_method_values() -> tuple[SummaryMethodValue, ...]:
    return tuple(
        SummaryMethodValue(method=method, status=AnalysisStatus.NOT_RUN)
        for method in SUMMARY_METHOD_ORDER
    )


def _shot_id_for_sweep(sweep: Sweep) -> str:
    current_shot = sweep.current_series_id.split("/", maxsplit=1)[0]
    voltage_shot = sweep.voltage_series_id.split("/", maxsplit=1)[0]
    return current_shot if current_shot == voltage_shot else current_shot
