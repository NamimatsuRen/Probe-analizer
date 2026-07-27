from __future__ import annotations

from pathlib import Path

import pytest

from probe_app.domain.models.catalog import FolderCatalog
from probe_app.domain.models.raw_series import RawSeriesDescriptor
from probe_app.domain.models.series_role import (
    AssignedSeries,
    SeriesRole,
    SeriesRoleAssignments,
    SignalTransform,
)
from probe_app.domain.services import (
    AssignmentApplyScope,
    propagate_role_assignments,
)


def _descriptor(shot_id: str, channel_id: str, *, suffix: str = "") -> RawSeriesDescriptor:
    series_id = f"{shot_id}/{channel_id}{suffix}"
    return RawSeriesDescriptor(
        series_id=series_id,
        shot_id=shot_id,
        channel_id=channel_id,
        header_path=Path(f"/data/{series_id}.hdr"),
        data_path=Path(f"/data/{series_id}.dat"),
        sample_count=100,
        value_unit="V",
        time_unit="s",
    )


def _assignments(shot_id: str) -> SeriesRoleAssignments:
    return SeriesRoleAssignments(
        (
            AssignedSeries(
                role=SeriesRole.CURRENT,
                series_id=f"{shot_id}/current-channel",
                transform=SignalTransform(
                    scale=0.05,
                    sign=-1.0,
                    output_unit="A",
                ),
            ),
            AssignedSeries(
                role=SeriesRole.SWEEP_VOLTAGE,
                series_id=f"{shot_id}/voltage-channel",
                transform=SignalTransform(
                    scale=100.0,
                    sign=1.0,
                    output_unit="V",
                ),
            ),
        )
    )


def _catalog(*shots: str) -> FolderCatalog:
    descriptors = tuple(
        descriptor
        for shot_id in shots
        for descriptor in (
            _descriptor(shot_id, "current-channel"),
            _descriptor(shot_id, "voltage-channel"),
        )
    )
    return FolderCatalog(root=Path("/data"), series=descriptors)


def test_all_scope_maps_roles_by_channel_and_preserves_transforms() -> None:
    source = _assignments("shot-002")

    result = propagate_role_assignments(
        _catalog("shot-001", "shot-002", "shot-003"),
        "shot-002",
        source,
        AssignmentApplyScope.ALL,
    )

    assert tuple(item.shot_id for item in result.assignments) == (
        "shot-001",
        "shot-002",
        "shot-003",
    )
    assert result.failures == ()
    target = result.assignments[-1].assignments
    assert target.for_role(SeriesRole.CURRENT) == AssignedSeries(
        role=SeriesRole.CURRENT,
        series_id="shot-003/current-channel",
        transform=source.for_role(SeriesRole.CURRENT).transform,  # type: ignore[union-attr]
    )
    assert target.for_role(SeriesRole.SWEEP_VOLTAGE) == AssignedSeries(
        role=SeriesRole.SWEEP_VOLTAGE,
        series_id="shot-003/voltage-channel",
        transform=source.for_role(SeriesRole.SWEEP_VOLTAGE).transform,  # type: ignore[union-attr]
    )


def test_remaining_scope_starts_at_the_active_shot() -> None:
    result = propagate_role_assignments(
        _catalog("shot-001", "shot-002", "shot-003"),
        "shot-002",
        _assignments("shot-002"),
        AssignmentApplyScope.REMAINING,
    )

    assert tuple(item.shot_id for item in result.assignments) == (
        "shot-002",
        "shot-003",
    )


def test_missing_or_ambiguous_channel_skips_the_whole_target() -> None:
    catalog = FolderCatalog(
        root=Path("/data"),
        series=(
            _descriptor("shot-001", "current-channel"),
            _descriptor("shot-001", "voltage-channel"),
            _descriptor("shot-002", "current-channel"),
            _descriptor("shot-003", "current-channel"),
            _descriptor("shot-003", "voltage-channel"),
            _descriptor("shot-003", "voltage-channel", suffix="-duplicate"),
        ),
    )

    result = propagate_role_assignments(
        catalog,
        "shot-001",
        _assignments("shot-001"),
        AssignmentApplyScope.ALL,
    )

    assert tuple(item.shot_id for item in result.assignments) == ("shot-001",)
    assert tuple(failure.shot_id for failure in result.failures) == (
        "shot-002",
        "shot-003",
    )
    assert "ありません" in result.failures[0].reason
    assert "複数あります" in result.failures[1].reason


def test_incomplete_source_is_rejected() -> None:
    with pytest.raises(ValueError, match="complete role assignments"):
        propagate_role_assignments(
            _catalog("shot-001"),
            "shot-001",
            SeriesRoleAssignments(),
            AssignmentApplyScope.CURRENT,
        )
