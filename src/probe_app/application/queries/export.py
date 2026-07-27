from __future__ import annotations

from probe_app.domain.models.analysis_result import (
    USABLE_ANALYSIS_STATUSES,
    AnalysisStatus,
)
from probe_app.domain.models.export import (
    ExportCandidate,
    ExportCandidateSnapshot,
)
from probe_app.domain.models.summary import SummaryRow, SummarySnapshot


def build_export_candidates(
    summary: SummarySnapshot,
) -> ExportCandidateSnapshot:
    """Project visible Export choices without mutating or running analysis."""

    candidates = tuple(_candidate_from_row(row) for row in summary.rows)
    return ExportCandidateSnapshot(
        folder_key=summary.scope.folder_key,
        shot_ids=summary.scope.shot_ids,
        candidates=candidates,
    )


def _candidate_from_row(row: SummaryRow) -> ExportCandidate:
    available_methods = tuple(
        method.method
        for method in row.methods
        if method.status in USABLE_ANALYSIS_STATUSES
        and (method.phi_v is not None or method.ti_ev is not None)
    )
    selected = row.current_revision and row.status in USABLE_ANALYSIS_STATUSES
    if selected:
        reason = "現在のRevisionと一致する有効な解析結果"
    elif not row.current_revision or row.status is AnalysisStatus.STALE:
        reason = row.message or "現在の設定と異なるため再計算が必要"
    elif row.status is AnalysisStatus.EXCLUDED:
        reason = row.exclusion_reason or row.message or "解析対象から除外"
    elif row.status is AnalysisStatus.ERROR:
        reason = row.message or "解析エラー"
    elif row.status is AnalysisStatus.BAD:
        reason = row.message or "品質判定で不適"
    elif row.status is AnalysisStatus.RUNNING:
        reason = "解析中のため完了済み結果だけを使用"
    else:
        reason = row.message or "解析結果が未確定"
    return ExportCandidate(
        number=row.number,
        sweep_id=row.sweep_id,
        shot_id=row.shot_id,
        status=row.status,
        current_revision=row.current_revision,
        available_methods=available_methods,
        selected_by_default=selected,
        reason=reason,
    )
