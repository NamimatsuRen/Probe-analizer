from __future__ import annotations

from dataclasses import dataclass

from probe_app.domain.models.analysis_result import (
    AnalysisInputRevision,
    AnalysisStage,
    AnalysisStatus,
    SweepAnalysisRecord,
)


@dataclass(frozen=True, slots=True)
class AnalysisResultStore:
    """Immutable metadata store keyed by Sweep identity and input revision."""

    records: tuple[SweepAnalysisRecord, ...] = ()

    def put(self, record: SweepAnalysisRecord) -> AnalysisResultStore:
        key = record.revision.cache_key
        remaining = tuple(
            item for item in self.records if item.revision.cache_key != key
        )
        return AnalysisResultStore((*remaining, record))

    def put_if_current(
        self,
        record: SweepAnalysisRecord,
        current_revision: AnalysisInputRevision,
    ) -> tuple[AnalysisResultStore, bool]:
        """Discard an old generation/revision without mutating existing state."""

        if record.revision.cache_key != current_revision.cache_key:
            return self, False
        return self.put(record), True

    def get(self, revision: AnalysisInputRevision) -> SweepAnalysisRecord | None:
        key = revision.cache_key
        return next(
            (record for record in reversed(self.records) if record.revision.cache_key == key),
            None,
        )

    def latest_for_sweep(self, sweep_id: str) -> SweepAnalysisRecord | None:
        return next(
            (
                record
                for record in reversed(self.records)
                if record.revision.sweep_id == sweep_id
            ),
            None,
        )

    def accepted_current(
        self,
        revision: AnalysisInputRevision,
    ) -> SweepAnalysisRecord | None:
        record = self.get(revision)
        return record if record is not None and record.is_usable else None

    def exclude(
        self,
        revision: AnalysisInputRevision,
        reason: str,
    ) -> AnalysisResultStore:
        record = self.get(revision)
        if record is None:
            raise ValueError("cannot exclude an analysis result that does not exist")
        return self.put(record.exclude(reason))

    def restore(self, revision: AnalysisInputRevision) -> AnalysisResultStore:
        record = self.get(revision)
        if record is None:
            raise ValueError("cannot restore an analysis result that does not exist")
        if record.status is not AnalysisStatus.EXCLUDED:
            raise ValueError("only an excluded analysis result can be restored")
        return self.put(record.restore())

    def mark_sweep_stale(
        self,
        sweep_id: str,
        *,
        from_stage: AnalysisStage = AnalysisStage.PREPROCESSING,
        reason: str,
    ) -> AnalysisResultStore:
        return AnalysisResultStore(
            tuple(
                (
                    record.mark_stale_from(from_stage, reason)
                    if record.revision.sweep_id == sweep_id
                    else record
                )
                for record in self.records
            )
        )

    def mark_all_stale(
        self,
        reason: str,
        *,
        from_stage: AnalysisStage = AnalysisStage.PREPROCESSING,
    ) -> AnalysisResultStore:
        return AnalysisResultStore(
            tuple(
                record.mark_stale_from(from_stage, reason)
                for record in self.records
            )
        )
