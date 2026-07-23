from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from probe_app.domain.errors import HeaderParseError


@dataclass(frozen=True, slots=True)
class PantaHeader:
    block_size: int
    value_resolution: float
    value_offset: float
    time_resolution: float
    time_offset: float
    endian: str
    data_type: str
    data_offset: int
    value_unit: str
    time_unit: str
    trace_name: str
    date: str
    time: str
    model: str
    fields: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> PantaHeader:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise HeaderParseError(path, f"ヘッダーを開けません: {exc}") from exc

        fields: dict[str, str] = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("$", "/", "#")):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                fields[parts[0]] = parts[1].strip()

        def required(name: str) -> str:
            value = fields.get(name)
            if value in (None, ""):
                raise HeaderParseError(path, f"必須項目 {name} がありません")
            return value

        try:
            block_size = int(required("BlockSize"))
            value_resolution = float(required("VResolution"))
            value_offset = float(required("VOffset"))
            time_resolution = float(required("HResolution"))
            time_offset = float(fields.get("HOffset", "0"))
            data_offset = int(fields.get("DataOffset", "0"))
        except ValueError as exc:
            raise HeaderParseError(path, f"数値項目の形式が不正です: {exc}") from exc

        if block_size <= 0:
            raise HeaderParseError(path, "BlockSize は1以上である必要があります")
        if time_resolution <= 0:
            raise HeaderParseError(path, "HResolution は正である必要があります")
        if data_offset < 0:
            raise HeaderParseError(path, "DataOffset は0以上である必要があります")

        return cls(
            block_size=block_size,
            value_resolution=value_resolution,
            value_offset=value_offset,
            time_resolution=time_resolution,
            time_offset=time_offset,
            endian=fields.get("Endian", "Ltl"),
            data_type=fields.get("VDataType", "IS2"),
            data_offset=data_offset,
            value_unit=fields.get("VUnit", ""),
            time_unit=fields.get("HUnit", "s"),
            trace_name=fields.get("TraceName", ""),
            date=fields.get("Date", ""),
            time=fields.get("Time", ""),
            model=fields.get("Model", ""),
            fields=fields,
        )

    @property
    def numpy_dtype(self) -> str:
        normalized_type = self.data_type.strip().upper()
        if normalized_type not in {"IS2", "I16", "INT16"}:
            raise ValueError(f"未対応のVDataTypeです: {self.data_type}")
        byte_order = "<" if self.endian.strip().lower() in {"ltl", "little", "le"} else ">"
        return f"{byte_order}i2"

    @property
    def recorded_at(self) -> str:
        return " ".join(part for part in (self.date, self.time) if part).strip()
