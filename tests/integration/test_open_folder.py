from __future__ import annotations

from pathlib import Path

import numpy as np

from probe_app.application.use_cases import OpenFolder
from probe_app.infrastructure.readers.panta_reader import PantaRawReader
from tests.conftest import write_panta_series


def test_folder_to_catalog_to_waveform(tmp_path: Path) -> None:
    write_panta_series(
        tmp_path / "shot-001",
        "current",
        samples=np.asarray([10, 20, 30], dtype=np.int16),
        resolution=0.1,
        offset=-1.0,
    )

    catalog = OpenFolder().execute(tmp_path)
    series = PantaRawReader().read(catalog.series[0])

    assert catalog.series[0].shot_id == "shot-001"
    np.testing.assert_allclose(series.values, [0.0, 1.0, 2.0])
