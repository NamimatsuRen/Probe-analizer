from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from probe_app.domain.models.catalog import FolderCatalog
from probe_app.domain.models.series_role import (
    AssignedSeries,
    SeriesRole,
    SeriesRoleAssignments,
)


class AssignmentApplyScope(StrEnum):
    """Shots that receive the active shot's role configuration."""

    CURRENT = "current"
    REMAINING = "remaining"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class ShotRoleAssignments:
    shot_id: str
    assignments: SeriesRoleAssignments


@dataclass(frozen=True, slots=True)
class AssignmentPropagationFailure:
    shot_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class AssignmentPropagationResult:
    assignments: tuple[ShotRoleAssignments, ...]
    failures: tuple[AssignmentPropagationFailure, ...]

    @property
    def applied_count(self) -> int:
        return len(self.assignments)

    @property
    def skipped_count(self) -> int:
        return len(self.failures)


def propagate_role_assignments(
    catalog: FolderCatalog,
    source_shot_id: str,
    source_assignments: SeriesRoleAssignments,
    scope: AssignmentApplyScope,
) -> AssignmentPropagationResult:
    """Map role assignments to target shots by channel ID.

    A complete target assignment is produced only when every source role has
    exactly one channel-ID match in the target shot. A missing or ambiguous
    match skips the whole target, so an existing saved configuration is never
    partially overwritten.
    """

    if not source_assignments.is_complete:
        raise ValueError("complete role assignments are required for bulk application")

    shots = catalog.shots
    if source_shot_id not in shots:
        raise ValueError(f"unknown source shot: {source_shot_id}")

    source_channels: dict[SeriesRole, str] = {}
    for role in SeriesRole:
        assignment = source_assignments.for_role(role)
        if assignment is None:  # pragma: no cover - guarded by is_complete
            raise ValueError(f"{role.value} is not assigned")
        descriptor = catalog.find(assignment.series_id)
        if descriptor is None or descriptor.shot_id != source_shot_id:
            raise ValueError(
                f"{role.value} series is outside source shot: {assignment.series_id}"
            )
        source_channels[role] = descriptor.channel_id

    target_shots = _target_shots(shots, source_shot_id, scope)
    propagated: list[ShotRoleAssignments] = []
    failures: list[AssignmentPropagationFailure] = []

    for shot_id in target_shots:
        descriptors = catalog.series_for_shot(shot_id)
        target_items: list[AssignedSeries] = []
        failure_reason = ""
        for role in SeriesRole:
            channel_id = source_channels[role]
            matches = tuple(
                descriptor
                for descriptor in descriptors
                if descriptor.channel_id == channel_id
            )
            if not matches:
                failure_reason = (
                    f"{role.value}のchannel「{channel_id}」がありません"
                )
                break
            if len(matches) > 1:
                failure_reason = (
                    f"{role.value}のchannel「{channel_id}」が複数あります"
                )
                break
            source_assignment = source_assignments.for_role(role)
            if source_assignment is None:  # pragma: no cover - guarded above
                raise ValueError(f"{role.value} is not assigned")
            target_items.append(
                AssignedSeries(
                    role=role,
                    series_id=matches[0].series_id,
                    transform=source_assignment.transform,
                )
            )

        if failure_reason:
            failures.append(
                AssignmentPropagationFailure(
                    shot_id=shot_id,
                    reason=failure_reason,
                )
            )
            continue

        try:
            assignments = SeriesRoleAssignments(tuple(target_items))
        except ValueError as error:
            failures.append(
                AssignmentPropagationFailure(
                    shot_id=shot_id,
                    reason=f"役割を一意に割り当てられません: {error}",
                )
            )
            continue
        propagated.append(
            ShotRoleAssignments(
                shot_id=shot_id,
                assignments=assignments,
            )
        )

    return AssignmentPropagationResult(
        assignments=tuple(propagated),
        failures=tuple(failures),
    )


def _target_shots(
    shots: tuple[str, ...],
    source_shot_id: str,
    scope: AssignmentApplyScope,
) -> tuple[str, ...]:
    if scope is AssignmentApplyScope.CURRENT:
        return (source_shot_id,)
    if scope is AssignmentApplyScope.ALL:
        return shots
    source_index = shots.index(source_shot_id)
    return shots[source_index:]
