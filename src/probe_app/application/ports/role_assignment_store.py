from __future__ import annotations

from pathlib import Path
from typing import Protocol

from probe_app.domain.models.series_role import SeriesRoleAssignments


class RoleAssignmentStore(Protocol):
    """Persistence boundary kept separate from folder discovery."""

    def load(self, folder: Path, shot_id: str) -> SeriesRoleAssignments:
        """Load assignments for one shot, or return an empty configuration."""

    def save(
        self,
        folder: Path,
        shot_id: str,
        assignments: SeriesRoleAssignments,
    ) -> None:
        """Persist assignments without writing into the measurement folder."""
