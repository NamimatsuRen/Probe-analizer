from __future__ import annotations

import numpy as np
import pytest

from probe_app.domain.errors import SignalAlignmentError, SignalAlignmentFailure
from probe_app.domain.models.series_role import PhysicalSignal, SeriesRole
from probe_app.domain.services.signal_alignment import align_current_and_voltage


def _physical(
    role: SeriesRole,
    series_id: str,
    unit: str,
    time_s: list[float],
    values: list[float],
) -> PhysicalSignal:
    return PhysicalSignal(
        role=role,
        series_id=series_id,
        unit=unit,
        time_s=np.asarray(time_s, dtype=np.float64),
        values=np.asarray(values, dtype=np.float64),
    )


def test_equal_axes_are_reused_without_interpolation() -> None:
    current = _physical(SeriesRole.CURRENT, "i", "A", [0, 1, 2], [10, 20, 30])
    voltage = _physical(
        SeriesRole.SWEEP_VOLTAGE,
        "v",
        "V",
        [0, 1, 2],
        [-1, 0, 1],
    )

    aligned = align_current_and_voltage(current, voltage)

    assert not aligned.interpolated_current
    assert aligned.voltage_source_start_index == 0
    np.testing.assert_allclose(aligned.current_a, [10, 20, 30])


def test_current_is_interpolated_only_on_overlapping_voltage_samples() -> None:
    current = _physical(
        SeriesRole.CURRENT,
        "i",
        "A",
        [0.5, 1.5, 2.5, 3.5],
        [5, 15, 25, 35],
    )
    voltage = _physical(
        SeriesRole.SWEEP_VOLTAGE,
        "v",
        "V",
        [0, 1, 2, 3, 4],
        [-2, -1, 0, 1, 2],
    )

    aligned = align_current_and_voltage(current, voltage)

    assert aligned.interpolated_current
    assert aligned.voltage_source_start_index == 1
    np.testing.assert_allclose(aligned.time_s, [1, 2, 3])
    np.testing.assert_allclose(aligned.current_a, [10, 20, 30])
    np.testing.assert_allclose(aligned.sweep_voltage_v, [-1, 0, 1])


def test_positive_offset_reads_current_later_than_voltage_reference() -> None:
    current = _physical(
        SeriesRole.CURRENT,
        "i",
        "A",
        [0, 1, 2, 3],
        [0, 10, 20, 30],
    )
    voltage = _physical(
        SeriesRole.SWEEP_VOLTAGE,
        "v",
        "V",
        [0, 1, 2, 3],
        [-1, 0, 1, 2],
    )

    aligned = align_current_and_voltage(
        current,
        voltage,
        current_time_offset_s=0.5,
    )

    assert aligned.interpolated_current
    assert aligned.current_time_offset_s == 0.5
    assert aligned.voltage_source_start_index == 0
    np.testing.assert_allclose(aligned.time_s, [0, 1, 2])
    np.testing.assert_allclose(aligned.current_a, [5, 15, 25])
    np.testing.assert_allclose(aligned.sweep_voltage_v, [-1, 0, 1])


def test_negative_offset_removes_voltage_before_current_lookup_range() -> None:
    current = _physical(
        SeriesRole.CURRENT,
        "i",
        "A",
        [0, 1, 2, 3],
        [0, 10, 20, 30],
    )
    voltage = _physical(
        SeriesRole.SWEEP_VOLTAGE,
        "v",
        "V",
        [0, 1, 2, 3],
        [-1, 0, 1, 2],
    )

    aligned = align_current_and_voltage(
        current,
        voltage,
        current_time_offset_s=-0.5,
    )

    assert aligned.voltage_source_start_index == 1
    np.testing.assert_allclose(aligned.time_s, [1, 2, 3])
    np.testing.assert_allclose(aligned.current_a, [5, 15, 25])
    np.testing.assert_allclose(aligned.sweep_voltage_v, [0, 1, 2])


def test_offset_that_removes_overlap_reports_a_typed_failure() -> None:
    current = _physical(SeriesRole.CURRENT, "i", "A", [0, 1], [0, 1])
    voltage = _physical(
        SeriesRole.SWEEP_VOLTAGE,
        "v",
        "V",
        [0, 1],
        [0, 1],
    )

    with pytest.raises(SignalAlignmentError) as caught:
        align_current_and_voltage(
            current,
            voltage,
            current_time_offset_s=2.0,
        )

    assert caught.value.failure is SignalAlignmentFailure.NO_TIME_OVERLAP


def test_disjoint_time_ranges_report_a_typed_failure() -> None:
    current = _physical(SeriesRole.CURRENT, "i", "A", [0, 1], [0, 1])
    voltage = _physical(
        SeriesRole.SWEEP_VOLTAGE,
        "v",
        "V",
        [2, 3],
        [0, 1],
    )

    with pytest.raises(SignalAlignmentError) as caught:
        align_current_and_voltage(current, voltage)

    assert caught.value.failure is SignalAlignmentFailure.NO_TIME_OVERLAP


def test_non_monotonic_time_reports_a_typed_failure() -> None:
    current = _physical(SeriesRole.CURRENT, "i", "A", [0, 1, 1], [0, 1, 2])
    voltage = _physical(
        SeriesRole.SWEEP_VOLTAGE,
        "v",
        "V",
        [0, 1, 2],
        [0, 1, 2],
    )

    with pytest.raises(SignalAlignmentError) as caught:
        align_current_and_voltage(current, voltage)

    assert caught.value.failure is SignalAlignmentFailure.NON_MONOTONIC_TIME
