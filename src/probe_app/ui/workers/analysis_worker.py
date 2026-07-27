from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from probe_app.analysis import (
    AnalysisSettings,
    CompleteAnalysisResult,
    PreprocessedSweep,
    PreprocessingError,
    SavitzkyGolaySettings,
    analyze_preprocessed,
    preprocess_sweep,
)
from probe_app.domain.models.analysis_result import (
    AnalysisInputRevision,
    AnalysisStage,
    AnalysisStatus,
    MethodOutcome,
    StageResult,
    SweepAnalysisRecord,
)
from probe_app.domain.models.sweep import Sweep


@dataclass(frozen=True, slots=True)
class AnalysisBatchInput:
    sweep: Sweep
    revision: AnalysisInputRevision


@dataclass(frozen=True, slots=True)
class AnalysisBatchOutput:
    record: SweepAnalysisRecord
    complete: CompleteAnalysisResult | None


class AnalysisBatchSignals(QObject):
    item_succeeded = Signal(int, object, int, int)
    failed = Signal(int, str, str)
    completed = Signal(int, int)
    cancelled = Signal(int, int)


class AnalysisBatchTask(QRunnable):
    """Cancellable current-shot analysis that emits every completed Sweep."""

    def __init__(
        self,
        generation: int,
        inputs: tuple[AnalysisBatchInput, ...],
        preprocessing_settings: SavitzkyGolaySettings,
        analysis_settings: AnalysisSettings,
    ) -> None:
        super().__init__()
        self.generation = generation
        self.signals = AnalysisBatchSignals()
        self._inputs = inputs
        self._preprocessing_settings = preprocessing_settings
        self._analysis_settings = analysis_settings
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @Slot()
    def run(self) -> None:
        completed = 0
        total = len(self._inputs)
        try:
            for item in self._inputs:
                if self._cancelled.is_set():
                    self.signals.cancelled.emit(self.generation, completed)
                    return
                output = self._analyze(item)
                completed += 1
                self.signals.item_succeeded.emit(
                    self.generation,
                    output,
                    completed,
                    total,
                )
            self.signals.completed.emit(self.generation, completed)
        except Exception as error:
            self.signals.failed.emit(
                self.generation,
                str(error),
                traceback.format_exc(),
            )

    def _analyze(self, item: AnalysisBatchInput) -> AnalysisBatchOutput:
        record = SweepAnalysisRecord.running(item.revision)
        try:
            preprocessed = preprocess_sweep(
                item.sweep,
                self._preprocessing_settings,
            )
        except (PreprocessingError, ValueError) as error:
            message = str(error)
            record = record.with_stage_result(
                StageResult(
                    stage=AnalysisStage.PREPROCESSING,
                    status=AnalysisStatus.ERROR,
                    methods=(
                        MethodOutcome(
                            method_id="savitzky_golay",
                            status=AnalysisStatus.ERROR,
                            message=message,
                        ),
                    ),
                    message=message,
                ),
                overall_status=AnalysisStatus.ERROR,
            )
            return AnalysisBatchOutput(record=record, complete=None)

        record = record.with_stage_result(_preprocessing_stage(preprocessed))
        complete = analyze_preprocessed(preprocessed, self._analysis_settings)
        for index, stage_result in enumerate(complete.stage_results):
            record = record.with_stage_result(
                stage_result,
                overall_status=(
                    complete.status
                    if index == len(complete.stage_results) - 1
                    else None
                ),
            )
        return AnalysisBatchOutput(record=record, complete=complete)


def _preprocessing_stage(result: PreprocessedSweep) -> StageResult:
    status = (
        AnalysisStatus.REVIEW
        if result.spacing_warning
        else AnalysisStatus.VALID
    )
    return StageResult(
        stage=AnalysisStage.PREPROCESSING,
        status=status,
        methods=(
            MethodOutcome(
                method_id="savitzky_golay",
                status=status,
                message=result.spacing_warning,
                metrics=(
                    (
                        "max_spacing_deviation_fraction",
                        result.max_spacing_deviation_fraction,
                    ),
                    ("polyorder", float(result.polyorder)),
                    ("used_window_length", float(result.used_window_length)),
                    ("voltage_step_v", result.voltage_step_v),
                ),
            ),
        ),
        message=result.spacing_warning,
    )
