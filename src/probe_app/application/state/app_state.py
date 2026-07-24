from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path

from probe_app.domain.models.catalog import FolderCatalog
from probe_app.domain.models.series_role import SeriesRoleAssignments


class LoadStatus(StrEnum):
    IDLE = "idle"
    LOADING = "loading"
    READY = "ready"
    EMPTY = "empty"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AppState:
    status: LoadStatus = LoadStatus.IDLE
    folder: Path | None = None
    catalog: FolderCatalog | None = None
    selected_series_id: str | None = None
    role_assignment_shot_id: str | None = None
    role_assignments: SeriesRoleAssignments = field(default_factory=SeriesRoleAssignments)
    message: str = "フォルダを選択してください"

    def start_loading(self, folder: Path) -> AppState:
        return replace(
            self,
            status=LoadStatus.LOADING,
            folder=folder,
            catalog=None,
            selected_series_id=None,
            role_assignment_shot_id=None,
            role_assignments=SeriesRoleAssignments(),
            message=f"{folder.name} を読み込んでいます…",
        )

    def apply_catalog(self, catalog: FolderCatalog) -> AppState:
        if catalog.is_empty:
            return replace(
                self,
                status=LoadStatus.EMPTY,
                folder=catalog.root,
                catalog=catalog,
                selected_series_id=None,
                role_assignment_shot_id=None,
                role_assignments=SeriesRoleAssignments(),
                message="対応する測定データが見つかりませんでした",
            )
        first_id = catalog.series[0].series_id
        status = LoadStatus.PARTIAL if catalog.is_partial else LoadStatus.READY
        message = f"{len(catalog.series)} 系列を認識しました"
        if catalog.is_partial:
            message += f"（{len(catalog.problems)} 件は読み込めません）"
        return replace(
            self,
            status=status,
            folder=catalog.root,
            catalog=catalog,
            selected_series_id=first_id,
            role_assignment_shot_id=None,
            role_assignments=SeriesRoleAssignments(),
            message=message,
        )

    def select_series(self, series_id: str) -> AppState:
        if self.catalog is None or self.catalog.find(series_id) is None:
            raise ValueError(f"unknown series_id: {series_id}")
        return replace(self, selected_series_id=series_id)

    def set_role_assignments(
        self,
        shot_id: str,
        assignments: SeriesRoleAssignments,
    ) -> AppState:
        if self.catalog is None:
            raise ValueError("a catalog is required before assigning series roles")
        valid_ids = {
            descriptor.series_id for descriptor in self.catalog.series_for_shot(shot_id)
        }
        if not valid_ids:
            raise ValueError(f"unknown shot_id: {shot_id}")
        invalid_ids = [
            assignment.series_id
            for assignment in assignments.items
            if assignment.series_id not in valid_ids
        ]
        if invalid_ids:
            raise ValueError(
                f"role assignments are outside shot {shot_id}: {', '.join(invalid_ids)}"
            )
        return replace(
            self,
            role_assignment_shot_id=shot_id,
            role_assignments=assignments,
        )

    def fail(self, message: str) -> AppState:
        return replace(
            self,
            status=LoadStatus.ERROR,
            catalog=None,
            selected_series_id=None,
            role_assignment_shot_id=None,
            role_assignments=SeriesRoleAssignments(),
            message=message,
        )

    def cancel(self) -> AppState:
        return replace(
            self,
            status=LoadStatus.CANCELLED,
            catalog=None,
            selected_series_id=None,
            role_assignment_shot_id=None,
            role_assignments=SeriesRoleAssignments(),
            message="読み込みをキャンセルしました",
        )
