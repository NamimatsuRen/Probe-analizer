from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np


def write_panta_series(
    folder: Path,
    name: str = "3_3_01",
    *,
    samples: np.ndarray | None = None,
    compressed: bool = False,
    endian: str = "Ltl",
    resolution: float = 0.5,
    offset: float = 1.0,
    time_resolution: float = 0.1,
    time_offset: float = 0.5,
) -> tuple[Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    sample_data = (
        np.asarray(samples, dtype=np.int16)
        if samples is not None
        else np.asarray([0, 1, -2, 4], dtype=np.int16)
    )
    dtype = np.dtype("<i2" if endian.lower() == "ltl" else ">i2")
    payload = sample_data.astype(dtype).tobytes()
    header = folder / f"{name}.hdr"
    header.write_text(
        "\n".join(
            [
                "$PublicInfo",
                "FormatVersion 1.01",
                "Model WE7275",
                f"Endian {endian}",
                "DataFormat Block",
                "DataOffset 0",
                "$Group1",
                "TraceName CH1",
                f"BlockSize {sample_data.size}",
                f"VResolution {resolution}",
                f"VOffset {offset}",
                "VDataType IS2",
                "VUnit V",
                f"HResolution {time_resolution}",
                f"HOffset {time_offset}",
                "HUnit s",
                "Date 2026/07/23",
                "Time 12:34:56",
            ]
        ),
        encoding="utf-8",
    )
    if compressed:
        data = folder / f"{name}.dat.gz"
        with gzip.open(data, "wb") as stream:
            stream.write(payload)
    else:
        data = folder / f"{name}.dat"
        data.write_bytes(payload)
    return header, data
