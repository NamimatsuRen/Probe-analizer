from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from probe_app.domain.errors import RawDataReadError
from probe_app.infrastructure.readers.folder_scanner import FolderScanner
from probe_app.infrastructure.readers.panta_reader import PantaRawReader
from tests.conftest import write_panta_series


@pytest.mark.parametrize("compressed", [False, True])
def test_reads_and_calibrates_waveform(tmp_path: Path, compressed: bool) -> None:
    write_panta_series(
        tmp_path,
        samples=np.asarray([0, 1, -2, 4], dtype=np.int16),
        compressed=compressed,
    )
    descriptor = FolderScanner().scan(tmp_path).series[0]

    series = PantaRawReader().read(descriptor)

    np.testing.assert_allclose(series.values, [1.0, 1.5, 0.0, 3.0])
    np.testing.assert_allclose(series.time_s, [0.15, 0.25, 0.35, 0.45])
    assert series.value_range == pytest.approx((0.0, 3.0))


def test_reads_big_endian_waveform(tmp_path: Path) -> None:
    write_panta_series(
        tmp_path,
        samples=np.asarray([1, 256], dtype=np.int16),
        endian="Big",
        resolution=1.0,
        offset=0.0,
    )
    descriptor = FolderScanner().scan(tmp_path).series[0]

    series = PantaRawReader().read(descriptor)

    np.testing.assert_allclose(series.values, [1.0, 256.0])


def test_rejects_truncated_waveform(tmp_path: Path) -> None:
    _, data_path = write_panta_series(tmp_path)
    data_path.write_bytes(b"\x00\x00")
    descriptor = FolderScanner().scan(tmp_path).series[0]

    with pytest.raises(RawDataReadError, match="1点しかありません"):
        PantaRawReader().read(descriptor)
