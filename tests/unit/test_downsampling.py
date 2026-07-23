from __future__ import annotations

import numpy as np
import pytest

from probe_app.ui.downsampling import min_max_downsample


def test_returns_original_arrays_below_limit() -> None:
    x = np.arange(10, dtype=np.float64)
    y = x**2

    reduced_x, reduced_y = min_max_downsample(x, y, max_points=20)

    assert reduced_x is x
    assert reduced_y is y


def test_preserves_endpoints_and_spike_within_limit() -> None:
    x = np.arange(10_000, dtype=np.float64)
    y = np.sin(x / 100)
    y[5_432] = 100.0

    reduced_x, reduced_y = min_max_downsample(x, y, max_points=500)

    assert reduced_x.size <= 500
    assert reduced_x[0] == 0
    assert reduced_x[-1] == 9_999
    assert np.max(reduced_y) == pytest.approx(100.0)


def test_rejects_mismatched_arrays() -> None:
    with pytest.raises(ValueError):
        min_max_downsample(np.arange(3.0), np.arange(4.0))
