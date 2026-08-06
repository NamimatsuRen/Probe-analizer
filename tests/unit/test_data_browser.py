from __future__ import annotations

from pathlib import Path

from probe_app.domain.models.catalog import FolderCatalog
from probe_app.domain.models.raw_series import RawSeriesDescriptor
from probe_app.ui.widgets.data_browser import DataBrowser


def test_data_browser_starts_with_guidance_and_collapsed_shots(
    qtbot: object,
    tmp_path: Path,
) -> None:
    browser = DataBrowser()
    qtbot.addWidget(browser)  # type: ignore[attr-defined]
    descriptor = RawSeriesDescriptor(
        series_id="shot-001/3_3_01",
        shot_id="shot-001",
        channel_id="3_3_01",
        header_path=tmp_path / "shot-001" / "3_3_01.hdr",
        data_path=tmp_path / "shot-001" / "3_3_01.dat",
        sample_count=600_000,
        value_unit="V",
        time_unit="s",
    )

    assert "フォルダを開く" in browser._guidance.text()  # noqa: SLF001
    browser.set_catalog(FolderCatalog(root=tmp_path, series=(descriptor,)))

    shot_item = browser._tree.topLevelItem(0)  # noqa: SLF001
    assert not shot_item.isExpanded()
    assert "初期状態では閉じています" in browser._guidance.text()  # noqa: SLF001
