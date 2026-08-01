from __future__ import annotations

from pathlib import Path
from typing import Protocol

from probe_app.domain.models.shot_metadata import ShotMetadata


class ShotMetadataStore(Protocol):
    def load(self, folder: Path, shot_id: str) -> ShotMetadata:
        """Return explicit metadata, or an unset record when none was saved."""

    def save(self, folder: Path, metadata: ShotMetadata) -> None:
        """Persist one shot's user-entered metadata outside measurement data."""

