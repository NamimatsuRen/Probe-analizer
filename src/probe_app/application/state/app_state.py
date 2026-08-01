from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path

from probe_app.application.state.analysis_result_store import AnalysisResultStore
from probe_app.domain.models.analysis_result import (
    AnalysisInputRevision,
    AnalysisStage,
    SweepAnalysisRecord,
)
from probe_app.domain.models.catalog import FolderCatalog
from probe_app.domain.models.series_role import SeriesRoleAssignments
from probe_app.domain.models.sweep import Sweep, SweepExclusion


class LoadStatus(StrEnum):
    IDLE = "idle"
    LOADING = "loading"
    READY = "ready"
    EMPTY = "empty"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    ERROR = "error"


class SweepRunStatus(StrEnum):
    IDLE = "idle"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
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
    sweep_status: SweepRunStatus = SweepRunStatus.IDLE
    sweeps: tuple[Sweep, ...] = ()
    sweep_exclusions: tuple[SweepExclusion, ...] = ()
    selected_sweep_id: str | None = None
    sweep_interpolated_current: bool | None = None
    analysis_results: AnalysisResultStore = field(default_factory=AnalysisResultStore)
    sweep_message: str = "解析系列の役割を選択してください"
    sweep_error: str = ""
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
            sweep_status=SweepRunStatus.IDLE,
            sweeps=(),
            sweep_exclusions=(),
            selected_sweep_id=None,
            sweep_interpolated_current=None,
            analysis_results=self.analysis_results.mark_all_stale(
                "入力フォルダが変更されました"
            ),
            sweep_message="解析系列の役割を選択してください",
            sweep_error="",
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
                sweep_status=SweepRunStatus.IDLE,
                sweeps=(),
                sweep_exclusions=(),
                selected_sweep_id=None,
                sweep_interpolated_current=None,
                analysis_results=self.analysis_results.mark_all_stale(
                    "読み込んだcatalogが変更されました"
                ),
                sweep_message="解析系列の役割を選択してください",
                sweep_error="",
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
            sweep_status=SweepRunStatus.IDLE,
            sweeps=(),
            sweep_exclusions=(),
            selected_sweep_id=None,
            sweep_interpolated_current=None,
            analysis_results=self.analysis_results.mark_all_stale(
                "読み込んだcatalogが変更されました"
            ),
            sweep_message="解析系列の役割を選択してください",
            sweep_error="",
            message=message,
        )

    def select_series(self, series_id: str) -> AppState:
        if self.catalog is None or self.catalog.find(series_id) is None:
            raise ValueError(f"unknown series_id: {series_id}")
        return replace(
            self,
            selected_series_id=series_id,
            sweep_status=(
                SweepRunStatus.READY
                if self.role_assignments.is_complete
                else SweepRunStatus.IDLE
            ),
            sweeps=(),
            sweep_exclusions=(),
            selected_sweep_id=None,
            sweep_interpolated_current=None,
            analysis_results=self.analysis_results.mark_all_stale(
                "表示系列が変更されました"
            ),
            sweep_message=(
                "Sweep分割を実行できます"
                if self.role_assignments.is_complete
                else "解析系列の役割を選択してください"
            ),
            sweep_error="",
        )

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
            sweep_status=(
                SweepRunStatus.READY if assignments.is_complete else SweepRunStatus.IDLE
            ),
            sweeps=(),
            sweep_exclusions=(),
            selected_sweep_id=None,
            sweep_interpolated_current=None,
            analysis_results=self.analysis_results.mark_all_stale(
                "解析系列の役割または変換設定が変更されました"
            ),
            sweep_message=(
                "Sweep分割を実行できます"
                if assignments.is_complete
                else "解析系列の役割を選択してください"
            ),
            sweep_error="",
        )

    def start_sweep_split(self) -> AppState:
        if not self.role_assignments.is_complete:
            raise ValueError("role assignments must be complete before splitting sweeps")
        return replace(
            self,
            sweep_status=SweepRunStatus.RUNNING,
            sweeps=(),
            sweep_exclusions=(),
            selected_sweep_id=None,
            sweep_interpolated_current=None,
            analysis_results=self.analysis_results.mark_all_stale(
                "Sweep分割条件を再実行しています"
            ),
            sweep_message="2系列を読み込み、Sweepへ分割しています…",
            sweep_error="",
        )

    def apply_sweep_result(
        self,
        sweeps: tuple[Sweep, ...],
        *,
        interpolated_current: bool,
        exclusions: tuple[SweepExclusion, ...] = (),
    ) -> AppState:
        if self.sweep_status is not SweepRunStatus.RUNNING:
            raise ValueError("Sweep result can only be applied while a split is running")
        return replace(
            self,
            sweep_status=SweepRunStatus.SUCCEEDED,
            sweeps=sweeps,
            sweep_exclusions=exclusions,
            selected_sweep_id=sweeps[0].sweep_id if sweeps else None,
            sweep_interpolated_current=interpolated_current,
            sweep_message=(
                f"{len(sweeps)} Sweepへ分割しました"
                + (f"（{len(exclusions)}区間を除外）" if exclusions else "")
            ),
            sweep_error="",
        )

    def fail_sweep_split(self, message: str, *, details: str = "") -> AppState:
        return replace(
            self,
            sweep_status=SweepRunStatus.ERROR,
            sweeps=(),
            sweep_exclusions=(),
            selected_sweep_id=None,
            sweep_interpolated_current=None,
            analysis_results=self.analysis_results.mark_all_stale(
                "Sweep分割に失敗しました"
            ),
            sweep_message=message,
            sweep_error=details,
        )

    def cancel_sweep_split(self) -> AppState:
        return replace(
            self,
            sweep_status=SweepRunStatus.CANCELLED,
            sweeps=(),
            sweep_exclusions=(),
            selected_sweep_id=None,
            sweep_interpolated_current=None,
            analysis_results=self.analysis_results.mark_all_stale(
                "Sweep分割をキャンセルしました"
            ),
            sweep_message=(
                "Sweep分割をキャンセルしました。再実行できます"
                if self.role_assignments.is_complete
                else "解析系列の役割を選択してください"
            ),
            sweep_error="",
        )

    def fail(self, message: str) -> AppState:
        return replace(
            self,
            status=LoadStatus.ERROR,
            catalog=None,
            selected_series_id=None,
            role_assignment_shot_id=None,
            role_assignments=SeriesRoleAssignments(),
            sweep_status=SweepRunStatus.IDLE,
            sweeps=(),
            sweep_exclusions=(),
            selected_sweep_id=None,
            sweep_interpolated_current=None,
            analysis_results=self.analysis_results.mark_all_stale(
                "フォルダ読込に失敗しました"
            ),
            sweep_message="解析系列の役割を選択してください",
            sweep_error="",
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
            sweep_status=SweepRunStatus.IDLE,
            sweeps=(),
            sweep_exclusions=(),
            selected_sweep_id=None,
            sweep_interpolated_current=None,
            analysis_results=self.analysis_results.mark_all_stale(
                "読込をキャンセルしました"
            ),
            sweep_message="解析系列の役割を選択してください",
            sweep_error="",
            message="読み込みをキャンセルしました",
        )

    @property
    def selected_sweep(self) -> Sweep | None:
        if self.selected_sweep_id is None:
            return None
        return next(
            (
                sweep
                for sweep in self.sweeps
                if sweep.sweep_id == self.selected_sweep_id
            ),
            None,
        )

    def select_sweep(self, sweep_id: str) -> AppState:
        if not any(sweep.sweep_id == sweep_id for sweep in self.sweeps):
            raise ValueError(f"unknown sweep_id: {sweep_id}")
        return replace(self, selected_sweep_id=sweep_id)

    def record_analysis(self, record: SweepAnalysisRecord) -> AppState:
        if record.revision.sweep_id not in {
            sweep.sweep_id for sweep in self.sweeps
        }:
            raise ValueError(
                f"analysis record is outside current Sweeps: {record.revision.sweep_id}"
            )
        return replace(
            self,
            analysis_results=self.analysis_results.put(record),
        )

    def record_analysis_if_current(
        self,
        record: SweepAnalysisRecord,
        current_revision: AnalysisInputRevision,
    ) -> tuple[AppState, bool]:
        store, accepted = self.analysis_results.put_if_current(
            record,
            current_revision,
        )
        return replace(self, analysis_results=store), accepted

    def exclude_analysis(
        self,
        revision: AnalysisInputRevision,
        reason: str,
    ) -> AppState:
        if revision.sweep_id not in {sweep.sweep_id for sweep in self.sweeps}:
            raise ValueError(
                "analysis record is outside current Sweeps: "
                f"{revision.sweep_id}"
            )
        return replace(
            self,
            analysis_results=self.analysis_results.exclude(revision, reason),
        )

    def restore_analysis(self, revision: AnalysisInputRevision) -> AppState:
        if revision.sweep_id not in {sweep.sweep_id for sweep in self.sweeps}:
            raise ValueError(
                "analysis record is outside current Sweeps: "
                f"{revision.sweep_id}"
            )
        return replace(
            self,
            analysis_results=self.analysis_results.restore(revision),
        )

    def invalidate_analysis(
        self,
        sweep_id: str,
        *,
        from_stage: AnalysisStage,
        reason: str,
    ) -> AppState:
        return replace(
            self,
            analysis_results=self.analysis_results.mark_sweep_stale(
                sweep_id,
                from_stage=from_stage,
                reason=reason,
            ),
        )
