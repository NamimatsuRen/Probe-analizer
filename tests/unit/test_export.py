from __future__ import annotations

from dataclasses import replace

import pytest

from probe_app.application.queries import build_export_candidates
from probe_app.domain.models import (
    AnalysisStatus,
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
    SummaryMethod,
    SummaryMethodValue,
    SummaryRow,
    SummaryScope,
    SummaryScopeKind,
    SummarySnapshot,
    SweepDirection,
)


def test_export_candidates_keep_warnings_visible_but_default_to_current_usable() -> None:
    summary = _summary_snapshot()

    candidates = build_export_candidates(summary)

    assert len(candidates.candidates) == 4
    assert candidates.default_candidate_count == 1
    assert candidates.warning_count == 3
    assert candidates.candidates[0].selected_by_default
    assert candidates.candidates[0].available_methods == (
        SummaryMethod.FILTERED_LOG,
    )
    assert not candidates.candidates[1].selected_by_default
    assert "設定" in candidates.candidates[1].reason
    assert not candidates.candidates[2].selected_by_default
    assert "放電" in candidates.candidates[2].reason
    assert not candidates.candidates[3].selected_by_default
    assert "fit" in candidates.candidates[3].reason
    assert candidates.default_selection.sweep_ids == ("shot-001/v:1:2",)
    assert candidates.default_selection.methods == (SummaryMethod.FILTERED_LOG,)
    assert candidates.default_selection.variants == (
        ExportDataVariant.RAW,
        ExportDataVariant.FILTERED,
    )


def test_export_manifest_is_deterministic_and_names_every_bundle_artifact() -> None:
    manifest = _manifest()
    same_recipe = _manifest()

    assert manifest.canonical_json == same_recipe.canonical_json
    assert manifest.manifest_id == same_recipe.manifest_id
    assert manifest.artifact_filenames == (
        "shot001_ti.svg",
        "shot001_ti.pdf",
        "shot001_ti.png",
        "shot001_ti.csv",
        "shot001_ti.manifest.json",
    )

    changed = replace(
        manifest,
        selection=replace(
            manifest.selection,
            sweep_ids=("shot-001/v:1:2", "shot-001/v:2:3"),
        ),
    )
    assert changed.manifest_id != manifest.manifest_id


def test_export_manifest_requires_provenance_bundle_and_safe_filename() -> None:
    manifest = _manifest()
    with pytest.raises(ValueError, match="manifest"):
        replace(
            manifest,
            artifacts=(ExportArtifactKind.SVG, ExportArtifactKind.SOURCE_CSV),
        )
    with pytest.raises(ValueError, match="path separators"):
        replace(manifest, filename_stem="paper/figure1")


def _summary_snapshot() -> SummarySnapshot:
    return SummarySnapshot(
        scope=SummaryScope(
            kind=SummaryScopeKind.CURRENT_SHOT,
            folder_key="/measurements",
            shot_ids=("shot-001",),
        ),
        rows=(
            _summary_row(
                1,
                "shot-001/v:1:2",
                AnalysisStatus.VALID,
                current_revision=True,
                methods=(
                    SummaryMethodValue(
                        method=SummaryMethod.FILTERED_LOG,
                        status=AnalysisStatus.VALID,
                        phi_v=14.2,
                        ti_ev=1.8,
                    ),
                ),
            ),
            _summary_row(
                2,
                "shot-001/v:2:3",
                AnalysisStatus.STALE,
                current_revision=False,
                message="SG設定が変更されました",
            ),
            _summary_row(
                3,
                "shot-001/v:3:4",
                AnalysisStatus.EXCLUDED,
                current_revision=True,
                exclusion_reason="放電由来の異常波形",
            ),
            _summary_row(
                4,
                "shot-001/v:4:5",
                AnalysisStatus.ERROR,
                current_revision=True,
                message="飽和域fitに失敗しました",
            ),
        ),
    )


def _summary_row(
    number: int,
    sweep_id: str,
    status: AnalysisStatus,
    *,
    current_revision: bool,
    message: str = "",
    exclusion_reason: str = "",
    methods: tuple[SummaryMethodValue, ...] = (),
) -> SummaryRow:
    return SummaryRow(
        number=number,
        sweep_id=sweep_id,
        shot_id="shot-001",
        direction=SweepDirection.UP,
        start_ms=float(number),
        stop_ms=float(number + 1),
        point_count=10,
        status=status,
        current_revision=current_revision,
        revision_key=str(number) * 64,
        message=message,
        exclusion_reason=exclusion_reason,
        methods=methods,
    )


def _manifest() -> ExportManifest:
    return ExportManifest(
        selection=ExportSelection(
            folder_key="/measurements",
            shot_ids=("shot-001",),
            sweep_ids=("shot-001/v:1:2",),
            methods=(SummaryMethod.FILTERED_LOG,),
            variants=(ExportDataVariant.FILTERED,),
        ),
        figure=FigureSpec(
            preset=ExportPreset.SINGLE_COLUMN,
            width_mm=85.0,
            height_mm=70.0,
            dpi=600,
            panels=(
                PanelSpec(
                    panel_id="a",
                    figure_type=ExportFigureType.TREND,
                    title="Ion temperature",
                    x_axis=AxisSpec(label="Sweep", unit="No."),
                    y_axis=AxisSpec(label="T_i", unit="eV"),
                ),
            ),
        ),
        styles=(
            (
                SummaryMethod.FILTERED_LOG,
                SeriesStyle(color="#175cd3", marker="circle"),
            ),
        ),
        provenance=(
            ExportProvenance(
                input_identity="shot-001/v:1:2",
                revision_key="a" * 64,
                analysis_settings=(("k_source", "shot_median"),),
                algorithm_version="level6-panta-v1",
                analysis_schema_version=1,
                code_version="abc1234",
                used_point_ids=("shot-001/v:1:2",),
            ),
        ),
        artifacts=(
            ExportArtifactKind.SVG,
            ExportArtifactKind.PDF,
            ExportArtifactKind.PNG,
            ExportArtifactKind.SOURCE_CSV,
            ExportArtifactKind.MANIFEST,
        ),
        filename_stem="shot001_ti",
    )
