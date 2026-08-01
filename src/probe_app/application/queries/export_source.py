from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from probe_app.analysis import PreprocessedSweep
from probe_app.analysis.temperature import panta_current
from probe_app.domain.models.analysis_result import (
    AnalysisStage,
    SweepAnalysisRecord,
)
from probe_app.domain.models.export import (
    AxisSpec,
    ExportArtifactKind,
    ExportDataVariant,
    ExportFigureType,
    ExportManifest,
    ExportPreset,
    ExportProvenance,
    ExportSelection,
    FigureSpec,
    PanelSpec,
    SeriesStyle,
)
from probe_app.domain.models.export_source import (
    ExportSourcePoint,
    ExportSourceTable,
)
from probe_app.domain.models.summary import (
    SUMMARY_METHOD_ORDER,
    SummaryAggregateSnapshot,
    SummaryMethod,
    SummaryMetric,
    SummarySnapshot,
)
from probe_app.domain.models.sweep import Sweep

_COLORS = ("#2563eb", "#ea580c", "#16a34a", "#9333ea", "#111827")


def build_summary_export_source(
    snapshot: SummarySnapshot,
    selected_sweep_ids: tuple[str, ...],
) -> ExportSourceTable:
    selected = frozenset(selected_sweep_ids)
    points: list[ExportSourcePoint] = []
    for metric in SummaryMetric:
        panel_id = metric.value
        unit = "eV" if metric is SummaryMetric.TI else "V"
        for method in SUMMARY_METHOD_ORDER:
            for point in snapshot.plot_points(metric, method):
                if point.sweep_id not in selected:
                    continue
                row = next(item for item in snapshot.rows if item.sweep_id == point.sweep_id)
                points.append(
                    ExportSourcePoint(
                        panel_id=panel_id,
                        series_id=f"{panel_id}:{method.value}",
                        point_id=f"{panel_id}:{method.value}:{point.sweep_id}",
                        x=float(point.number),
                        y=point.value,
                        x_unit="Sweep No.",
                        y_unit=unit,
                        kind="aggregate_point" if point.included else "reference_point",
                        status=point.status.value,
                        shot_id=row.shot_id,
                        sweep_id=point.sweep_id,
                        method_id=method.value,
                    )
                )
    return ExportSourceTable(tuple(points))


def build_position_export_source(
    snapshot: SummaryAggregateSnapshot,
) -> ExportSourceTable:
    points = tuple(
        ExportSourcePoint(
            panel_id=point.metric.value,
            series_id=f"{point.metric.value}:{point.method.value}",
            point_id=f"{point.metric.value}:{point.method.value}:{point.group_id}",
            x=point.x_value,
            y=point.mean,
            y_error=point.sample_std,
            x_unit=snapshot.x_unit or "shot",
            y_unit="eV" if point.metric is SummaryMetric.TI else "V",
            kind="aggregate_mean",
            status="aggregate",
            shot_id=";".join(point.source_shot_ids),
            method_id=point.method.value,
        )
        for point in snapshot.points
    )
    return ExportSourceTable(points)


def build_iv_export_source(
    sweep: Sweep,
    preprocessed: PreprocessedSweep | None,
    record: SweepAnalysisRecord | None,
    *,
    include_fit_evidence: bool,
) -> ExportSourceTable:
    voltage = np.asarray(sweep.iv_voltage_v, dtype=np.float64)
    current_ma = np.asarray(sweep.iv_current_a, dtype=np.float64) * 1_000.0
    points: list[ExportSourcePoint] = []
    points.extend(
        _curve_points(
            "iv",
            "iv:raw",
            voltage,
            current_ma,
            sweep,
            kind="raw",
            y_unit="mA",
        )
    )
    if preprocessed is not None and preprocessed.sweep_id == sweep.sweep_id:
        points.extend(
            _curve_points(
                "iv",
                "iv:filtered",
                preprocessed.voltage_v,
                preprocessed.filtered_current_a * 1_000.0,
                sweep,
                kind="filtered",
                y_unit="mA",
            )
        )
        if include_fit_evidence:
            points.extend(
                _curve_points(
                    "derivative",
                    "derivative:sg",
                    preprocessed.voltage_v,
                    preprocessed.dcurrent_dvoltage_a_per_v * 1_000.0,
                    sweep,
                    kind="derivative",
                    y_unit="mA/V",
                )
            )
            if record is not None:
                points.extend(_panta_model_points(preprocessed, sweep, record))
    return ExportSourceTable(tuple(points))


def build_export_manifest(
    source: ExportSourceTable,
    *,
    figure_type: ExportFigureType,
    preset: ExportPreset,
    artifacts: tuple[ExportArtifactKind, ...],
    filename_stem: str,
    folder_key: str,
    shot_ids: tuple[str, ...],
    sweep_ids: tuple[str, ...],
    records: tuple[SweepAnalysisRecord, ...],
    code_version: str,
) -> ExportManifest:
    methods = tuple(
        method
        for method in SummaryMethod
        if any(point.method_id == method.value for point in source.points)
    )
    variants = tuple(
        variant
        for variant in ExportDataVariant
        if any(point.kind == variant.value for point in source.points)
    )
    if not variants:
        variants = (ExportDataVariant.RAW,)
    selection = ExportSelection(
        folder_key=folder_key,
        shot_ids=shot_ids,
        sweep_ids=sweep_ids,
        methods=methods,
        variants=variants,
        position_ids=tuple(
            dict.fromkeys(
                point.point_id.rsplit(":", 1)[-1]
                for point in source.points
                if figure_type is ExportFigureType.POSITION
            )
        ),
    )
    width_mm, height_mm = _preset_size(preset)
    panels = tuple(
        _panel_spec(panel_id, figure_type, source.for_panel(panel_id))
        for panel_id in source.panel_ids
    )
    styles = tuple(
        (
            series_id,
            SeriesStyle(
                color=_COLORS[index % len(_COLORS)],
                marker="circle" if figure_type in _aggregate_figure_types() else "none",
            ),
        )
        for index, series_id in enumerate(source.series_ids)
    )
    provenance = tuple(
        _record_provenance(record, code_version)
        for record in records
        if not sweep_ids or record.revision.sweep_id in sweep_ids
    )
    normalized_artifacts = tuple(dict.fromkeys((*artifacts, ExportArtifactKind.MANIFEST)))
    return ExportManifest(
        selection=selection,
        figure=FigureSpec(
            preset=preset,
            width_mm=width_mm,
            height_mm=height_mm,
            dpi=300,
            panels=panels,
        ),
        styles=styles,
        provenance=provenance,
        artifacts=normalized_artifacts,
        filename_stem=filename_stem,
    )


def _curve_points(
    panel_id: str,
    series_id: str,
    x_values: np.ndarray,
    y_values: np.ndarray,
    sweep: Sweep,
    *,
    kind: str,
    y_unit: str,
) -> Iterable[ExportSourcePoint]:
    for index, (x_value, y_value) in enumerate(zip(x_values, y_values, strict=True)):
        yield ExportSourcePoint(
            panel_id=panel_id,
            series_id=series_id,
            point_id=f"{series_id}:{index}",
            x=float(x_value),
            y=float(y_value),
            x_unit="V",
            y_unit=y_unit,
            kind=kind,
            status="measured" if kind == "raw" else "derived",
            shot_id=_shot_id(sweep),
            sweep_id=sweep.sweep_id,
        )


def _panta_model_points(
    preprocessed: PreprocessedSweep,
    sweep: Sweep,
    record: SweepAnalysisRecord,
) -> tuple[ExportSourcePoint, ...]:
    saturation_stage = record.stage_result(AnalysisStage.SATURATION)
    temperature_stage = record.stage_result(AnalysisStage.TEMPERATURE)
    if saturation_stage is None or temperature_stage is None:
        return ()
    saturation = next(
        (item for item in saturation_stage.methods if item.method_id == "saturation_parameters"),
        None,
    )
    if saturation is None:
        return ()
    saturation_metrics = dict(saturation.metrics)
    required = ("vf_v", "isat_i_a", "r_ratio", "k_per_v")
    if any(name not in saturation_metrics for name in required):
        return ()
    points: list[ExportSourcePoint] = []
    for method in temperature_stage.methods:
        metrics = dict(method.metrics)
        if "phi_v" not in metrics or "ti_ev" not in metrics:
            continue
        model_ma = panta_current(
            preprocessed.voltage_v,
            ti_ev=metrics["ti_ev"],
            phi_v=metrics["phi_v"],
            vf_v=saturation_metrics["vf_v"],
            isat_i_a=saturation_metrics["isat_i_a"],
            r_ratio=saturation_metrics["r_ratio"],
            k_per_v=saturation_metrics["k_per_v"],
        ) * 1_000.0
        series_id = f"iv:model:{method.method_id}"
        for index, (voltage, current) in enumerate(
            zip(preprocessed.voltage_v, model_ma, strict=True)
        ):
            points.append(
                ExportSourcePoint(
                    panel_id="iv",
                    series_id=series_id,
                    point_id=f"{series_id}:{index}",
                    x=float(voltage),
                    y=float(current),
                    x_unit="V",
                    y_unit="mA",
                    kind="model",
                    status=method.status.value,
                    shot_id=_shot_id(sweep),
                    sweep_id=sweep.sweep_id,
                    method_id=method.method_id,
                )
            )
    return tuple(points)


def _panel_spec(
    panel_id: str,
    figure_type: ExportFigureType,
    points: tuple[ExportSourcePoint, ...],
) -> PanelSpec:
    first = points[0]
    title = {
        "iv": "Probe I–V",
        "derivative": "dI/dV",
        "ti": "Ion temperature",
        "phi": "Plasma potential",
    }.get(panel_id, panel_id)
    return PanelSpec(
        panel_id=panel_id,
        figure_type=figure_type,
        title=title,
        x_axis=AxisSpec("Voltage" if first.x_unit == "V" else "Sweep / position", first.x_unit),
        y_axis=AxisSpec(title, first.y_unit),
        show_error_bars=any(point.y_error is not None for point in points),
    )


def _record_provenance(
    record: SweepAnalysisRecord,
    code_version: str,
) -> ExportProvenance:
    revision = record.revision
    settings = tuple(
        sorted(
            (
                *revision.fit_settings,
                ("sg_polyorder", str(revision.preprocessing.polyorder)),
                ("sg_window", str(revision.preprocessing.window_length)),
                ("sample_start", str(revision.split.sample_start)),
                ("sample_stop", str(revision.split.sample_stop)),
                ("time_offset_s", f"{revision.split.current_time_offset_s:.17g}"),
            )
        )
    )
    return ExportProvenance(
        input_identity=revision.sweep_id,
        revision_key=revision.cache_key,
        analysis_settings=settings,
        algorithm_version=revision.algorithm_version,
        analysis_schema_version=revision.schema_version,
        code_version=code_version,
        used_point_ids=(f"sweep:{revision.sweep_id}",),
        exclusion_reason=record.exclusion_reason,
    )


def _preset_size(preset: ExportPreset) -> tuple[float, float]:
    return {
        ExportPreset.SINGLE_COLUMN: (89.0, 70.0),
        ExportPreset.DOUBLE_COLUMN: (183.0, 110.0),
        ExportPreset.TWO_PANEL: (183.0, 85.0),
        ExportPreset.FOUR_PANEL: (183.0, 150.0),
    }[preset]


def _aggregate_figure_types() -> frozenset[ExportFigureType]:
    return frozenset(
        (
            ExportFigureType.TREND,
            ExportFigureType.POSITION,
            ExportFigureType.METHOD_COMPARISON,
        )
    )


def _shot_id(sweep: Sweep) -> str:
    return sweep.current_series_id.split("/", 1)[0]
