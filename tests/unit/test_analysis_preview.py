from __future__ import annotations

import numpy as np

from probe_app.analysis import summarize_sweep
from probe_app.domain.models.sweep import Sweep, SweepDirection
from probe_app.ui.widgets import AnalysisPreviewPanel


def _sweep() -> Sweep:
    return Sweep(
        sweep_id="shot-001/voltage:10:14",
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        source_start_index=10,
        source_stop_index=14,
        direction=SweepDirection.UP,
        time_s=np.asarray([0.1, 0.2, 0.3, 0.4], dtype=np.float64),
        voltage_v=np.asarray([-2.0, -0.5, 1.0, 2.5], dtype=np.float64),
        current_a=np.asarray([-0.02, -0.01, 0.03, 0.08], dtype=np.float64),
    )


def test_analysis_preview_is_a_pure_sweep_summary() -> None:
    preview = summarize_sweep(_sweep())

    assert preview.point_count == 4
    assert preview.voltage_min_v == -2.0
    assert preview.voltage_max_v == 2.5
    assert preview.current_min_a == -0.02
    assert preview.current_max_a == 0.08
    assert preview.median_voltage_step_v == 1.5


def test_analysis_preview_panel_consumes_selection_without_a_reader(
    qtbot: object,
) -> None:
    panel = AnalysisPreviewPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    sweep = _sweep()

    panel.show_sweep(sweep)

    assert panel.selected_sweep == sweep
    assert sweep.sweep_id in panel.description
    assert "4 点" in panel.description
    assert "readerを再実行せず" in panel.description

    panel.clear()
    assert panel.selected_sweep is None
