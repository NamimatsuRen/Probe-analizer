from __future__ import annotations

import argparse
import resource
import time
from pathlib import Path

from probe_app.application.use_cases import OpenFolder
from probe_app.infrastructure.readers.panta_reader import PantaRawReader
from probe_app.ui.downsampling import min_max_downsample


def megabytes_from_max_rss(value: int) -> float:
    # macOS reports bytes; Linux reports KiB.
    if value > 10_000_000:
        return value / 1024**2
    return value / 1024


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure Level 1 folder and waveform loading")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--series", help="series_id to load; defaults to the first series")
    args = parser.parse_args()

    scan_start = time.perf_counter()
    catalog = OpenFolder().execute(args.folder)
    scan_seconds = time.perf_counter() - scan_start

    print(f"folder={catalog.root}")
    print(f"shots={len(catalog.shots)}")
    print(f"series={len(catalog.series)}")
    print(f"problems={len(catalog.problems)}")
    print(f"scan_seconds={scan_seconds:.6f}")

    if catalog.is_empty:
        return 1
    descriptor = catalog.find(args.series) if args.series else catalog.series[0]
    if descriptor is None:
        raise SystemExit(f"series_id not found: {args.series}")

    read_start = time.perf_counter()
    series = PantaRawReader().read(descriptor)
    read_seconds = time.perf_counter() - read_start

    display_start = time.perf_counter()
    display_x, _ = min_max_downsample(series.time_s, series.values)
    display_seconds = time.perf_counter() - display_start

    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"selected={descriptor.series_id}")
    print(f"points={series.point_count}")
    print(f"display_points={display_x.size}")
    print(f"read_seconds={read_seconds:.6f}")
    print(f"downsample_seconds={display_seconds:.6f}")
    print(f"peak_rss_mb={megabytes_from_max_rss(max_rss):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
