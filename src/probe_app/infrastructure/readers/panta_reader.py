from __future__ import annotations

import gzip
from collections.abc import Callable

import numpy as np

from probe_app.domain.errors import OperationCancelled, RawDataReadError
from probe_app.domain.models.raw_series import RawSeries, RawSeriesDescriptor
from probe_app.infrastructure.readers.panta_header import PantaHeader


class PantaRawReader:
    """Decode one PANTA/Yokogawa waveform using its sibling header."""

    def read(
        self,
        descriptor: RawSeriesDescriptor,
        *,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> RawSeries:
        if is_cancelled is not None and is_cancelled():
            raise OperationCancelled()

        header = PantaHeader.from_file(descriptor.header_path)
        try:
            dtype = np.dtype(header.numpy_dtype)
        except ValueError as exc:
            raise RawDataReadError(descriptor.data_path, str(exc)) from exc

        expected_bytes = header.block_size * dtype.itemsize
        try:
            if descriptor.data_path.name.lower().endswith(".gz"):
                with gzip.open(descriptor.data_path, "rb") as stream:
                    if header.data_offset:
                        stream.seek(header.data_offset)
                    payload = stream.read(expected_bytes)
            else:
                with descriptor.data_path.open("rb") as stream:
                    if header.data_offset:
                        stream.seek(header.data_offset)
                    payload = stream.read(expected_bytes)
        except OSError as exc:
            raise RawDataReadError(descriptor.data_path, f"波形を開けません: {exc}") from exc

        if len(payload) != expected_bytes:
            actual_points = len(payload) // dtype.itemsize
            raise RawDataReadError(
                descriptor.data_path,
                f"{header.block_size}点を期待しましたが{actual_points}点しかありません",
            )
        if is_cancelled is not None and is_cancelled():
            raise OperationCancelled()

        raw = np.frombuffer(payload, dtype=dtype, count=header.block_size)
        values = raw.astype(np.float64, copy=False) * header.value_resolution + header.value_offset
        # Keep the legacy pantaADC sampling-axis convention for result comparison.
        # HOffset is treated as a sample offset and samples start at index 1.
        time_s = header.time_resolution * (
            np.arange(header.block_size, dtype=np.float64) + 1.0 + header.time_offset
        )
        return RawSeries(descriptor=descriptor, time_s=time_s, values=values)
