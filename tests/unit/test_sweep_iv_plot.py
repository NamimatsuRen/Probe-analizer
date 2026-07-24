from __future__ import annotations

import numpy as np

from probe_app.domain.models.sweep import Sweep, SweepDirection
from probe_app.ui.widgets import SweepIVPlot


def _down_sweep() -> Sweep:
    return Sweep(
        sweep_id="shot-001/voltage:10:14",
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        source_start_index=10,
        source_stop_index=14,
        direction=SweepDirection.DOWN,
        time_s=np.asarray([1.0, 1.1, 1.2, 1.3], dtype=np.float64),
        voltage_v=np.asarray([2.0, 1.0, 0.0, -1.0], dtype=np.float64),
        current_a=np.asarray([20.0, 10.0, 0.0, -10.0], dtype=np.float64),
    )


def test_iv_plot_uses_voltage_ascending_order_and_required_units(qtbot: object) -> None:
    plot = SweepIVPlot()
    qtbot.addWidget(plot)  # type: ignore[attr-defined]
    sweep = _down_sweep()

    plot.show_sweep(sweep)

    assert plot.selected_sweep == sweep
    np.testing.assert_allclose(plot.displayed_voltage_v, [-1.0, 0.0, 1.0, 2.0])
    np.testing.assert_allclose(plot.displayed_current_a, [-10.0, 0.0, 10.0, 20.0])
    curve_x, curve_y = plot._curve.getData()  # type: ignore[union-attr]  # noqa: SLF001
    np.testing.assert_allclose(curve_x, plot.displayed_voltage_v)
    np.testing.assert_allclose(curve_y, plot.displayed_current_a)
    bottom_axis = plot._plot.getPlotItem().getAxis("bottom")  # noqa: SLF001
    left_axis = plot._plot.getPlotItem().getAxis("left")  # noqa: SLF001
    assert bottom_axis.labelText == "Voltage"
    assert bottom_axis.labelUnits == "V"
    assert left_axis.labelText == "Current"
    assert left_axis.labelUnits == "A"


def test_iv_plot_displays_direction_sources_and_acquisition_endpoints(
    qtbot: object,
) -> None:
    plot = SweepIVPlot()
    qtbot.addWidget(plot)  # type: ignore[attr-defined]
    sweep = _down_sweep()

    plot.show_sweep(sweep)

    assert "取得方向: 下降" in plot.description
    assert "current: shot-001/current [A]" in plot.description
    assert "voltage: shot-001/voltage [V]" in plot.description
    start_x, start_y = plot._start_marker.getData()  # type: ignore[union-attr]  # noqa: SLF001
    end_x, end_y = plot._end_marker.getData()  # type: ignore[union-attr]  # noqa: SLF001
    np.testing.assert_allclose(start_x, [2.0])
    np.testing.assert_allclose(start_y, [20.0])
    np.testing.assert_allclose(end_x, [-1.0])
    np.testing.assert_allclose(end_y, [-10.0])

    plot.clear_plot("Sweep分割を実行してください")

    assert plot.selected_sweep is None
    assert plot.displayed_voltage_v is None
    assert plot.displayed_current_a is None
    assert plot.description == "Sweep分割を実行してください"
