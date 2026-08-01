from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QImage

from probe_app.application.queries import build_export_manifest
from probe_app.domain.models import (
    ExportArtifactKind,
    ExportFigureType,
    ExportPreset,
    ExportSourcePoint,
    ExportSourceTable,
)
from probe_app.infrastructure.exporting import (
    ExportBundleExistsError,
    PaperRenderer,
)


def test_paper_renderer_creates_vector_raster_source_and_manifest_bundle(
    tmp_path: Path,
    qtbot: object,
) -> None:
    del qtbot
    source = _source()
    manifest = build_export_manifest(
        source,
        figure_type=ExportFigureType.TREND,
        preset=ExportPreset.TWO_PANEL,
        artifacts=tuple(ExportArtifactKind),
        filename_stem="shot-001-trend",
        folder_key="/measurements",
        shot_ids=("shot-001",),
        sweep_ids=("sweep-1", "sweep-2"),
        records=(),
        code_version="0.8.0",
    )

    result = PaperRenderer().render_bundle(manifest, source, tmp_path)

    assert result.manifest_id == manifest.manifest_id
    assert {path.suffix for path in result.artifacts} >= {
        ".svg",
        ".pdf",
        ".png",
        ".csv",
        ".json",
    }
    assert all(path.stat().st_size > 0 for path in result.artifacts)
    assert (tmp_path / "shot-001-trend.manifest.json").read_text(
        encoding="utf-8"
    ).strip() == manifest.canonical_json
    assert "y_error" in (tmp_path / "shot-001-trend.csv").read_text(
        encoding="utf-8"
    )


def test_renderer_preview_and_no_implicit_overwrite(
    tmp_path: Path,
    qtbot: object,
) -> None:
    del qtbot
    source = _source()
    manifest = build_export_manifest(
        source,
        figure_type=ExportFigureType.POSITION,
        preset=ExportPreset.SINGLE_COLUMN,
        artifacts=(ExportArtifactKind.PNG, ExportArtifactKind.MANIFEST),
        filename_stem="position",
        folder_key="/measurements",
        shot_ids=("shot-001",),
        sweep_ids=(),
        records=(),
        code_version="0.8.0",
    )
    renderer = PaperRenderer()

    preview = renderer.render_preview(manifest, source, width_px=480)
    renderer.render_bundle(manifest, source, tmp_path)

    assert isinstance(preview, QImage)
    assert preview.width() == 480
    with pytest.raises(ExportBundleExistsError) as error:
        renderer.render_bundle(manifest, source, tmp_path)
    assert {path.name for path in error.value.paths} == {
        "position.png",
        "position.manifest.json",
    }


def _source() -> ExportSourceTable:
    return ExportSourceTable(
        (
            ExportSourcePoint(
                panel_id="ti",
                series_id="ti:filtered-log",
                point_id="ti:1",
                x=1.0,
                y=1.4,
                y_error=0.2,
                x_unit="Sweep No.",
                y_unit="eV",
                kind="aggregate_mean",
                status="valid",
                shot_id="shot-001",
                sweep_id="sweep-1",
            ),
            ExportSourcePoint(
                panel_id="ti",
                series_id="ti:filtered-log",
                point_id="ti:2",
                x=2.0,
                y=1.8,
                x_unit="Sweep No.",
                y_unit="eV",
                kind="aggregate_mean",
                status="review",
                shot_id="shot-001",
                sweep_id="sweep-2",
            ),
        )
    )
