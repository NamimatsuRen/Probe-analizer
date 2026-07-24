from __future__ import annotations

import numpy as np

from probe_app.analysis import SavitzkyGolaySettings, preprocess_sweep
from probe_app.domain.models.sweep import Sweep, SweepDirection
from probe_app.ui.widgets import PreprocessingPanel


def _sweep() -> Sweep:
    voltage_v = np.linspace(-2.0, 2.0, 9, dtype=np.float64)
    return Sweep(
        sweep_id="shot-001/voltage:10:19",
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        source_start_index=10,
        source_stop_index=19,
        direction=SweepDirection.UP,
        time_s=np.linspace(0.1, 0.18, 9, dtype=np.float64),
        voltage_v=voltage_v,
        current_a=voltage_v**2,
    )


def test_preprocessing_panel_emits_explicit_settings(qtbot: object) -> None:
    panel = PreprocessingPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.show_result(
        preprocess_sweep(
            _sweep(),
            SavitzkyGolaySettings(window_length=5, polyorder=2),
        )
    )
    panel.set_settings(SavitzkyGolaySettings(window_length=7, polyorder=3))

    with qtbot.waitSignal(panel.run_requested, timeout=1_000) as blocker:  # type: ignore[attr-defined]
        panel._run_button.click()  # noqa: SLF001

    assert blocker.args == [SavitzkyGolaySettings(window_length=7, polyorder=3)]


def test_preprocessing_panel_describes_adjusted_window_and_error(
    qtbot: object,
) -> None:
    panel = PreprocessingPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    sweep = _sweep()
    result = preprocess_sweep(
        sweep,
        SavitzkyGolaySettings(window_length=501, polyorder=3),
    )

    panel.show_result(result)

    assert panel.selected_sweep_id == sweep.sweep_id
    assert panel.result is result
    assert "SG窓 9 点" in panel.description
    assert "指定 501 点から自動調整" in panel.description

    panel.show_error(sweep.sweep_id, "点数が不足しています")
    assert panel.result is None
    assert "点数が不足" in panel.description
    assert "再計算" in panel.description

    panel.clear()
    assert panel.selected_sweep_id is None
    assert panel.result is None
