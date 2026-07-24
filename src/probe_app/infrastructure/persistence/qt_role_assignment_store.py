from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QSettings

from probe_app.domain.errors import RoleAssignmentStoreError
from probe_app.domain.models.series_role import (
    AssignedSeries,
    SeriesRole,
    SeriesRoleAssignments,
    SignalTransform,
)


class QSettingsRoleAssignmentStore:
    """Store role configuration in app preferences, never in measurement data."""

    def __init__(self, settings: QSettings) -> None:
        self._settings = settings

    @staticmethod
    def _group_key(folder: Path, shot_id: str) -> str:
        normalized = str(folder.expanduser().resolve(strict=False))
        digest = hashlib.sha256(f"{normalized}\0{shot_id}".encode()).hexdigest()
        return f"roleAssignments/{digest}"

    def load(self, folder: Path, shot_id: str) -> SeriesRoleAssignments:
        self._settings.beginGroup(self._group_key(folder, shot_id))
        try:
            items = tuple(
                assignment
                for role in SeriesRole
                if (assignment := self._read_assignment(role)) is not None
            )
            assignments = SeriesRoleAssignments(items)
        except (TypeError, ValueError) as error:
            raise RoleAssignmentStoreError(
                f"{shot_id} の保存済み役割設定を読み込めません: {error}"
            ) from error
        finally:
            self._settings.endGroup()
        if self._settings.status() is not QSettings.Status.NoError:
            raise RoleAssignmentStoreError(
                f"{shot_id} の役割設定をアプリ設定から読み込めません"
            )
        return assignments

    def save(
        self,
        folder: Path,
        shot_id: str,
        assignments: SeriesRoleAssignments,
    ) -> None:
        self._settings.beginGroup(self._group_key(folder, shot_id))
        try:
            self._settings.remove("")
            self._settings.setValue("folder", str(folder.expanduser().resolve(strict=False)))
            self._settings.setValue("shotId", shot_id)
            for assignment in assignments.items:
                prefix = assignment.role.value
                self._settings.setValue(f"{prefix}/seriesId", assignment.series_id)
                self._settings.setValue(f"{prefix}/scale", assignment.transform.scale)
                self._settings.setValue(f"{prefix}/sign", assignment.transform.sign)
                self._settings.setValue(
                    f"{prefix}/outputUnit",
                    assignment.transform.output_unit,
                )
        finally:
            self._settings.endGroup()
        self._settings.sync()
        if self._settings.status() is not QSettings.Status.NoError:
            raise RoleAssignmentStoreError(
                f"{shot_id} の役割設定をアプリ設定へ保存できません"
            )

    def _read_assignment(self, role: SeriesRole) -> AssignedSeries | None:
        prefix = role.value
        raw_series_id = self._settings.value(f"{prefix}/seriesId")
        if raw_series_id is None or not str(raw_series_id).strip():
            return None

        raw_scale = self._settings.value(f"{prefix}/scale")
        raw_sign = self._settings.value(f"{prefix}/sign")
        raw_unit = self._settings.value(f"{prefix}/outputUnit")
        if raw_scale is None or raw_sign is None or raw_unit is None:
            raise ValueError(f"{role.value} の設定項目が不足しています")
        return AssignedSeries(
            role=role,
            series_id=str(raw_series_id),
            transform=SignalTransform(
                scale=float(raw_scale),
                sign=float(raw_sign),
                output_unit=str(raw_unit),
            ),
        )
