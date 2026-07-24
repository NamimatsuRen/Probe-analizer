from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from probe_app.domain.models.catalog import FolderCatalog
from probe_app.infrastructure.readers.folder_scanner import FolderScanner


class OpenFolder:
    """Build a data catalog directly from a folder; no JSON config is required."""

    def __init__(self, scanner: FolderScanner | None = None) -> None:
        self._scanner = scanner or FolderScanner()

    def execute(
        self,
        folder: Path,
        *,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> FolderCatalog:
        return self._scanner.scan(folder, is_cancelled=is_cancelled)
