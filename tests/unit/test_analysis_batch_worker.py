from __future__ import annotations

import numpy as np

from probe_app.analysis import AnalysisSettings, SavitzkyGolaySettings
from probe_app.domain.models import (
    AnalysisInputRevision,
    AnalysisStage,
    AnalysisStatus,
    PreprocessingRevision,
    SignalAssignmentRevision,
    Sweep,
    SweepDirection,
    SweepSplitRevision,
)
from probe_app.ui.workers import AnalysisBatchInput, AnalysisBatchOutput
from probe_app.ui.workers.analysis_worker import AnalysisBatchTask


def test_analysis_batch_emits_each_completed_sweep_and_final_count(
    qtbot: object,
) -> None:
    del qtbot
    sweep = _synthetic_sweep("shot-001/voltage:200000:210001")
    task = AnalysisBatchTask(
        7,
        (AnalysisBatchInput(sweep, _revision(sweep.sweep_id)),),
        SavitzkyGolaySettings(window_length=501, polyorder=3),
        AnalysisSettings(),
    )
    items: list[tuple[int, object, int, int]] = []
    completed: list[tuple[int, int]] = []
    task.signals.item_succeeded.connect(
        lambda generation, output, count, total: items.append(
            (generation, output, count, total)
        )
    )
    task.signals.completed.connect(
        lambda generation, count: completed.append((generation, count))
    )

    task.run()

    assert completed == [(7, 1)]
    assert len(items) == 1
    generation, output_object, count, total = items[0]
    assert generation == 7
    assert (count, total) == (1, 1)
    assert isinstance(output_object, AnalysisBatchOutput)
    assert output_object.complete is not None
    assert output_object.record.stage_result(AnalysisStage.QUALITY) is not None
    assert output_object.record.status in (
        AnalysisStatus.VALID,
        AnalysisStatus.REVIEW,
        AnalysisStatus.BAD,
    )


def test_analysis_batch_cancel_before_start_keeps_zero_completed_results(
    qtbot: object,
) -> None:
    del qtbot
    sweep = _synthetic_sweep("shot-001/voltage:200000:210001")
    task = AnalysisBatchTask(
        3,
        (AnalysisBatchInput(sweep, _revision(sweep.sweep_id)),),
        SavitzkyGolaySettings(window_length=501, polyorder=3),
        AnalysisSettings(),
    )
    cancelled: list[tuple[int, int]] = []
    task.signals.cancelled.connect(
        lambda generation, count: cancelled.append((generation, count))
    )

    task.cancel()
    task.run()

    assert cancelled == [(3, 0)]


def _synthetic_sweep(sweep_id: str) -> Sweep:
    voltage = np.linspace(-50.0, 50.0, 10_001, dtype=np.float64)
    current = np.empty_like(voltage)
    negative = voltage < 0.0
    current[negative] = -2e-4 + 2e-6 * (voltage[negative] + 50.0)
    middle = (voltage >= 0.0) & (voltage < 10.0)
    current[middle] = 1e-6 * (voltage[middle] + 1.0)
    fit1 = (voltage >= 10.0) & (voltage <= 15.0)
    current[fit1] = 10 ** (0.1 * voltage[fit1] - 7.0)
    bridge = (voltage > 15.0) & (voltage < 20.0)
    current[bridge] = np.linspace(current[fit1][-1], 2e-5, int(bridge.sum()))
    fit2 = voltage >= 20.0
    current[fit2] = 10 ** (0.01 * voltage[fit2] - 5.5)
    return Sweep(
        sweep_id=sweep_id,
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        source_start_index=200_000,
        source_stop_index=210_001,
        direction=SweepDirection.UP,
        time_s=np.linspace(0.2, 0.21, 10_001, dtype=np.float64),
        voltage_v=voltage,
        current_a=current,
    )


def _revision(sweep_id: str) -> AnalysisInputRevision:
    return AnalysisInputRevision(
        folder_key="/measurements",
        shot_id="shot-001",
        sweep_id=sweep_id,
        current=SignalAssignmentRevision(
            series_id="shot-001/current",
            scale=0.05,
            sign=-1.0,
            output_unit="A",
        ),
        sweep_voltage=SignalAssignmentRevision(
            series_id="shot-001/voltage",
            scale=100.0,
            sign=1.0,
            output_unit="V",
        ),
        split=SweepSplitRevision(
            points_per_cycle=20_002,
            sample_start=200_000,
            sample_stop=500_000,
            current_time_offset_s=0.0,
        ),
        preprocessing=PreprocessingRevision(window_length=501, polyorder=3),
        fit_settings=AnalysisSettings().as_revision_settings(),
        algorithm_version="level6-panta-v1",
        generation_id=1,
    )
