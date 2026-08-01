from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, QSizeF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPageSize,
    QPainter,
    QPdfWriter,
    QPen,
    QPolygonF,
)
from PySide6.QtSvg import QSvgGenerator

from probe_app.domain.models.export import (
    ExportArtifactKind,
    ExportManifest,
    PanelSpec,
    SeriesStyle,
)
from probe_app.domain.models.export_source import (
    ExportSourcePoint,
    ExportSourceTable,
)


class ExportRenderError(RuntimeError):
    pass


class ExportBundleExistsError(ExportRenderError):
    def __init__(self, paths: tuple[Path, ...]) -> None:
        self.paths = paths
        super().__init__(
            "同名の出力があります: " + ", ".join(path.name for path in paths)
        )


@dataclass(frozen=True, slots=True)
class ExportBundleResult:
    output_directory: Path
    manifest_id: str
    artifacts: tuple[Path, ...]


class PaperRenderer:
    """Dedicated manifest/source renderer independent from on-screen widgets."""

    def render_bundle(
        self,
        manifest: ExportManifest,
        source: ExportSourceTable,
        output_directory: Path,
    ) -> ExportBundleResult:
        output = output_directory.expanduser().resolve(strict=False)
        output.mkdir(parents=True, exist_ok=True)
        targets = tuple(output / name for name in manifest.artifact_filenames)
        existing = tuple(path for path in targets if path.exists())
        if existing:
            raise ExportBundleExistsError(existing)
        temporary = Path(tempfile.mkdtemp(prefix=".probe-export-", dir=output))
        staged: list[tuple[Path, Path]] = []
        moved: list[Path] = []
        try:
            for artifact, target in zip(manifest.artifacts, targets, strict=True):
                staged_path = temporary / target.name
                self._render_artifact(artifact, staged_path, manifest, source)
                staged.append((staged_path, target))
            for staged_path, target in staged:
                os.replace(staged_path, target)
                moved.append(target)
        except (OSError, ValueError) as error:
            for path in moved:
                path.unlink(missing_ok=True)
            raise ExportRenderError(f"図bundleを完成できません: {error}") from error
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
        return ExportBundleResult(output, manifest.manifest_id, targets)

    def render_preview(
        self,
        manifest: ExportManifest,
        source: ExportSourceTable,
        *,
        width_px: int = 1200,
    ) -> QImage:
        ratio = manifest.figure.height_mm / manifest.figure.width_mm
        image = QImage(
            QSize(width_px, max(200, round(width_px * ratio))),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(Qt.GlobalColor.white)
        self._paint(image, manifest, source)
        return image

    def _render_artifact(
        self,
        artifact: ExportArtifactKind,
        path: Path,
        manifest: ExportManifest,
        source: ExportSourceTable,
    ) -> None:
        if artifact is ExportArtifactKind.MANIFEST:
            path.write_text(manifest.canonical_json + "\n", encoding="utf-8")
            return
        if artifact is ExportArtifactKind.SOURCE_CSV:
            path.write_text(source.canonical_csv, encoding="utf-8")
            return
        if artifact is ExportArtifactKind.SVG:
            generator = QSvgGenerator()
            generator.setFileName(str(path))
            generator.setSize(self._pixel_size(manifest, 96))
            generator.setViewBox(
                QRectF(
                    0,
                    0,
                    generator.size().width(),
                    generator.size().height(),
                )
            )
            generator.setTitle(manifest.filename_stem)
            generator.setDescription(
                f"Probe Analizer manifest {manifest.manifest_id}"
            )
            self._paint(generator, manifest, source)
            return
        if artifact is ExportArtifactKind.PDF:
            writer = QPdfWriter(str(path))
            writer.setPageSize(
                QPageSize(
                    QSizeF(
                        manifest.figure.width_mm,
                        manifest.figure.height_mm,
                    ),
                    QPageSize.Unit.Millimeter,
                )
            )
            writer.setResolution(300)
            writer.setTitle(manifest.filename_stem)
            self._paint(writer, manifest, source)
            return
        if artifact is ExportArtifactKind.PNG:
            image = QImage(
                self._pixel_size(manifest, manifest.figure.dpi),
                QImage.Format.Format_ARGB32_Premultiplied,
            )
            image.fill(Qt.GlobalColor.white)
            dots_per_meter = round(manifest.figure.dpi / 0.0254)
            image.setDotsPerMeterX(dots_per_meter)
            image.setDotsPerMeterY(dots_per_meter)
            self._paint(image, manifest, source)
            if not image.save(str(path)):
                raise ExportRenderError(f"PNGを書き込めません: {path}")

    def _paint(
        self,
        device: object,
        manifest: ExportManifest,
        source: ExportSourceTable,
    ) -> None:
        painter = QPainter()
        if not painter.begin(device):  # type: ignore[arg-type]
            raise ExportRenderError("描画deviceを開始できません")
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.fillRect(
                QRectF(0, 0, painter.device().width(), painter.device().height()),
                Qt.GlobalColor.white,
            )
            self._paint_panels(painter, manifest, source)
        finally:
            painter.end()

    def _paint_panels(
        self,
        painter: QPainter,
        manifest: ExportManifest,
        source: ExportSourceTable,
    ) -> None:
        width = float(painter.device().width())
        height = float(painter.device().height())
        margin = max(18.0, width * 0.055)
        gap = max(12.0, height * 0.035)
        panels = manifest.figure.panels
        panel_height = (height - 2 * margin - gap * (len(panels) - 1)) / len(panels)
        style_map = dict(manifest.styles)
        for index, panel in enumerate(panels):
            rect = QRectF(
                margin,
                margin + index * (panel_height + gap),
                width - 2 * margin,
                panel_height,
            )
            self._paint_panel(
                painter,
                rect,
                panel,
                source.for_panel(panel.panel_id),
                style_map,
            )

    def _paint_panel(
        self,
        painter: QPainter,
        rect: QRectF,
        panel: PanelSpec,
        points: tuple[ExportSourcePoint, ...],
        styles: dict[str, SeriesStyle],
    ) -> None:
        if not points:
            return
        title_height = rect.height() * 0.10
        label_margin = rect.width() * 0.09
        plot = QRectF(
            rect.left() + label_margin,
            rect.top() + title_height,
            rect.width() - label_margin * 1.25,
            rect.height() - title_height * 1.75,
        )
        painter.setPen(QPen(QColor("#111827"), 1.0))
        painter.setFont(QFont("Helvetica", max(7, round(rect.height() * 0.026))))
        painter.drawText(
            QRectF(rect.left(), rect.top(), rect.width(), title_height),
            Qt.AlignmentFlag.AlignCenter,
            panel.title,
        )
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())
        painter.drawLine(plot.bottomLeft(), plot.topLeft())

        x_min, x_max, y_min, y_max = _bounds(points)
        painter.setFont(QFont("Helvetica", max(6, round(rect.height() * 0.021))))
        painter.drawText(
            QRectF(plot.left(), plot.bottom() + 2, plot.width(), title_height * 0.65),
            Qt.AlignmentFlag.AlignCenter,
            f"{panel.x_axis.label} [{panel.x_axis.unit}]",
        )
        painter.save()
        painter.translate(rect.left() + 3, plot.center().y())
        painter.rotate(-90)
        painter.drawText(
            QRectF(-plot.height() / 2, 0, plot.height(), title_height * 0.6),
            Qt.AlignmentFlag.AlignCenter,
            f"{panel.y_axis.label} [{panel.y_axis.unit}]",
        )
        painter.restore()
        painter.drawText(
            QRectF(plot.left() - 25, plot.bottom() + 1, 50, 18),
            Qt.AlignmentFlag.AlignLeft,
            f"{x_min:.4g}",
        )
        painter.drawText(
            QRectF(plot.right() - 45, plot.bottom() + 1, 45, 18),
            Qt.AlignmentFlag.AlignRight,
            f"{x_max:.4g}",
        )
        painter.drawText(
            QRectF(plot.left() - 55, plot.bottom() - 10, 50, 18),
            Qt.AlignmentFlag.AlignRight,
            f"{y_min:.4g}",
        )
        painter.drawText(
            QRectF(plot.left() - 55, plot.top() - 8, 50, 18),
            Qt.AlignmentFlag.AlignRight,
            f"{y_max:.4g}",
        )

        series_ids = tuple(dict.fromkeys(point.series_id for point in points))
        for series_id in series_ids:
            series = tuple(point for point in points if point.series_id == series_id)
            style = styles.get(series_id, SeriesStyle("#2563eb"))
            color = QColor(style.color)
            painter.setPen(QPen(color, max(0.8, style.line_width_pt)))
            mapped = tuple(
                QPointF(
                    _map(point.x, x_min, x_max, plot.left(), plot.right()),
                    _map(point.y, y_min, y_max, plot.bottom(), plot.top()),
                )
                for point in series
            )
            if len(mapped) > 1:
                painter.drawPolyline(QPolygonF(mapped))
            if style.marker != "none" or len(mapped) == 1:
                for mapped_point in mapped:
                    painter.setBrush(color)
                    painter.drawEllipse(mapped_point, 2.5, 2.5)
            if panel.show_error_bars:
                for point, mapped_point in zip(series, mapped, strict=True):
                    if point.y_error is None:
                        continue
                    top = _map(
                        point.y + point.y_error,
                        y_min,
                        y_max,
                        plot.bottom(),
                        plot.top(),
                    )
                    bottom = _map(
                        point.y - point.y_error,
                        y_min,
                        y_max,
                        plot.bottom(),
                        plot.top(),
                    )
                    painter.drawLine(
                        QPointF(mapped_point.x(), top),
                        QPointF(mapped_point.x(), bottom),
                    )
            painter.setBrush(Qt.BrushStyle.NoBrush)
        if panel.show_legend:
            self._paint_legend(painter, plot, series_ids, styles)

    def _paint_legend(
        self,
        painter: QPainter,
        plot: QRectF,
        series_ids: tuple[str, ...],
        styles: dict[str, SeriesStyle],
    ) -> None:
        line_height = 14.0
        width = min(plot.width() * 0.42, 210.0)
        legend = QRectF(
            plot.right() - width - 5,
            plot.top() + 5,
            width,
            line_height * len(series_ids) + 6,
        )
        painter.fillRect(legend, QColor(255, 255, 255, 220))
        painter.setFont(QFont("Helvetica", 7))
        for index, series_id in enumerate(series_ids):
            y = legend.top() + 5 + line_height * index + line_height / 2
            style = styles.get(series_id, SeriesStyle("#2563eb"))
            painter.setPen(QPen(QColor(style.color), 1.5))
            painter.drawLine(QPointF(legend.left() + 5, y), QPointF(legend.left() + 22, y))
            painter.setPen(QPen(QColor("#111827"), 1.0))
            painter.drawText(
                QRectF(legend.left() + 27, y - 7, legend.width() - 30, 14),
                Qt.AlignmentFlag.AlignVCenter,
                series_id,
            )

    @staticmethod
    def _pixel_size(manifest: ExportManifest, dpi: int) -> QSize:
        return QSize(
            max(1, round(manifest.figure.width_mm / 25.4 * dpi)),
            max(1, round(manifest.figure.height_mm / 25.4 * dpi)),
        )


def _bounds(points: tuple[ExportSourcePoint, ...]) -> tuple[float, float, float, float]:
    x_values = [point.x for point in points]
    y_lows = [point.y - (point.y_error or 0.0) for point in points]
    y_highs = [point.y + (point.y_error or 0.0) for point in points]
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_lows), max(y_highs)
    if x_min == x_max:
        x_min -= 0.5
        x_max += 0.5
    if y_min == y_max:
        y_min -= 0.5
        y_max += 0.5
    x_padding = (x_max - x_min) * 0.04
    y_padding = (y_max - y_min) * 0.08
    return (
        x_min - x_padding,
        x_max + x_padding,
        y_min - y_padding,
        y_max + y_padding,
    )


def _map(value: float, minimum: float, maximum: float, start: float, stop: float) -> float:
    return start + (value - minimum) / (maximum - minimum) * (stop - start)
