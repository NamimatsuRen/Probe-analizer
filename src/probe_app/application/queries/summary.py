from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping

from probe_app.application.state.analysis_result_store import AnalysisResultStore
from probe_app.domain.models.analysis_catalog import AnalysisCatalog, ShotAnalysisSnapshot
from probe_app.domain.models.analysis_result import (
    AnalysisInputRevision,
    AnalysisStage,
    AnalysisStatus,
    MethodOutcome,
    SweepAnalysisRecord,
)
from probe_app.domain.models.summary import (
    SUMMARY_METHOD_ORDER,
    SummaryAggregatePoint,
    SummaryAggregateSnapshot,
    SummaryMethod,
    SummaryMethodValue,
    SummaryMetric,
    SummaryMetricStatistics,
    SummaryRow,
    SummaryScope,
    SummaryScopeKind,
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


def build_catalog_summary_snapshot(
    folder_key: str,
    catalog: AnalysisCatalog,
    kind: SummaryScopeKind,
) -> SummaryAggregateSnapshot:
    """Aggregate lightweight shot snapshots without loading waveform arrays."""

    if kind is SummaryScopeKind.CURRENT_SHOT:
        raise ValueError("catalog summary requires loaded-shots or position scope")
    shots = catalog.for_folder(folder_key)
    if not shots:
        raise ValueError("the selected folder has no captured shot results")
    if kind is SummaryScopeKind.LOADED_SHOTS:
        return _loaded_shot_aggregates(folder_key, shots)
    return _position_aggregates(folder_key, shots)


def _loaded_shot_aggregates(
    folder_key: str,
    shots: tuple[ShotAnalysisSnapshot, ...],
) -> SummaryAggregateSnapshot:
    points: list[SummaryAggregatePoint] = []
    missing: list[tuple[str, str]] = []
    for index, shot in enumerate(shots, start=1):
        shot_points = _shot_metric_points(shot, x_value=float(index), label=shot.shot_id)
        if shot_points:
            points.extend(shot_points)
        else:
            missing.append((shot.shot_id, "集計可能なcurrent revision結果がありません"))
    return SummaryAggregateSnapshot(
        kind=SummaryScopeKind.LOADED_SHOTS,
        folder_key=folder_key,
        shot_ids=tuple(shot.shot_id for shot in shots),
        points=tuple(points),
        missing=tuple(missing),
        x_label="shot",
    )


def _position_aggregates(
    folder_key: str,
    shots: tuple[ShotAnalysisSnapshot, ...],
) -> SummaryAggregateSnapshot:
    by_position: dict[float, list[ShotAnalysisSnapshot]] = defaultdict(list)
    missing: list[tuple[str, str]] = []
    for shot in shots:
        position = shot.metadata.position
        if position is None:
            missing.append((shot.shot_id, "プローブ位置が未設定です"))
            continue
        by_position[position.millimeters].append(shot)

    points: list[SummaryAggregatePoint] = []
    for position_mm, position_shots in sorted(by_position.items()):
        for metric in SummaryMetric:
            for method in SUMMARY_METHOD_ORDER:
                shot_means: list[float] = []
                source_ids: list[str] = []
                scope_count = 0
                for shot in position_shots:
                    statistic = _shot_statistics(shot, metric, method)
                    scope_count += 1
                    if statistic.mean is not None:
                        shot_means.append(statistic.mean)
                        source_ids.append(shot.shot_id)
                if not shot_means:
                    continue
                mean = sum(shot_means) / len(shot_means)
                sample_std = (
                    math.sqrt(
                        sum((value - mean) ** 2 for value in shot_means)
                        / (len(shot_means) - 1)
                    )
                    if len(shot_means) > 1
                    else None
                )
                points.append(
                    SummaryAggregatePoint(
                        group_id=f"position-mm:{position_mm:.12g}",
                        label=f"{position_mm:g} mm",
                        x_value=position_mm,
                        method=method,
                        metric=metric,
                        count=len(shot_means),
                        scope_count=scope_count,
                        mean=mean,
                        sample_std=sample_std,
                        source_shot_ids=tuple(source_ids),
                    )
                )
    return SummaryAggregateSnapshot(
        kind=SummaryScopeKind.POSITION,
        folder_key=folder_key,
        shot_ids=tuple(shot.shot_id for shot in shots),
        points=tuple(points),
        missing=tuple(missing),
        x_label="probe position",
        x_unit="mm",
    )


def _shot_metric_points(
    shot: ShotAnalysisSnapshot,
    *,
    x_value: float,
    label: str,
) -> tuple[SummaryAggregatePoint, ...]:
    points: list[SummaryAggregatePoint] = []
    for metric in SummaryMetric:
        for method in SUMMARY_METHOD_ORDER:
            statistic = _shot_statistics(shot, metric, method)
            if statistic.mean is None:
                continue
            points.append(
                SummaryAggregatePoint(
                    group_id=shot.shot_id,
                    label=label,
                    x_value=x_value,
                    method=method,
                    metric=metric,
                    count=statistic.count,
                    scope_count=statistic.scope_count,
                    mean=statistic.mean,
                    sample_std=statistic.sample_std,
                    source_shot_ids=(shot.shot_id,),
                )
            )
    return tuple(points)


def _shot_statistics(
    shot: ShotAnalysisSnapshot,
    metric: SummaryMetric,
    method: SummaryMethod,
) -> SummaryMetricStatistics:
    snapshot = SummarySnapshot(
        scope=SummaryScope(
            kind=SummaryScopeKind.CURRENT_SHOT,
            folder_key=shot.folder_key,
            shot_ids=(shot.shot_id,),
        ),
        rows=shot.rows,
    )
    return next(
        item for item in snapshot.metric_statistics(metric) if item.method is method
    )


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
    outcomes: dict[SummaryMethod, list[tuple[AnalysisStage, MethodOutcome]]] = {
        method: [] for method in SUMMARY_METHOD_ORDER
    }
    for stage in record.stages:
        for outcome in stage.methods:
            try:
                method = SummaryMethod(outcome.method_id)
            except ValueError:
                continue
            outcomes[method].append((stage.stage, outcome))

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
    outcomes: list[tuple[AnalysisStage, MethodOutcome]],
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
    for _, outcome in outcomes:
        metrics.update(outcome.metrics)
    final = outcomes[-1][1]
    potential = next(
        (
            outcome
            for stage, outcome in reversed(outcomes)
            if stage is AnalysisStage.POTENTIAL
        ),
        None,
    )
    temperature = next(
        (
            outcome
            for stage, outcome in reversed(outcomes)
            if stage is AnalysisStage.TEMPERATURE
        ),
        None,
    )
    return SummaryMethodValue(
        method=method,
        status=final.status,
        phi_status=potential.status if potential is not None else None,
        ti_status=temperature.status if temperature is not None else None,
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
