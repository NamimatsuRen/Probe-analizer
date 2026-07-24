from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from probe_app.application.use_cases import (
    OpenFolder,
    SplitSweeps,
    SweepSplitRequest,
)
from probe_app.domain.errors import OperationCancelled
from probe_app.domain.models import (
    AssignedSeries,
    SeriesRole,
    SeriesRoleAssignments,
    SignalTransform,
)
from probe_app.domain.services.sweep_splitter import LegacySweepSplitParameters
from tests.conftest import write_panta_series


def _request(tmp_path: Path) -> SweepSplitRequest:
    current_samples = np.arange(32, dtype=np.int16)
    voltage_cycle = np.asarray([-3, -2, -1, 0, 1, 2, 3, 2], dtype=np.int16)
    voltage_samples = np.tile(voltage_cycle, 4)
    shot = tmp_path / "shot-001"
    write_panta_series(
        shot,
        "current",
        samples=current_samples,
        resolution=1.0,
        offset=0.0,
        time_resolution=0.01,
        time_offset=0.0,
    )
    write_panta_series(
        shot,
        "voltage",
        samples=voltage_samples,
        resolution=1.0,
        offset=0.0,
        time_resolution=0.01,
        time_offset=0.0,
    )
    catalog = OpenFolder().execute(tmp_path)
    current = catalog.find("shot-001/current")
    voltage = catalog.find("shot-001/voltage")
    assert current is not None
    assert voltage is not None
    assignments = SeriesRoleAssignments(
        (
            AssignedSeries(
                role=SeriesRole.CURRENT,
                series_id=current.series_id,
                transform=SignalTransform(scale=1.0, sign=1.0, output_unit="A"),
            ),
            AssignedSeries(
                role=SeriesRole.SWEEP_VOLTAGE,
                series_id=voltage.series_id,
                transform=SignalTransform(scale=1.0, sign=1.0, output_unit="V"),
            ),
        )
    )
    return SweepSplitRequest(
        current_descriptor=current,
        voltage_descriptor=voltage,
        assignments=assignments,
        parameters=LegacySweepSplitParameters(points_per_cycle=8),
    )


def test_folder_assigned_series_are_loaded_aligned_and_split(tmp_path: Path) -> None:
    result = SplitSweeps().execute(_request(tmp_path))

    assert result.sweep_count == 6
    assert not result.interpolated_current
    assert result.current_series_id == "shot-001/current"
    assert result.voltage_series_id == "shot-001/voltage"
    assert [sweep.source_start_index for sweep in result.sweeps] == [
        0,
        4,
        8,
        12,
        16,
        20,
    ]


def test_split_can_be_cancelled_before_loading(tmp_path: Path) -> None:
    with pytest.raises(OperationCancelled):
        SplitSweeps().execute(_request(tmp_path), is_cancelled=lambda: True)
