from __future__ import annotations

from dataclasses import dataclass, replace

from probe_app.domain.models.shot_metadata import ShotMetadata
from probe_app.domain.models.summary import SummaryRow, SummaryScopeKind, SummarySnapshot


@dataclass(frozen=True, slots=True)
class ShotAnalysisSnapshot:
    """Lightweight shot results; waveform arrays are deliberately absent."""

    folder_key: str
    shot_id: str
    rows: tuple[SummaryRow, ...]
    metadata: ShotMetadata

    def __post_init__(self) -> None:
        if not self.folder_key.strip() or not self.shot_id.strip():
            raise ValueError("folder_key and shot_id cannot be empty")
        if self.metadata.folder_key != self.folder_key:
            raise ValueError("metadata folder does not match the snapshot")
        if self.metadata.shot_id != self.shot_id:
            raise ValueError("metadata shot does not match the snapshot")
        if any(row.shot_id != self.shot_id for row in self.rows):
            raise ValueError("all rows must belong to the snapshot shot")

    @classmethod
    def capture(
        cls,
        snapshot: SummarySnapshot,
        metadata: ShotMetadata,
    ) -> ShotAnalysisSnapshot:
        if snapshot.scope.kind is not SummaryScopeKind.CURRENT_SHOT:
            raise ValueError("only a current-shot summary can be captured")
        shot_id = snapshot.scope.shot_ids[0]
        return cls(
            folder_key=snapshot.scope.folder_key,
            shot_id=shot_id,
            rows=snapshot.rows,
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class AnalysisCatalog:
    """Immutable collection of scalar analysis snapshots across loaded shots."""

    shots: tuple[ShotAnalysisSnapshot, ...] = ()

    def put(self, snapshot: ShotAnalysisSnapshot) -> AnalysisCatalog:
        remaining = tuple(
            item
            for item in self.shots
            if (item.folder_key, item.shot_id)
            != (snapshot.folder_key, snapshot.shot_id)
        )
        return AnalysisCatalog((*remaining, snapshot))

    def get(self, folder_key: str, shot_id: str) -> ShotAnalysisSnapshot | None:
        return next(
            (
                item
                for item in reversed(self.shots)
                if item.folder_key == folder_key and item.shot_id == shot_id
            ),
            None,
        )

    def for_folder(self, folder_key: str) -> tuple[ShotAnalysisSnapshot, ...]:
        return tuple(item for item in self.shots if item.folder_key == folder_key)

    def update_metadata(self, metadata: ShotMetadata) -> AnalysisCatalog:
        existing = self.get(metadata.folder_key, metadata.shot_id)
        if existing is None:
            return self.put(
                ShotAnalysisSnapshot(
                    folder_key=metadata.folder_key,
                    shot_id=metadata.shot_id,
                    rows=(),
                    metadata=metadata,
                )
            )
        return self.put(replace(existing, metadata=metadata))

    def clear_other_folders(self, folder_key: str) -> AnalysisCatalog:
        return AnalysisCatalog(self.for_folder(folder_key))

