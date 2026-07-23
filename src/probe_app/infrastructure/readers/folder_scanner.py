from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from probe_app.domain.errors import FolderScanError, OperationCancelled
from probe_app.domain.models.catalog import FolderCatalog, ScanProblem
from probe_app.domain.models.raw_series import RawSeriesDescriptor
from probe_app.infrastructure.readers.panta_header import PantaHeader

WAVEFORM_SUFFIXES = (".wvf", ".dat", ".dat.gz")


class FolderScanner:
    """Discover PANTA/Yokogawa header-waveform pairs below a selected folder."""

    def scan(
        self,
        folder: Path,
        *,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> FolderCatalog:
        root = folder.expanduser().resolve()
        if not root.exists():
            raise FolderScanError(root, "フォルダが存在しません")
        if not root.is_dir():
            raise FolderScanError(root, "フォルダではありません")

        descriptors: list[RawSeriesDescriptor] = []
        problems: list[ScanProblem] = []

        try:
            header_paths = sorted(
                path for path in root.rglob("*") if path.is_file() and path.suffix.lower() == ".hdr"
            )
        except OSError as exc:
            raise FolderScanError(root, f"フォルダを走査できません: {exc}") from exc

        for header_path in header_paths:
            if is_cancelled is not None and is_cancelled():
                raise OperationCancelled()
            data_path = self._find_waveform(header_path)
            if data_path is None:
                problems.append(
                    ScanProblem(
                        path=header_path,
                        message=".wvf / .dat / .dat.gz の対応ファイルがありません",
                    )
                )
                continue
            try:
                header = PantaHeader.from_file(header_path)
            except Exception as exc:
                problems.append(ScanProblem(path=header_path, message=str(exc)))
                continue
            descriptors.append(self._descriptor(root, header_path, data_path, header))

        descriptors.sort(key=lambda item: (item.shot_id, item.channel_id, item.series_id))
        return FolderCatalog(root=root, series=tuple(descriptors), problems=tuple(problems))

    @staticmethod
    def _find_waveform(header_path: Path) -> Path | None:
        filenames = {
            item.name.lower(): item for item in header_path.parent.iterdir() if item.is_file()
        }
        stem = header_path.stem
        for suffix in WAVEFORM_SUFFIXES:
            match = filenames.get(f"{stem}{suffix}".lower())
            if match is not None:
                return match
        return None

    @staticmethod
    def _descriptor(
        root: Path,
        header_path: Path,
        data_path: Path,
        header: PantaHeader,
    ) -> RawSeriesDescriptor:
        relative_header = header_path.relative_to(root)
        relative_parent = relative_header.parent
        shot_id = root.name if relative_parent == Path(".") else relative_parent.as_posix()
        series_id = relative_header.with_suffix("").as_posix()
        return RawSeriesDescriptor(
            series_id=series_id,
            shot_id=shot_id,
            channel_id=header_path.stem,
            header_path=header_path,
            data_path=data_path,
            sample_count=header.block_size,
            value_unit=header.value_unit,
            time_unit=header.time_unit,
            trace_name=header.trace_name,
            recorded_at=header.recorded_at,
            metadata={
                "model": header.model,
                "data_type": header.data_type,
                "endian": header.endian,
            },
        )
