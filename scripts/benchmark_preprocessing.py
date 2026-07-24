from __future__ import annotations

import argparse
import statistics
import time

import numpy as np

from probe_app.analysis import SavitzkyGolaySettings, preprocess_sweep
from probe_app.domain.models.sweep import Sweep, SweepDirection


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark one selected-Sweep SG smoothing and derivative run."
    )
    parser.add_argument("--points", type=int, default=10_000)
    parser.add_argument("--repeat", type=int, default=100)
    parser.add_argument("--window", type=int, default=501)
    arguments = parser.parse_args()

    voltage_v = np.linspace(-50.0, 50.0, arguments.points, dtype=np.float64)
    rng = np.random.default_rng(20260724)
    current_a = 0.02 * np.tanh(voltage_v / 4.0) + rng.normal(
        0.0,
        0.0002,
        arguments.points,
    )
    sweep = Sweep(
        sweep_id="benchmark/voltage:0:end",
        current_series_id="benchmark/current",
        voltage_series_id="benchmark/voltage",
        source_start_index=0,
        source_stop_index=arguments.points,
        direction=SweepDirection.UP,
        time_s=np.arange(arguments.points, dtype=np.float64) * 1e-6,
        voltage_v=voltage_v,
        current_a=current_a,
    )
    settings = SavitzkyGolaySettings(
        window_length=arguments.window,
        polyorder=3,
    )

    preprocess_sweep(sweep, settings)
    elapsed_ms: list[float] = []
    for _ in range(arguments.repeat):
        started = time.perf_counter()
        preprocess_sweep(sweep, settings)
        elapsed_ms.append((time.perf_counter() - started) * 1_000.0)

    sorted_elapsed = sorted(elapsed_ms)
    p95_index = max(0, int(len(sorted_elapsed) * 0.95) - 1)
    print(
        f"points={arguments.points:,} window={arguments.window:,} "
        f"repeat={arguments.repeat:,}"
    )
    print(f"median_ms={statistics.median(elapsed_ms):.3f}")
    print(f"p95_ms={sorted_elapsed[p95_index]:.3f}")
    print(f"max_ms={max(elapsed_ms):.3f}")


if __name__ == "__main__":
    main()
