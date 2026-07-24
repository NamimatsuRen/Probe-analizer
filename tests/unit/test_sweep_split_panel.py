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
    panel.set_current_time_offset_s(0.00125)

    assert panel.parameters() == parameters
    assert panel.current_time_offset_s() == 0.00125
    assert (
        panel._current_time_offset_ms.toolTip()  # noqa: SLF001
        == "currentの参照時刻を補正します。"
        "正の値ではSweep電圧より後のcurrentを使います。"
    )
    assert "Rawプレビュー: +1.250000 ms（未適用）" in panel.offset_status_text


def test_split_panel_defaults_to_the_legacy_analysis_window(qtbot: object) -> None:
    panel = SweepSplitPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]

    assert panel.parameters() == LegacySweepSplitParameters(
        points_per_cycle=20_000,
        sample_start=200_000,
        sample_stop=500_000,
    )


def test_offset_change_emits_lightweight_preview_and_tracks_applied_value(
    qtbot: object,
) -> None:
    panel = SweepSplitPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]

    with qtbot.waitSignal(  # type: ignore[attr-defined]
        panel.current_time_offset_preview_changed,
        timeout=1_000,
    ) as blocker:
        panel.set_current_time_offset_s(0.05)

    assert blocker.args == [0.05]
    assert "Rawプレビュー: +50.000000 ms（未適用）" in panel.offset_status_text
    assert "I–V・Sweep一覧・平滑化/微分" in panel.offset_status_text

    panel.mark_current_time_offset_applied(0.05)
    assert "適用済み: +50.000000 ms" in panel.offset_status_text


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
    assert not panel._current_time_offset_ms.isEnabled()  # noqa: SLF001
