from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from probe_app.domain.errors import SweepSplitError, SweepSplitFailure
from probe_app.domain.models.sweep import (
    Sweep,
    SweepDirection,
    SweepExclusion,
    SweepExclusionReason,
)
from probe_app.domain.services.signal_alignment import AlignedSignals

DEFAULT_ANALYSIS_SAMPLE_START = 200_000
DEFAULT_ANALYSIS_SAMPLE_STOP = 500_000


@dataclass(frozen=True, slots=True)
class LegacySweepSplitParameters:
    """Explicit inputs formerly supplied by the legacy JSON configuration."""

    points_per_cycle: int
    sample_start: int = DEFAULT_ANALYSIS_SAMPLE_START
    sample_stop: int | None = DEFAULT_ANALYSIS_SAMPLE_STOP


@dataclass(frozen=True, slots=True)
class SweepSplitDiagnostics:
    """Valid Sweeps plus every source interval excluded by legacy alignment."""

    sweeps: tuple[Sweep, ...]
    exclusions: tuple[SweepExclusion, ...]


def _validated_window(
    signals: AlignedSignals,
    parameters: LegacySweepSplitParameters,
) -> tuple[int, int, int]:
    points_per_cycle = parameters.points_per_cycle
    if points_per_cycle < 2 or points_per_cycle % 2:
        raise SweepSplitError(
            SweepSplitFailure.INVALID_PARAMETERS,
            "points_per_cycle must be an even integer of at least 2",
        )
    stop = signals.time_s.size if parameters.sample_stop is None else parameters.sample_stop
    if parameters.sample_start < 0 or stop <= parameters.sample_start:
        raise SweepSplitError(
            SweepSplitFailure.INVALID_SAMPLE_WINDOW,
            "sample window must be a non-empty half-open interval",
        )
    if stop > signals.time_s.size:
        raise SweepSplitError(
            SweepSplitFailure.INVALID_SAMPLE_WINDOW,
            f"sample_stop {stop} exceeds aligned length {signals.time_s.size}",
        )
    if stop - parameters.sample_start <= points_per_cycle:
        raise SweepSplitError(
            SweepSplitFailure.INSUFFICIENT_DATA,
            "legacy alignment discards one full cycle, leaving no complete sweep",
        )
    return parameters.sample_start, stop, points_per_cycle


def split_legacy_sweeps(
    signals: AlignedSignals,
    parameters: LegacySweepSplitParameters,
) -> tuple[Sweep, ...]:
    """Reproduce the old minimum-aligned half-cycle split as a pure function.

    The first minimum within one full cycle sets the leading boundary. The
    complementary part of that cycle is removed from the end, matching the old
    ``sweep_sort`` behavior. Incomplete half-cycles are rejected explicitly.
    """

    diagnostics = split_legacy_sweeps_with_diagnostics(signals, parameters)
    incomplete = next(
        (
            exclusion
            for exclusion in diagnostics.exclusions
            if exclusion.reason is SweepExclusionReason.INCOMPLETE_SWEEP
        ),
        None,
    )
    if incomplete is not None:
        half_cycle = parameters.points_per_cycle // 2
        raise SweepSplitError(
            SweepSplitFailure.MISALIGNED_WINDOW,
            (
                f"{incomplete.point_count} usable points remain after complete "
                f"half-cycles of {half_cycle} points"
            ),
        )
    return diagnostics.sweeps


def split_legacy_sweeps_with_diagnostics(
    signals: AlignedSignals,
    parameters: LegacySweepSplitParameters,
) -> SweepSplitDiagnostics:
    """Split complete Sweeps and retain every excluded source interval."""

    window_start, window_stop, points_per_cycle = _validated_window(signals, parameters)
    half_cycle = points_per_cycle // 2
    first_cycle = signals.sweep_voltage_v[
        window_start : window_start + points_per_cycle
    ]
    minimum_offset = int(np.argmin(first_cycle))

    aligned_start = window_start + minimum_offset
    aligned_stop = window_stop - (points_per_cycle - minimum_offset)
    usable_points = aligned_stop - aligned_start
    if usable_points < half_cycle:
        raise SweepSplitError(
            SweepSplitFailure.INSUFFICIENT_DATA,
            "minimum alignment leaves fewer than one half-cycle",
        )
    remainder = usable_points % half_cycle
    complete_stop = aligned_stop - remainder

    sweeps: list[Sweep] = []
    source_offset = signals.voltage_source_start_index
    for index, local_start in enumerate(range(aligned_start, complete_stop, half_cycle)):
        local_stop = local_start + half_cycle
        source_start = source_offset + local_start
        source_stop = source_offset + local_stop
        direction = SweepDirection.UP if index % 2 == 0 else SweepDirection.DOWN
        sweeps.append(
            Sweep(
                sweep_id=f"{signals.voltage_series_id}:{source_start}:{source_stop}",
                current_series_id=signals.current_series_id,
                voltage_series_id=signals.voltage_series_id,
                source_start_index=source_start,
                source_stop_index=source_stop,
                direction=direction,
                time_s=np.asarray(signals.time_s[local_start:local_stop], dtype=np.float64),
                voltage_v=np.asarray(
                    signals.sweep_voltage_v[local_start:local_stop],
                    dtype=np.float64,
                ),
                current_a=np.asarray(
                    signals.current_a[local_start:local_stop],
                    dtype=np.float64,
                ),
                current_time_offset_s=signals.current_time_offset_s,
            )
        )

    exclusions: list[SweepExclusion] = []
    if aligned_start > window_start:
        exclusions.append(
            _exclusion(
                signals,
                window_start,
                aligned_start,
                SweepExclusionReason.ALIGNMENT_PREFIX,
                "先頭を最初の最小電圧へ揃えるため除外",
            )
        )
    if complete_stop < aligned_stop:
        exclusions.append(
            _exclusion(
                signals,
                complete_stop,
                aligned_stop,
                SweepExclusionReason.INCOMPLETE_SWEEP,
                f"{half_cycle}点のSweepに満たない端数のため除外",
            )
        )
    if aligned_stop < window_stop:
        exclusions.append(
            _exclusion(
                signals,
                aligned_stop,
                window_stop,
                SweepExclusionReason.ALIGNMENT_SUFFIX,
                "旧方式の周期境界を保つため末尾を除外",
            )
        )
    return SweepSplitDiagnostics(tuple(sweeps), tuple(exclusions))


def _exclusion(
    signals: AlignedSignals,
    local_start: int,
    local_stop: int,
    reason: SweepExclusionReason,
    detail: str,
) -> SweepExclusion:
    source_offset = signals.voltage_source_start_index
    return SweepExclusion(
        voltage_series_id=signals.voltage_series_id,
        source_start_index=source_offset + local_start,
        source_stop_index=source_offset + local_stop,
        start_time_s=float(signals.time_s[local_start]),
        end_time_s=float(signals.time_s[local_stop - 1]),
        reason=reason,
        detail=detail,
    )
