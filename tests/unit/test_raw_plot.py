from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from probe_app.domain.models.raw_series import RawSeries, RawSeriesDescriptor
from probe_app.domain.models.sweep import Sweep, SweepDirection
from probe_app.ui.widgets import RawPlot


def _raw_series(series_id: str = "shot-001/current") -> RawSeries:
    channel_id = series_id.rsplit("/", 1)[-1]
    descriptor = RawSeriesDescriptor(
        series_id=series_id,
        shot_id="shot-001",
        channel_id=channel_id,
        header_path=Path(f"{channel_id}.hdr"),
        data_path=Path(f"{channel_id}.dat"),
        sample_count=8,
        value_unit="A",
        time_unit="s",
    )
    return RawSeries(
        descriptor=descriptor,
        time_s=np.arange(8, dtype=np.float64) * 0.1,
        values=np.arange(8, dtype=np.float64),
    )


def _sweep(*, current_time_offset_s: float = 0.0) -> Sweep:
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
        current_time_offset_s=current_time_offset_s,
    )


def test_raw_plot_highlights_selected_sweep_and_explains_source(qtbot: object) -> None:
    plot = RawPlot()
    qtbot.addWidget(plot)  # type: ignore[attr-defined]
    plot.show_series(_raw_series())

    sweep = _sweep()
    plot.highlight_sweep(sweep)

    assert plot.highlighted_sweep == sweep
    assert plot.highlighted_interval_s == (0.2, 0.5)
    assert plot.highlighted_interval_ms == (200.0, 500.0)
    assert tuple(plot._sweep_region.getRegion()) == (200.0, 500.0)  # type: ignore[union-attr]  # noqa: SLF001
    assert "shot-001/voltage" in plot.highlight_description
    assert "sample 2–5" in plot.highlight_description
    assert "200–500 ms" in plot.highlight_description
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


def test_current_raw_highlight_uses_corrected_reference_time(
    qtbot: object,
) -> None:
    plot = RawPlot()
    qtbot.addWidget(plot)  # type: ignore[attr-defined]
    plot.show_series(_raw_series("shot-001/current"))

    sweep = _sweep(current_time_offset_s=0.05)
    plot.highlight_sweep(sweep)

    assert plot.highlighted_interval_s == pytest.approx((0.25, 0.55))
    assert tuple(plot._sweep_region.getRegion()) == pytest.approx((250.0, 550.0))  # type: ignore[union-attr]  # noqa: SLF001
    assert "表示中current参照 250–550 ms" in plot.highlight_description
    assert "補正 +50.000000 ms" in plot.highlight_description
    assert "Sweep電圧基準 200–500 ms" in plot.highlight_description


def test_voltage_raw_highlight_keeps_voltage_reference_time(
    qtbot: object,
) -> None:
    plot = RawPlot()
    qtbot.addWidget(plot)  # type: ignore[attr-defined]
    plot.show_series(_raw_series("shot-001/voltage"))

    sweep = _sweep(current_time_offset_s=0.05)
    plot.highlight_sweep(sweep)

    assert plot.highlighted_interval_s == pytest.approx((0.2, 0.5))
    assert tuple(plot._sweep_region.getRegion()) == pytest.approx((200.0, 500.0))  # type: ignore[union-attr]  # noqa: SLF001
    assert "Sweep電圧基準 200–500 ms" in plot.highlight_description
    assert "current 補正 +50.000000 ms" in plot.highlight_description


def test_raw_plot_keeps_the_complete_time_range_and_displays_ms(
    qtbot: object,
) -> None:
    plot = RawPlot()
    qtbot.addWidget(plot)  # type: ignore[attr-defined]

    plot.show_series(_raw_series())

    curve = plot._plot.listDataItems()[0]  # noqa: SLF001
    x, _ = curve.getData()
    assert x is not None
    assert float(x[0]) == 0.0
    assert float(x[-1]) == pytest.approx(700.0)
    bottom_axis = plot._plot.getPlotItem().getAxis("bottom")  # noqa: SLF001
    assert bottom_axis.labelText == "Time"
    assert bottom_axis.labelUnits == "ms"


def test_offset_preview_moves_only_the_current_raw_region(
    qtbot: object,
) -> None:
    plot = RawPlot()
    qtbot.addWidget(plot)  # type: ignore[attr-defined]
    plot.show_series(_raw_series("shot-001/current"))
    sweep = _sweep(current_time_offset_s=0.05)
    plot.highlight_sweep(sweep)
    region_before_preview = plot._sweep_region  # noqa: SLF001

    plot.preview_current_time_offset(0.075)

    assert plot._sweep_region is region_before_preview  # noqa: SLF001
    assert plot.highlighted_interval_s == pytest.approx((0.275, 0.575))
    assert plot.highlighted_interval_ms == pytest.approx((275.0, 575.0))
    assert tuple(plot._sweep_region.getRegion()) == pytest.approx((275.0, 575.0))  # type: ignore[union-attr]  # noqa: SLF001
    assert "プレビュー +75.000000 ms（未適用）" in plot.highlight_description
    assert "適用済み +50.000000 ms" in plot.highlight_description
    assert sweep.current_time_offset_s == 0.05

    plot.clear_current_time_offset_preview()

    assert plot.preview_current_time_offset_s is None
    assert plot.highlighted_interval_ms == pytest.approx((250.0, 550.0))
