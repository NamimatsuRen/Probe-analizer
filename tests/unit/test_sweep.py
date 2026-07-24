from __future__ import annotations

import numpy as np
import pytest

from probe_app.domain.models.sweep import Sweep, SweepDirection


def test_down_sweep_keeps_acquisition_order_and_exposes_ascending_iv() -> None:
    sweep = Sweep(
        sweep_id="v:10:13",
        current_series_id="i",
        voltage_series_id="v",
        source_start_index=10,
        source_stop_index=13,
        direction=SweepDirection.DOWN,
        time_s=np.asarray([1.0, 2.0, 3.0]),
        voltage_v=np.asarray([2.0, 1.0, 0.0]),
        current_a=np.asarray([20.0, 10.0, 0.0]),
        current_time_offset_s=0.25,
    )

    np.testing.assert_allclose(sweep.time_s, [1, 2, 3])
    np.testing.assert_allclose(sweep.current_reference_time_s, [1.25, 2.25, 3.25])
    assert sweep.current_time_range_s == pytest.approx((1.25, 3.25))
    np.testing.assert_allclose(sweep.iv_time_s, [3, 2, 1])
    np.testing.assert_allclose(sweep.iv_voltage_v, [0, 1, 2])
    np.testing.assert_allclose(sweep.iv_current_a, [0, 10, 20])
    assert sweep.mid_time_s == pytest.approx(2.0)


def test_boundary_must_match_array_length() -> None:
    with pytest.raises(ValueError, match="half-open source boundary"):
        Sweep(
            sweep_id="invalid",
            current_series_id="i",
            voltage_series_id="v",
            source_start_index=0,
            source_stop_index=4,
            direction=SweepDirection.UP,
            time_s=np.asarray([0.0, 1.0]),
            voltage_v=np.asarray([0.0, 1.0]),
            current_a=np.asarray([0.0, 1.0]),
        )


def test_current_time_offset_must_be_finite() -> None:
    with pytest.raises(ValueError, match="current_time_offset_s"):
        Sweep(
            sweep_id="invalid-offset",
            current_series_id="i",
            voltage_series_id="v",
            source_start_index=0,
            source_stop_index=2,
            direction=SweepDirection.UP,
            time_s=np.asarray([0.0, 1.0]),
            voltage_v=np.asarray([0.0, 1.0]),
            current_a=np.asarray([0.0, 1.0]),
            current_time_offset_s=float("nan"),
        )
