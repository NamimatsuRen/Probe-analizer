from __future__ import annotations

import numpy as np

from probe_app.application.state import SweepRunStatus
from probe_app.domain.models.sweep import Sweep, SweepDirection
from probe_app.ui.widgets import SweepBrowser


def _sweep(number: int, direction: SweepDirection) -> Sweep:
    start = number * 4
    voltage = np.asarray([-2.0, -0.5, 1.0, 2.5], dtype=np.float64)
    if direction is SweepDirection.DOWN:
        voltage = voltage[::-1]
    return Sweep(
        sweep_id=f"voltage:{start}:{start + 4}",
        current_series_id="shot-001/current",
        voltage_series_id="shot-001/voltage",
        source_start_index=start,
        source_stop_index=start + 4,
        direction=direction,
        time_s=np.asarray([0.1, 0.2, 0.3, 0.4], dtype=np.float64) + number,
        voltage_v=voltage,
        current_a=np.asarray([1.0, 2.0, 3.0, 4.0], dtype=np.float64),
    )


def test_sweep_browser_displays_required_metadata(qtbot: object) -> None:
    browser = SweepBrowser()
    qtbot.addWidget(browser)  # type: ignore[attr-defined]
    sweeps = (
        _sweep(0, SweepDirection.UP),
        _sweep(1, SweepDirection.DOWN),
    )

    browser.render_state(SweepRunStatus.SUCCEEDED, sweeps, "2 Sweepへ分割しました")

    assert browser.sweep_count == 2
    assert browser.selected_sweep == sweeps[0]
    first = browser._tree.topLevelItem(0)  # noqa: SLF001
    second = browser._tree.topLevelItem(1)  # noqa: SLF001
    assert [first.text(column) for column in range(6)] == [
        "1",
        "↑ 上昇",
        "0.1",
        "0.4",
        "4",
        "-2 – 2.5",
    ]
    assert second.text(1) == "↓ 下降"
    assert second.text(2) == "1.1"
    assert second.text(3) == "1.4"


def test_sweep_browser_emits_selection_and_clears_invalidated_results(
    qtbot: object,
) -> None:
    browser = SweepBrowser()
    qtbot.addWidget(browser)  # type: ignore[attr-defined]
    sweeps = (
        _sweep(0, SweepDirection.UP),
        _sweep(1, SweepDirection.DOWN),
    )
    selected: list[Sweep] = []
    browser.sweep_selected.connect(selected.append)
    browser.set_sweeps(sweeps)

    assert browser.select_sweep(sweeps[1].sweep_id)
    assert browser.selected_sweep == sweeps[1]
    assert selected[-1] == sweeps[1]

    browser.render_state(SweepRunStatus.READY, (), "Sweep分割を実行できます")

    assert browser.sweep_count == 0
    assert browser.selected_sweep is None
    assert browser._tree.topLevelItemCount() == 0  # noqa: SLF001
    assert browser._summary.text() == "Sweep分割を実行できます"  # noqa: SLF001
