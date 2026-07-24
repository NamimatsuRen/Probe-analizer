from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from probe_app.domain.models.raw_series import RawSeries, RawSeriesDescriptor
from probe_app.domain.models.series_role import (
    AssignedSeries,
    SeriesRole,
    SeriesRoleAssignments,
    SignalTransform,
    legacy_current_transform,
    legacy_sweep_voltage_transform,
)


def _series(series_id: str, values: list[float]) -> RawSeries:
    descriptor = RawSeriesDescriptor(
        series_id=series_id,
        shot_id="shot-1",
        channel_id=series_id,
        header_path=Path(f"{series_id}.hdr"),
        data_path=Path(f"{series_id}.wvf"),
        sample_count=len(values),
        value_unit="V",
        time_unit="s",
    )
    return RawSeries(
        descriptor=descriptor,
        time_s=np.arange(len(values), dtype=np.float64),
        values=np.asarray(values, dtype=np.float64),
    )


def test_unassigned_roles_are_explicit() -> None:
    assignments = SeriesRoleAssignments()

    assert not assignments.is_complete
    assert assignments.unassigned_roles == (
        SeriesRole.CURRENT,
        SeriesRole.SWEEP_VOLTAGE,
    )


def test_assigns_roles_without_using_basenames() -> None:
    current = AssignedSeries(
        role=SeriesRole.CURRENT,
        series_id="arbitrary-channel-a",
        transform=legacy_current_transform(sign=-1.0),
    )
    voltage = AssignedSeries(
        role=SeriesRole.SWEEP_VOLTAGE,
        series_id="arbitrary-channel-b",
        transform=legacy_sweep_voltage_transform(),
    )

    assignments = SeriesRoleAssignments().assign(current).assign(voltage)

    assert assignments.is_complete
    assert assignments.for_role(SeriesRole.CURRENT) == current
    assert assignments.unassigned_roles == ()


def test_legacy_transforms_are_explicit_and_preserve_raw_values() -> None:
    raw_current = _series("channel-a", [20.0, -40.0])
    assignment = AssignedSeries(
        role=SeriesRole.CURRENT,
        series_id="channel-a",
        transform=legacy_current_transform(sign=-1.0),
    )

    physical = SeriesRoleAssignments((assignment,)).prepare(
        SeriesRole.CURRENT,
        raw_current,
    )

    np.testing.assert_allclose(physical.values, [-1.0, 2.0])
    np.testing.assert_allclose(raw_current.values, [20.0, -40.0])
    assert physical.unit == "A"


def test_legacy_sweep_voltage_scale_is_reproducible() -> None:
    transform = legacy_sweep_voltage_transform()

    np.testing.assert_allclose(
        transform.apply(np.asarray([0.1, -0.25], dtype=np.float64)),
        [10.0, -25.0],
    )
    assert transform.output_unit == "V"


def test_rejects_duplicate_series_assignment() -> None:
    transform = SignalTransform(scale=1.0, sign=1.0, output_unit="A")

    with pytest.raises(ValueError, match="multiple roles"):
        SeriesRoleAssignments(
            (
                AssignedSeries(SeriesRole.CURRENT, "same", transform),
                AssignedSeries(SeriesRole.SWEEP_VOLTAGE, "same", transform),
            )
        )
