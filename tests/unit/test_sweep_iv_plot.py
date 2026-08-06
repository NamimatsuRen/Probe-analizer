from __future__ import annotations

import numpy as np
import pytest

from probe_app.analysis import SavitzkyGolaySettings, preprocess_sweep
from probe_app.domain.models.sweep import Sweep, SweepDirection
from probe_app.ui.widgets import SweepIVPlot


def _down_sweep(*, current_time_offset_s: float = 0.0) -> Sweep:
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
        current_time_offset_s=current_time_offset_s,
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
    limits = plot._plot.getViewBox().state["limits"]  # noqa: SLF001
    assert limits["xLimits"] == [-55.0, 55.0]
    assert limits["yLimits"] == pytest.approx([-13.0, 23.0])
    assert plot._plot.viewRange()[0] == pytest.approx([-55.0, 55.0])  # noqa: SLF001
    assert plot._zero_line in plot._plot.getPlotItem().items  # noqa: SLF001


def test_iv_plot_displays_direction_sources_and_acquisition_endpoints(
    qtbot: object,
) -> None:
    plot = SweepIVPlot()
    qtbot.addWidget(plot)  # type: ignore[attr-defined]
    sweep = _down_sweep(current_time_offset_s=0.05)

    plot.show_sweep(sweep)

    assert "取得方向: 下降" in plot.description
    assert "current: shot-001/current [A]" in plot.description
    assert "current時間補正: +50.000000 ms" in plot.description
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


def test_iv_plot_compares_raw_filtered_and_derivative(qtbot: object) -> None:
    voltage_v = np.linspace(2.0, -2.0, 9, dtype=np.float64)
    sweep = Sweep(
        sweep_id="shot-001/voltage:0:9",
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        source_start_index=0,
        source_stop_index=9,
        direction=SweepDirection.DOWN,
        time_s=np.arange(9, dtype=np.float64),
        voltage_v=voltage_v,
        current_a=voltage_v**2,
    )
    result = preprocess_sweep(
        sweep,
        SavitzkyGolaySettings(window_length=5, polyorder=2),
    )
    plot = SweepIVPlot()
    qtbot.addWidget(plot)  # type: ignore[attr-defined]

    plot.show_sweep(sweep)
    plot.show_preprocessing(result)

    np.testing.assert_allclose(plot.displayed_filtered_current_a, result.filtered_current_a)
    np.testing.assert_allclose(
        plot.displayed_derivative_a_per_v,
        result.dcurrent_dvoltage_a_per_v,
    )
    filtered_x, filtered_y = plot._filtered_curve.getData()  # type: ignore[union-attr]  # noqa: SLF001
    derivative_x, derivative_y = plot._derivative_curve.getData()  # type: ignore[union-attr]  # noqa: SLF001
    np.testing.assert_allclose(filtered_x, result.voltage_v)
    np.testing.assert_allclose(filtered_y, result.filtered_current_a)
    np.testing.assert_allclose(derivative_x, result.voltage_v)
    np.testing.assert_allclose(derivative_y, result.dcurrent_dvoltage_a_per_v)
    derivative_left_axis = plot._derivative_plot.getPlotItem().getAxis("left")  # noqa: SLF001
    assert derivative_left_axis.labelText == "dI/dV"
    assert derivative_left_axis.labelUnits == "A/V"

    plot.clear_preprocessing()
    assert plot.preprocessed is None
    assert plot.displayed_filtered_current_a is None
    assert plot.displayed_derivative_a_per_v is None


def test_raw_only_plot_never_adds_filtered_or_derivative_views(qtbot: object) -> None:
    plot = SweepIVPlot(analysis_enabled=False)
    qtbot.addWidget(plot)  # type: ignore[attr-defined]
    sweep = _down_sweep()

    plot.show_sweep(sweep)

    assert plot.analysis_enabled is False
    assert plot.preprocessed is None
    assert plot._derivative_plot is None  # noqa: SLF001
    assert "Raw / Filtered" not in plot._plot.getPlotItem().titleLabel.text  # noqa: SLF001

    result = preprocess_sweep(
        sweep,
        SavitzkyGolaySettings(window_length=3, polyorder=1),
    )
    with pytest.raises(RuntimeError, match="Raw-only"):
        plot.show_preprocessing(result)
