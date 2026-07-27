from __future__ import annotations

from probe_app.analysis import AnalysisSettings
from probe_app.ui.widgets import FitAnalysisPanel


def test_fit_panel_requires_explicit_run_and_emits_typed_settings(
    qtbot: object,
) -> None:
    panel = FitAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    emitted: list[object] = []
    panel.run_requested.connect(emitted.append)

    assert not panel._run_button.isEnabled()  # noqa: SLF001
    panel.select_sweep("shot-001/sweep:1")
    assert panel._run_button.isEnabled()  # noqa: SLF001
    assert "変更だけでは再計算しません" in panel.description

    panel._fit1_min.setValue(9.5)  # noqa: SLF001
    assert emitted == []

    panel._run_button.click()  # noqa: SLF001

    assert len(emitted) == 1
    assert isinstance(emitted[0], AnalysisSettings)
    assert emitted[0].potential.log_fit1_min_v == 9.5
    assert emitted[0].temperature.fit_window_v == 0.1


def test_fit_panel_controls_current_shot_batch_without_implicit_run(
    qtbot: object,
) -> None:
    panel = FitAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    run_all: list[object] = []
    cancelled: list[bool] = []
    panel.run_all_requested.connect(run_all.append)
    panel.cancel_all_requested.connect(lambda: cancelled.append(True))

    panel.select_sweep("shot-001/sweep:1")
    assert panel._run_all_button.isEnabled()  # noqa: SLF001

    panel._fit1_min.setValue(9.0)  # noqa: SLF001
    assert run_all == []

    panel._run_all_button.click()  # noqa: SLF001
    assert len(run_all) == 1
    assert isinstance(run_all[0], AnalysisSettings)

    panel.show_batch_progress(3, 12, "shot-001/sweep:3")
    assert not panel._run_all_button.isEnabled()  # noqa: SLF001
    assert panel._cancel_all_button.isEnabled()  # noqa: SLF001
    assert "3 / 12" in panel.description

    panel._cancel_all_button.click()  # noqa: SLF001
    assert cancelled == [True]

    panel.show_batch_cancelled(3, 12)
    assert panel._run_all_button.isEnabled()  # noqa: SLF001
    assert "完了済みの結果はサマリーに残ります" in panel.description
