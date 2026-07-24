from __future__ import annotations

from pathlib import Path

import numpy as np

from probe_app.domain.models.raw_series import RawSeries, RawSeriesDescriptor
from probe_app.domain.models.sweep import Sweep, SweepDirection
from probe_app.ui.widgets import RawPlot


def _raw_series() -> RawSeries:
    descriptor = RawSeriesDescriptor(
        series_id="shot-001/current",
        shot_id="shot-001",
        channel_id="current",
        header_path=Path("current.hdr"),
        data_path=Path("current.dat"),
        sample_count=8,
        value_unit="A",
        time_unit="s",
    )
    return RawSeries(
        descriptor=descriptor,
        time_s=np.arange(8, dtype=np.float64) * 0.1,
        values=np.arange(8, dtype=np.float64),
    )


def _sweep() -> Sweep:
    return Sweep(
        sweep_id="shot-001/voltage:2:6",
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        source_start_index=2,
        source_stop_index=6,
        direction=SweepDirection.DOWN,
        time_s=np.asarray([0.2, 0.3, 0.4, 0.5], dtype=np.float64),
        voltage_v=np.asarray([2.0, 1.0, 0.0, -1.0], dtype=np.float64),
        current_a=np.asarray([4.0, 3.0, 2.0, 1.0], dtype=np.float64),
    )


def test_raw_plot_highlights_selected_sweep_and_explains_source(qtbot: object) -> None:
    plot = RawPlot()
    qtbot.addWidget(plot)  # type: ignore[attr-defined]
    plot.show_series(_raw_series())

    sweep = _sweep()
    plot.highlight_sweep(sweep)

    assert plot.highlighted_sweep == sweep
    assert plot.highlighted_interval_s == (0.2, 0.5)
    assert tuple(plot._sweep_region.getRegion()) == (0.2, 0.5)  # type: ignore[union-attr]  # noqa: SLF001
    assert "shot-001/voltage" in plot.highlight_description
    assert "sample 2–5" in plot.highlight_description
    assert not plot._selection_info.isHidden()  # noqa: SLF001


def test_raw_plot_preserves_highlight_on_redraw_and_can_clear(qtbot: object) -> None:
    plot = RawPlot()
    qtbot.addWidget(plot)  # type: ignore[attr-defined]
    sweep = _sweep()
    plot.highlight_sweep(sweep)

    plot.show_series(_raw_series())

    assert plot.highlighted_sweep == sweep
    assert plot._sweep_region is not None  # noqa: SLF001

    plot.clear_sweep_highlight()

    assert plot.highlighted_sweep is None
    assert plot.highlighted_interval_s is None
    assert plot._sweep_region is None  # noqa: SLF001
    assert plot._selection_info.isHidden()  # noqa: SLF001
