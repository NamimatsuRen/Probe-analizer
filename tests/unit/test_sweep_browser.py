from __future__ import annotations

import numpy as np

from probe_app.application.state import SweepRunStatus
from probe_app.domain.models.sweep import (
    Sweep,
    SweepDirection,
    SweepExclusion,
    SweepExclusionReason,
)
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

    browser.render_state(SweepRunStatus.SUCCEEDED, sweeps, (), "2 Sweepへ分割しました")

    assert browser.sweep_count == 2
    assert browser.selected_sweep == sweeps[0]
    assert browser._tree.headerItem().text(2) == "電圧開始 [ms]"  # noqa: SLF001
    assert browser._tree.headerItem().text(3) == "電圧終了 [ms]"  # noqa: SLF001
    first = browser._tree.topLevelItem(0)  # noqa: SLF001
    second = browser._tree.topLevelItem(1)  # noqa: SLF001
    assert [first.text(column) for column in range(6)] == [
        "1",
        "↑ 上昇",
        "100",
        "400",
        "4",
        "-2 – 2.5",
    ]
    assert second.text(1) == "↓ 下降"
    assert second.text(2) == "1100"
    assert second.text(3) == "1400"


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

    browser.render_state(SweepRunStatus.READY, (), (), "Sweep分割を実行できます")

    assert browser.sweep_count == 0
    assert browser.selected_sweep is None
    assert browser._tree.topLevelItemCount() == 0  # noqa: SLF001
    assert browser._summary.text() == "Sweep分割を実行できます"  # noqa: SLF001
    assert browser._position.text() == "0 / 0"  # noqa: SLF001
    assert not browser.can_select_previous
    assert not browser.can_select_next


def test_sweep_browser_navigates_without_leaving_the_available_range(
    qtbot: object,
) -> None:
    browser = SweepBrowser()
    qtbot.addWidget(browser)  # type: ignore[attr-defined]
    sweeps = (
        _sweep(0, SweepDirection.UP),
        _sweep(1, SweepDirection.DOWN),
        _sweep(2, SweepDirection.UP),
    )
    selected: list[Sweep] = []
    browser.sweep_selected.connect(selected.append)
    browser.set_sweeps(sweeps)

    assert browser.selected_index == 0
    assert browser._position.text() == "1 / 3"  # noqa: SLF001
    assert not browser.can_select_previous
    assert browser.can_select_next
    assert not browser.select_previous()
    assert browser.selected_sweep == sweeps[0]

    assert browser.select_next()
    assert browser.selected_sweep == sweeps[1]
    assert selected[-1] == sweeps[1]
    assert browser._position.text() == "2 / 3"  # noqa: SLF001
    assert browser.can_select_previous
    assert browser.can_select_next

    assert browser.select_next()
    assert browser.selected_sweep == sweeps[2]
    assert browser._position.text() == "3 / 3"  # noqa: SLF001
    assert browser.can_select_previous
    assert not browser.can_select_next
    assert not browser.select_next()
    assert browser.selected_sweep == sweeps[2]

    assert browser.select_previous()
    assert browser.selected_sweep == sweeps[1]


def test_sweep_browser_displays_excluded_intervals_separately(
    qtbot: object,
) -> None:
    browser = SweepBrowser()
    qtbot.addWidget(browser)  # type: ignore[attr-defined]
    exclusion = SweepExclusion(
        voltage_series_id="shot-001/voltage",
        source_start_index=12,
        source_stop_index=15,
        start_time_s=0.12,
        end_time_s=0.14,
        reason=SweepExclusionReason.INCOMPLETE_SWEEP,
        detail="4点のSweepに満たない端数のため除外",
    )

    browser.render_state(
        SweepRunStatus.SUCCEEDED,
        (_sweep(0, SweepDirection.UP),),
        (exclusion,),
        "1 Sweepへ分割しました（1区間を除外）",
    )

    assert browser.sweep_count == 1
    assert browser.exclusion_count == 1
    assert not browser._issues_heading.isHidden()  # noqa: SLF001
    assert browser._issues_tree.topLevelItemCount() == 1  # noqa: SLF001
    issue = browser._issues_tree.topLevelItem(0)  # noqa: SLF001
    assert [issue.text(column) for column in range(4)] == [
        "12–14",
        "120 – 140",
        "3",
        "短い未完了Sweep",
    ]
    assert "満たない" in issue.toolTip(3)
