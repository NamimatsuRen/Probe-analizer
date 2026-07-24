from __future__ import annotations

from probe_app.application.state import SweepRunStatus
from probe_app.domain.services.sweep_splitter import LegacySweepSplitParameters
from probe_app.ui.widgets import SweepSplitPanel


def test_split_panel_exposes_explicit_non_json_parameters(qtbot: object) -> None:
    panel = SweepSplitPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    parameters = LegacySweepSplitParameters(
        points_per_cycle=8,
        sample_start=4,
        sample_stop=28,
    )

    panel.set_parameters(parameters)

    assert panel.parameters() == parameters


def test_split_panel_only_runs_when_ready_and_not_running(qtbot: object) -> None:
    panel = SweepSplitPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    run_button = panel.findChild(type(panel._run_button), "runSweepSplit")  # noqa: SLF001
    cancel_button = panel.findChild(
        type(panel._cancel_button),  # noqa: SLF001
        "cancelSweepSplit",
    )
    assert run_button is not None
    assert cancel_button is not None
    assert not run_button.isEnabled()

    panel.render_state(SweepRunStatus.READY, "実行できます", ready=True)
    assert run_button.isEnabled()
    assert not cancel_button.isEnabled()

    panel.render_state(SweepRunStatus.RUNNING, "分割中", ready=True)
    assert not run_button.isEnabled()
    assert cancel_button.isEnabled()
