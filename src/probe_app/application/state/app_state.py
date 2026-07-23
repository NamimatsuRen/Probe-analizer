from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from probe_app.domain.models.catalog import FolderCatalog


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
    message: str = "フォルダを選択してください"

    def start_loading(self, folder: Path) -> AppState:
        return replace(
            self,
            status=LoadStatus.LOADING,
            folder=folder,
            catalog=None,
            selected_series_id=None,
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
            message=message,
        )

    def select_series(self, series_id: str) -> AppState:
        if self.catalog is None or self.catalog.find(series_id) is None:
            raise ValueError(f"unknown series_id: {series_id}")
        return replace(self, selected_series_id=series_id)

    def fail(self, message: str) -> AppState:
        return replace(
            self,
            status=LoadStatus.ERROR,
            catalog=None,
            selected_series_id=None,
            message=message,
        )

    def cancel(self) -> AppState:
        return replace(
            self,
            status=LoadStatus.CANCELLED,
            catalog=None,
            selected_series_id=None,
            message="読み込みをキャンセルしました",
        )
