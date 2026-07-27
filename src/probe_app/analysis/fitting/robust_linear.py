from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from probe_app.domain.models.raw_series import FloatArray


class LinearFitError(ValueError):
    """A user-correctable robust linear fit failure."""


@dataclass(frozen=True, slots=True)
class RobustLinearFit:
    """Line coefficients and diagnostics after iterative MAD clipping."""

    slope: float
    intercept: float
    rmse: float
    r_squared: float
    point_count: int
    used_point_count: int
    x_min: float
    x_max: float

    def evaluate(self, x: FloatArray | float) -> FloatArray | float:
        return self.slope * x + self.intercept


def robust_linear_fit(
    x: FloatArray,
    y: FloatArray,
    *,
    minimum_points: int = 3,
    sigma_threshold: float = 2.5,
    max_iterations: int = 6,
) -> RobustLinearFit:
    """Fit y=a*x+b while repeatedly removing large MAD residuals."""

    x_values = np.asarray(x, dtype=np.float64)
    y_values = np.asarray(y, dtype=np.float64)
    if x_values.ndim != 1 or y_values.ndim != 1:
        raise LinearFitError("fit arrays must be one-dimensional")
    if x_values.size != y_values.size:
        raise LinearFitError("fit arrays must have the same length")
    finite = np.isfinite(x_values) & np.isfinite(y_values)
    if int(np.count_nonzero(finite)) < minimum_points:
        raise LinearFitError(
            f"fitに必要な有限点が不足しています（最低{minimum_points}点）"
        )

    x_values = x_values[finite]
    y_values = y_values[finite]
    if float(np.ptp(x_values)) <= np.finfo(np.float64).eps:
        raise LinearFitError("fit電圧に幅がありません")

    keep = np.ones(x_values.size, dtype=np.bool_)
    for _ in range(max_iterations):
        slope, intercept = _least_squares(x_values[keep], y_values[keep])
        residuals = y_values - (slope * x_values + intercept)
        kept_residuals = residuals[keep]
        center = float(np.median(kept_residuals))
        mad = float(np.median(np.abs(kept_residuals - center)))
        robust_sigma = 1.4826 * mad
        value_scale = max(
            1.0,
            float(np.max(np.abs(y_values[keep]))),
            float(np.max(np.abs(slope * x_values[keep] + intercept))),
        )
        numerical_tolerance = 64.0 * np.finfo(np.float64).eps * value_scale
        clipping_threshold = max(
            sigma_threshold * robust_sigma,
            numerical_tolerance,
        )
        updated = np.abs(residuals - center) <= clipping_threshold
        if int(np.count_nonzero(updated)) < minimum_points:
            break
        if np.array_equal(updated, keep):
            break
        keep = updated

    slope, intercept = _least_squares(x_values[keep], y_values[keep])
    predicted = slope * x_values[keep] + intercept
    residuals = y_values[keep] - predicted
    sum_squared = float(np.sum(residuals**2))
    rmse = float(np.sqrt(sum_squared / keep.sum()))
    centered = y_values[keep] - float(np.mean(y_values[keep]))
    total_squared = float(np.sum(centered**2))
    r_squared = 1.0 if total_squared <= np.finfo(np.float64).eps else (
        1.0 - sum_squared / total_squared
    )
    return RobustLinearFit(
        slope=slope,
        intercept=intercept,
        rmse=rmse,
        r_squared=float(r_squared),
        point_count=int(x_values.size),
        used_point_count=int(np.count_nonzero(keep)),
        x_min=float(np.min(x_values[keep])),
        x_max=float(np.max(x_values[keep])),
    )


def _least_squares(x: FloatArray, y: FloatArray) -> tuple[float, float]:
    design = np.column_stack((x, np.ones(x.size, dtype=np.float64)))
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    return float(coefficients[0]), float(coefficients[1])
