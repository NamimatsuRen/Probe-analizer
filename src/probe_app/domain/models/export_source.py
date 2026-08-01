from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExportSourcePoint:
    panel_id: str
    series_id: str
    point_id: str
    x: float
    y: float
    x_unit: str
    y_unit: str
    kind: str
    status: str
    shot_id: str = ""
    sweep_id: str = ""
    method_id: str = ""
    y_error: float | None = None

    def __post_init__(self) -> None:
        if not self.panel_id.strip() or not self.series_id.strip():
            raise ValueError("export panel and series identity cannot be empty")
        if not self.point_id.strip() or not self.kind.strip():
            raise ValueError("export point identity and kind cannot be empty")
        if not math.isfinite(self.x) or not math.isfinite(self.y):
            raise ValueError("export point coordinates must be finite")
        if self.y_error is not None and (
            not math.isfinite(self.y_error) or self.y_error < 0
        ):
            raise ValueError("y_error must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ExportSourceTable:
    points: tuple[ExportSourcePoint, ...]

    def __post_init__(self) -> None:
        if not self.points:
            raise ValueError("export source table cannot be empty")
        point_ids = tuple(point.point_id for point in self.points)
        if len(point_ids) != len(set(point_ids)):
            raise ValueError("export point IDs must be unique")

    @property
    def panel_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(point.panel_id for point in self.points))

    @property
    def series_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(point.series_id for point in self.points))

    def for_panel(self, panel_id: str) -> tuple[ExportSourcePoint, ...]:
        return tuple(point for point in self.points if point.panel_id == panel_id)

    @property
    def canonical_csv(self) -> str:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            (
                "panel_id",
                "series_id",
                "point_id",
                "x",
                "y",
                "y_error",
                "x_unit",
                "y_unit",
                "kind",
                "status",
                "shot_id",
                "sweep_id",
                "method_id",
            )
        )
        for point in self.points:
            writer.writerow(
                (
                    point.panel_id,
                    point.series_id,
                    point.point_id,
                    format(point.x, ".17g"),
                    format(point.y, ".17g"),
                    "" if point.y_error is None else format(point.y_error, ".17g"),
                    point.x_unit,
                    point.y_unit,
                    point.kind,
                    point.status,
                    point.shot_id,
                    point.sweep_id,
                    point.method_id,
                )
            )
        return stream.getvalue()
