from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from probe_app.domain.models.sweep import Sweep


@dataclass(frozen=True, slots=True)
class SweepPreview:
    """Small Level 3 seam used to verify analysis can be added without readers."""

    point_count: int
    voltage_min_v: float
    voltage_max_v: float
    current_min_a: float
    current_max_a: float
    median_voltage_step_v: float | None


def summarize_sweep(sweep: Sweep) -> SweepPreview:
    """Return read-only numerical facts without importing any GUI dependency."""

    voltage_steps = np.abs(np.diff(sweep.voltage_v))
    return SweepPreview(
        point_count=sweep.point_count,
        voltage_min_v=float(np.min(sweep.voltage_v)),
        voltage_max_v=float(np.max(sweep.voltage_v)),
        current_min_a=float(np.min(sweep.current_a)),
        current_max_a=float(np.max(sweep.current_a)),
        median_voltage_step_v=(
            float(np.median(voltage_steps)) if voltage_steps.size else None
        ),
    )
