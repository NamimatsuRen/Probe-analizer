from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt

IV_X_MIN_V = -55.0
IV_X_MAX_V = 55.0
Y_RANGE_MARGIN_FRACTION = 0.10


def add_zero_reference(plot: pg.PlotWidget) -> pg.InfiniteLine:
    """Add a quiet y=0 reference that never affects auto-ranging."""

    line = pg.InfiniteLine(
        pos=0.0,
        angle=0,
        pen=pg.mkPen("#667085", width=1.0, style=Qt.PenStyle.DashLine),
    )
    line.setZValue(-10)
    plot.addItem(line, ignoreBounds=True)
    return line


def constrain_y_to_data(
    plot: pg.PlotWidget,
    values: Iterable[object],
    *,
    include_zero: bool = True,
) -> tuple[float, float] | None:
    """Use the finite data extent as the maximum zoom-out Y range."""

    finite_parts: list[np.ndarray] = []
    for value in values:
        array = np.asarray(value, dtype=np.float64).reshape(-1)
        finite = array[np.isfinite(array)]
        if finite.size:
            finite_parts.append(finite)
    if not finite_parts:
        return None
    combined = np.concatenate(finite_parts)
    lower = float(np.min(combined))
    upper = float(np.max(combined))
    if include_zero:
        lower = min(lower, 0.0)
        upper = max(upper, 0.0)
    span = upper - lower
    scale = max(abs(lower), abs(upper), 1.0)
    margin = max(span * Y_RANGE_MARGIN_FRACTION, scale * 1e-6)
    limits = (lower - margin, upper + margin)
    plot.getViewBox().setLimits(yMin=limits[0], yMax=limits[1])
    plot.setYRange(*limits, padding=0.0)
    return limits


def constrain_iv_x(plot: pg.PlotWidget) -> None:
    """Prevent I–V zoom-out and pan beyond the physical -55...+55 V view."""

    plot.getViewBox().setLimits(xMin=IV_X_MIN_V, xMax=IV_X_MAX_V)
    plot.setXRange(IV_X_MIN_V, IV_X_MAX_V, padding=0.0)
