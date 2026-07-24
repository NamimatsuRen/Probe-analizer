from __future__ import annotations

import numpy as np
import pytest

from probe_app.domain.errors import SweepSplitError, SweepSplitFailure
from probe_app.domain.models.sweep import SweepDirection, SweepExclusionReason
from probe_app.domain.services.signal_alignment import AlignedSignals
from probe_app.domain.services.sweep_splitter import (
    LegacySweepSplitParameters,
    split_legacy_sweeps,
    split_legacy_sweeps_with_diagnostics,
)


def _aligned(voltage: list[float], *, source_offset: int = 0) -> AlignedSignals:
    count = len(voltage)
    return AlignedSignals(
        current_series_id="current",
        voltage_series_id="voltage",
        time_s=np.arange(count, dtype=np.float64) * 0.1,
        current_a=np.arange(count, dtype=np.float64),
        sweep_voltage_v=np.asarray(voltage, dtype=np.float64),
        voltage_source_start_index=source_offset,
        interpolated_current=False,
    )


def test_golden_legacy_boundaries_directions_and_iv_order() -> None:
    # Three identical 8-point cycles. Legacy alignment discards one full cycle,
    # then returns four 4-point half-cycles from the remaining two cycles.
    cycle = [0, 1, 2, 3, 4, 3, 2, 1]
    signals = _aligned(cycle * 3, source_offset=100)

    sweeps = split_legacy_sweeps(
        signals,
        LegacySweepSplitParameters(points_per_cycle=8),
    )

    assert len(sweeps) == 4
    assert [
        (sweep.source_start_index, sweep.source_stop_index)
        for sweep in sweeps
    ] == [(100, 104), (104, 108), (108, 112), (112, 116)]
    assert [sweep.direction for sweep in sweeps] == [
        SweepDirection.UP,
        SweepDirection.DOWN,
        SweepDirection.UP,
        SweepDirection.DOWN,
    ]
    np.testing.assert_allclose(sweeps[0].iv_voltage_v, [0, 1, 2, 3])
    np.testing.assert_allclose(sweeps[1].iv_voltage_v, [1, 2, 3, 4])
    np.testing.assert_allclose(sweeps[1].iv_current_a, [7, 6, 5, 4])


def test_first_cycle_minimum_sets_the_source_boundary() -> None:
    cycle = [2, 1, 0, 1, 2, 3, 4, 3]
    signals = _aligned(cycle * 3, source_offset=10)

    sweeps = split_legacy_sweeps(
        signals,
        LegacySweepSplitParameters(points_per_cycle=8),
    )

    assert sweeps[0].source_start_index == 12
    assert sweeps[-1].source_stop_index == 28


def test_explicit_sample_window_replaces_legacy_json_time_range() -> None:
    padding = [99, 99, 99, 99]
    cycle = [0, 1, 2, 3, 4, 3, 2, 1]
    signals = _aligned(padding + cycle * 3 + padding)

    sweeps = split_legacy_sweeps(
        signals,
        LegacySweepSplitParameters(
            points_per_cycle=8,
            sample_start=4,
            sample_stop=28,
        ),
    )

    assert len(sweeps) == 4
    assert sweeps[0].source_start_index == 4
    assert sweeps[-1].source_stop_index == 20


def test_odd_cycle_length_reports_a_typed_failure() -> None:
    signals = _aligned([0, 1, 2, 1] * 3)

    with pytest.raises(SweepSplitError) as caught:
        split_legacy_sweeps(
            signals,
            LegacySweepSplitParameters(points_per_cycle=3),
        )

    assert caught.value.failure is SweepSplitFailure.INVALID_PARAMETERS


def test_partial_half_cycle_is_not_silently_dropped() -> None:
    signals = _aligned([0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 2])

    with pytest.raises(SweepSplitError) as caught:
        split_legacy_sweeps(
            signals,
            LegacySweepSplitParameters(points_per_cycle=6),
        )

    assert caught.value.failure is SweepSplitFailure.MISALIGNED_WINDOW


def test_diagnostics_retains_valid_sweeps_and_every_excluded_interval() -> None:
    signals = _aligned(
        [2, 1, 0, 1, 2, 3, 4, 3] * 3 + [2, 1],
        source_offset=100,
    )

    diagnostics = split_legacy_sweeps_with_diagnostics(
        signals,
        LegacySweepSplitParameters(points_per_cycle=8),
    )

    assert [
        (sweep.source_start_index, sweep.source_stop_index)
        for sweep in diagnostics.sweeps
    ] == [
        (102, 106),
        (106, 110),
        (110, 114),
        (114, 118),
    ]
    assert [
        (
            exclusion.source_start_index,
            exclusion.source_stop_index,
            exclusion.reason,
        )
        for exclusion in diagnostics.exclusions
    ] == [
        (100, 102, SweepExclusionReason.ALIGNMENT_PREFIX),
        (118, 120, SweepExclusionReason.INCOMPLETE_SWEEP),
        (120, 126, SweepExclusionReason.ALIGNMENT_SUFFIX),
    ]
    assert sum(item.point_count for item in diagnostics.exclusions) == 10


def test_golden_boundaries_allow_zero_sample_error() -> None:
    cycle = [0, 1, 2, 3, 4, 3, 2, 1]
    signals = _aligned(cycle * 3, source_offset=100)
    expected_boundaries = ((100, 104), (104, 108), (108, 112), (112, 116))

    diagnostics = split_legacy_sweeps_with_diagnostics(
        signals,
        LegacySweepSplitParameters(points_per_cycle=8),
    )
    actual_boundaries = tuple(
        (sweep.source_start_index, sweep.source_stop_index)
        for sweep in diagnostics.sweeps
    )

    boundary_errors = tuple(
        max(abs(actual_start - expected_start), abs(actual_stop - expected_stop))
        for (actual_start, actual_stop), (expected_start, expected_stop) in zip(
            actual_boundaries,
            expected_boundaries,
            strict=True,
        )
    )
    assert boundary_errors == (0, 0, 0, 0)
    assert [sweep.direction for sweep in diagnostics.sweeps] == [
        SweepDirection.UP,
        SweepDirection.DOWN,
        SweepDirection.UP,
        SweepDirection.DOWN,
    ]
