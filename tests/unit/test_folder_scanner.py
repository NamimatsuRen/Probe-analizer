from __future__ import annotations

from pathlib import Path

import pytest

from probe_app.domain.errors import FolderScanError, OperationCancelled
from probe_app.infrastructure.readers.folder_scanner import FolderScanner
from tests.conftest import write_panta_series


def test_discovers_nested_header_data_pairs(tmp_path: Path) -> None:
    write_panta_series(tmp_path / "20211221" / "107845_032", "3_3_01")
    write_panta_series(tmp_path / "20211221" / "107845_032", "3_3_02")

    catalog = FolderScanner().scan(tmp_path)

    assert len(catalog.series) == 2
    assert catalog.shots == ("20211221/107845_032",)
    assert catalog.series[0].series_id == "20211221/107845_032/3_3_01"
    assert catalog.series[0].sample_count == 4
    assert not catalog.problems


def test_uses_selected_folder_name_when_files_are_at_root(tmp_path: Path) -> None:
    write_panta_series(tmp_path, "3_3_01")

    catalog = FolderScanner().scan(tmp_path)

    assert catalog.series[0].shot_id == tmp_path.name


def test_reports_missing_waveform_without_stopping_valid_series(tmp_path: Path) -> None:
    write_panta_series(tmp_path / "shot-a", "good")
    (tmp_path / "shot-a" / "missing.hdr").write_text("BlockSize 4", encoding="utf-8")

    catalog = FolderScanner().scan(tmp_path)

    assert len(catalog.series) == 1
    assert catalog.is_partial
    assert len(catalog.problems) == 1
    assert "対応ファイルがありません" in catalog.problems[0].message


def test_rejects_non_folder(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("not a folder", encoding="utf-8")

    with pytest.raises(FolderScanError, match="フォルダではありません"):
        FolderScanner().scan(path)


def test_honors_cancellation(tmp_path: Path) -> None:
    write_panta_series(tmp_path, "3_3_01")

    with pytest.raises(OperationCancelled):
        FolderScanner().scan(tmp_path, is_cancelled=lambda: True)
