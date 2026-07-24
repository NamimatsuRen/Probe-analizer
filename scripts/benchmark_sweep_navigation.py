from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import asdict, dataclass

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from probe_app.domain.models.sweep import Sweep, SweepDirection
from probe_app.domain.services.signal_alignment import AlignedSignals
from probe_app.domain.services.sweep_splitter import (
    LegacySweepSplitParameters,
    split_legacy_sweeps_with_diagnostics,
)
from probe_app.ui.widgets import RawPlot, SweepBrowser, SweepIVPlot


@dataclass(frozen=True, slots=True)
class TimingSummary:
    iterations: int
    median_ms: float
    p95_ms: float
    maximum_ms: float


@dataclass(frozen=True, slots=True)
class Level2Benchmark:
    selection_target_ms: float
    sweep_count: int
    points_per_sweep: int
    plot_update: TimingSummary
    split_recalculation: TimingSummary

    @property
    def selection_target_met(self) -> bool:
        return self.plot_update.p95_ms <= self.selection_target_ms


def main() -> None:
    app = QApplication.instance() or QApplication([])
    sweeps = _sweeps(count=40, point_count=10_000)
    browser = SweepBrowser()
    raw_plot = RawPlot()
    iv_plot = SweepIVPlot()
    browser.sweep_selected.connect(raw_plot.highlight_sweep)
    browser.sweep_selected.connect(iv_plot.show_sweep)
    browser.set_sweeps(sweeps)

    for index in range(1, 6):
        browser.select_sweep(sweeps[index].sweep_id)
        app.processEvents()

    selection_timings: list[float] = []
    for iteration in range(200):
        target = sweeps[iteration % len(sweeps)]
        start = time.perf_counter()
        browser.select_sweep(target.sweep_id)
        app.processEvents()
        selection_timings.append((time.perf_counter() - start) * 1_000)

    signals = _aligned_signals(cycle_count=2_000)
    parameters = LegacySweepSplitParameters(points_per_cycle=8)
    recalculation_timings: list[float] = []
    for _ in range(30):
        start = time.perf_counter()
        split_legacy_sweeps_with_diagnostics(signals, parameters)
        recalculation_timings.append((time.perf_counter() - start) * 1_000)

    result = Level2Benchmark(
        selection_target_ms=200.0,
        sweep_count=len(sweeps),
        points_per_sweep=sweeps[0].point_count,
        plot_update=_summary(selection_timings),
        split_recalculation=_summary(recalculation_timings),
    )
    output = asdict(result)
    output["selection_target_met"] = result.selection_target_met
    print(json.dumps(output, ensure_ascii=False, indent=2))


def _sweeps(*, count: int, point_count: int) -> tuple[Sweep, ...]:
    voltage_up = np.linspace(-35.0, 50.0, point_count, dtype=np.float64)
    current_up = 0.002 * voltage_up + 0.01 * np.tanh(voltage_up / 8.0)
    sweeps: list[Sweep] = []
    for index in range(count):
        direction = SweepDirection.UP if index % 2 == 0 else SweepDirection.DOWN
        voltage = voltage_up if direction is SweepDirection.UP else voltage_up[::-1]
        current = current_up if direction is SweepDirection.UP else current_up[::-1]
        start = index * point_count
        time_s = np.arange(start, start + point_count, dtype=np.float64) * 1e-5
        sweeps.append(
            Sweep(
                sweep_id=f"benchmark/voltage:{start}:{start + point_count}",
                current_series_id="benchmark/current",
                voltage_series_id="benchmark/voltage",
                source_start_index=start,
                source_stop_index=start + point_count,
                direction=direction,
                time_s=time_s,
                voltage_v=voltage,
                current_a=current,
            )
        )
    return tuple(sweeps)


def _aligned_signals(*, cycle_count: int) -> AlignedSignals:
    cycle = np.asarray([-3, -2, -1, 0, 1, 2, 3, 2], dtype=np.float64)
    voltage = np.tile(cycle, cycle_count)
    time_s = np.arange(voltage.size, dtype=np.float64) * 1e-5
    return AlignedSignals(
        current_series_id="benchmark/current",
        voltage_series_id="benchmark/voltage",
        time_s=time_s,
        current_a=0.002 * voltage,
        sweep_voltage_v=voltage,
        voltage_source_start_index=0,
        interpolated_current=False,
    )


def _summary(values: list[float]) -> TimingSummary:
    return TimingSummary(
        iterations=len(values),
        median_ms=round(statistics.median(values), 3),
        p95_ms=round(float(np.percentile(values, 95)), 3),
        maximum_ms=round(max(values), 3),
    )


if __name__ == "__main__":
    main()
