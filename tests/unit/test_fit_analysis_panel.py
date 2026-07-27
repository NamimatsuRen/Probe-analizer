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
