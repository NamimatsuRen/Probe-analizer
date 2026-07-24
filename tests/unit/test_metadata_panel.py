from __future__ import annotations

from pathlib import Path

import numpy as np

from probe_app.domain.models.raw_series import RawSeries, RawSeriesDescriptor
from probe_app.ui.widgets import MetadataPanel


def test_metadata_time_range_is_displayed_in_ms(qtbot: object) -> None:
    descriptor = RawSeriesDescriptor(
        series_id="shot-001/current",
        shot_id="shot-001",
        channel_id="current",
        header_path=Path("current.hdr"),
        data_path=Path("current.dat"),
        sample_count=3,
        value_unit="A",
        time_unit="s",
    )
    series = RawSeries(
        descriptor=descriptor,
        time_s=np.asarray([0.0, 0.2, 0.6], dtype=np.float64),
        values=np.asarray([1.0, 2.0, 3.0], dtype=np.float64),
    )
    panel = MetadataPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]

    panel.show_series(series)

    assert panel._fields["time"].text() == "0 ms ～ 600 ms"  # noqa: SLF001
