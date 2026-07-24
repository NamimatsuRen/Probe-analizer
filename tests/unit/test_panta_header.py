from __future__ import annotations

from pathlib import Path

import pytest

from probe_app.domain.errors import HeaderParseError
from probe_app.infrastructure.readers.panta_header import PantaHeader
from tests.conftest import write_panta_series


def test_parses_required_header_fields(tmp_path: Path) -> None:
    header_path, _ = write_panta_series(tmp_path)

    header = PantaHeader.from_file(header_path)

    assert header.block_size == 4
    assert header.value_resolution == pytest.approx(0.5)
    assert header.value_offset == pytest.approx(1.0)
    assert header.time_resolution == pytest.approx(0.1)
    assert header.time_offset == pytest.approx(0.5)
    assert header.recorded_at == "2026/07/23 12:34:56"
    assert header.numpy_dtype == "<i2"


def test_rejects_header_without_block_size(tmp_path: Path) -> None:
    path = tmp_path / "broken.hdr"
    path.write_text("VResolution 1\nVOffset 0\nHResolution 1\n", encoding="utf-8")

    with pytest.raises(HeaderParseError, match="BlockSize"):
        PantaHeader.from_file(path)


def test_big_endian_dtype(tmp_path: Path) -> None:
    header_path, _ = write_panta_series(tmp_path, endian="Big")

    assert PantaHeader.from_file(header_path).numpy_dtype == ">i2"
