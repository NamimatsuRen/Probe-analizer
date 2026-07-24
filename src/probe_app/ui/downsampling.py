from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]


def min_max_downsample(
    x: FloatArray,
    y: FloatArray,
    *,
    max_points: int = 50_000,
) -> tuple[FloatArray, FloatArray]:
    """Reduce display points while retaining local extrema and endpoints."""

    if x.ndim != 1 or y.ndim != 1 or x.size != y.size:
        raise ValueError("x and y must be one-dimensional arrays of the same length")
    if max_points < 4:
        raise ValueError("max_points must be at least 4")
    if x.size <= max_points:
        return x, y

    bucket_count = max(1, (max_points - 2) // 2)
    bucket_size = math.ceil(x.size / bucket_count)
    full_size = (x.size // bucket_size) * bucket_size
    if full_size == 0:
        indices = np.linspace(0, x.size - 1, max_points, dtype=np.int64)
        return x[indices], y[indices]

    values = y[:full_size].reshape(-1, bucket_size)
    offsets = np.arange(values.shape[0], dtype=np.int64) * bucket_size
    min_indices = offsets + np.argmin(values, axis=1)
    max_indices = offsets + np.argmax(values, axis=1)
    indices = np.sort(np.concatenate((min_indices, max_indices, np.array([0, x.size - 1]))))
    indices = np.unique(indices)
    return x[indices], y[indices]
