from __future__ import annotations

import numpy as np
import pytest

from probe_app.analysis import (
    PreprocessingError,
    SavitzkyGolaySettings,
    preprocess_sweep,
    safe_savgol_window,
)
from probe_app.domain.models.sweep import Sweep, SweepDirection


def _sweep(
    voltage_v: np.ndarray,
    current_a: np.ndarray,
    *,
    direction: SweepDirection = SweepDirection.UP,
) -> Sweep:
    point_count = voltage_v.size
    return Sweep(
        sweep_id="shot-001/voltage:0:test",
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        source_start_index=0,
        source_stop_index=point_count,
        direction=direction,
        time_s=np.arange(point_count, dtype=np.float64) * 0.001,
        voltage_v=np.asarray(voltage_v, dtype=np.float64),
        current_a=np.asarray(current_a, dtype=np.float64),
    )


@pytest.mark.parametrize(
    ("point_count", "requested", "polyorder", "expected"),
    [
        (10_000, 501, 3, 501),
        (10, 501, 3, 9),
        (10, 8, 3, 7),
        (5, 3, 3, 5),
    ],
)
def test_safe_savgol_window_adjusts_to_valid_odd_length(
    point_count: int,
    requested: int,
    polyorder: int,
    expected: int,
) -> None:
    settings = SavitzkyGolaySettings(
        window_length=requested,
        polyorder=polyorder,
    )

    assert safe_savgol_window(point_count, settings) == expected


def test_safe_savgol_window_explains_insufficient_points() -> None:
    with pytest.raises(PreprocessingError, match="最低5点"):
        safe_savgol_window(
            4,
            SavitzkyGolaySettings(window_length=501, polyorder=3),
        )


@pytest.mark.parametrize(
    ("window_length", "polyorder"),
    [(0, 3), (5, -1)],
)
def test_settings_reject_invalid_values(window_length: int, polyorder: int) -> None:
    with pytest.raises(ValueError):
        SavitzkyGolaySettings(
            window_length=window_length,
            polyorder=polyorder,
        )


def test_preprocessing_is_exact_for_cubic_polynomial() -> None:
    voltage_v = np.linspace(-5.0, 5.0, 101, dtype=np.float64)
    current_a = voltage_v**3 + 2.0 * voltage_v**2 - 4.0 * voltage_v + 1.0
    sweep = _sweep(voltage_v, current_a)

    result = preprocess_sweep(
        sweep,
        SavitzkyGolaySettings(window_length=21, polyorder=3),
    )

    expected_derivative = 3.0 * voltage_v**2 + 4.0 * voltage_v - 4.0
    np.testing.assert_allclose(result.voltage_v, voltage_v)
    np.testing.assert_allclose(result.raw_current_a, current_a)
    np.testing.assert_allclose(result.filtered_current_a, current_a, atol=2e-11)
    np.testing.assert_allclose(
        result.dcurrent_dvoltage_a_per_v,
        expected_derivative,
        atol=2e-10,
    )
    assert result.used_window_length == 21
    assert result.polyorder == 3
    assert result.voltage_step_v == pytest.approx(0.1)
    assert result.spacing_warning == ""


def test_preprocessing_uses_voltage_ascending_order_for_down_sweep() -> None:
    acquisition_voltage = np.linspace(5.0, -5.0, 11, dtype=np.float64)
    acquisition_current = 2.0 * acquisition_voltage + 3.0
    sweep = _sweep(
        acquisition_voltage,
        acquisition_current,
        direction=SweepDirection.DOWN,
    )

    result = preprocess_sweep(
        sweep,
        SavitzkyGolaySettings(window_length=5, polyorder=1),
    )

    np.testing.assert_allclose(result.voltage_v, np.linspace(-5.0, 5.0, 11))
    np.testing.assert_allclose(result.filtered_current_a, result.raw_current_a)
    np.testing.assert_allclose(result.dcurrent_dvoltage_a_per_v, 2.0)


def test_preprocessing_reports_nonuniform_voltage_spacing() -> None:
    voltage_v = np.asarray([0.0, 1.0, 0.9, 3.0, 4.0, 5.0, 6.0])
    sweep = _sweep(voltage_v, voltage_v.copy())

    result = preprocess_sweep(
        sweep,
        SavitzkyGolaySettings(window_length=5, polyorder=2),
    )

    assert result.max_spacing_deviation_fraction > 0.05
    assert "等間隔近似" in result.spacing_warning


def test_preprocessing_does_not_mutate_sweep_arrays() -> None:
    voltage_v = np.linspace(-1.0, 1.0, 9, dtype=np.float64)
    current_a = voltage_v**2
    sweep = _sweep(voltage_v, current_a)
    original_voltage = sweep.voltage_v.copy()
    original_current = sweep.current_a.copy()

    result = preprocess_sweep(
        sweep,
        SavitzkyGolaySettings(window_length=5, polyorder=2),
    )
    result.filtered_current_a[0] = 123.0

    np.testing.assert_array_equal(sweep.voltage_v, original_voltage)
    np.testing.assert_array_equal(sweep.current_a, original_current)
