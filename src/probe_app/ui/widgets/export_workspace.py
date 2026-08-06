from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from probe_app.domain.models.analysis_result import AnalysisStatus
from probe_app.domain.models.export import (
    ExportArtifactKind,
    ExportCandidate,
    ExportCandidateSnapshot,
    ExportFigureType,
    ExportPreset,
)

_STATUS_LABELS = {
    AnalysisStatus.NOT_RUN: ("未実行", "#667085"),
    AnalysisStatus.RUNNING: ("実行中", "#175cd3"),
    AnalysisStatus.VALID: ("有効", "#067647"),
    AnalysisStatus.REVIEW: ("要確認", "#b54708"),
    AnalysisStatus.BAD: ("不適", "#b42318"),
    AnalysisStatus.ERROR: ("エラー", "#b42318"),
    AnalysisStatus.STALE: ("再計算必要", "#b54708"),
    AnalysisStatus.EXCLUDED: ("除外", "#475467"),
}

_FIGURE_LABELS = {
    ExportFigureType.IV: "単一Sweep I–V",
    ExportFigureType.FIT: "I–Vとfit根拠",
    ExportFigureType.TREND: "T_i / Phi のSweep推移",
    ExportFigureType.POSITION: "位置依存",
    ExportFigureType.METHOD_COMPARISON: "方式比較",
}

_PRESET_LABELS = {
    ExportPreset.SINGLE_COLUMN: "論文1段",
    ExportPreset.DOUBLE_COLUMN: "論文2段",
    ExportPreset.TWO_PANEL: "2 panel",
    ExportPreset.FOUR_PANEL: "4 panel",
}

EXPORT_SWEEP_ID_ROLE = int(Qt.ItemDataRole.UserRole)


@dataclass(frozen=True, slots=True)
class ExportWorkspaceRequest:
    figure_type: ExportFigureType
    preset: ExportPreset
    artifacts: tuple[ExportArtifactKind, ...]
    sweep_ids: tuple[str, ...]
    filename_stem: str


class ExportWorkspace(QWidget):
    """Paper-figure recipe editor; it never changes numerical analysis."""

    preview_requested = Signal(object)
    render_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("exportWorkspace")
        self._snapshot: ExportCandidateSnapshot | None = None
        self._updating = False

        self._figure_type = QComboBox()
        self._figure_type.setObjectName("exportFigureType")
        for figure_type, label in _FIGURE_LABELS.items():
            self._figure_type.addItem(label, figure_type)

        self._preset = QComboBox()
        self._preset.setObjectName("exportPreset")
        for preset, label in _PRESET_LABELS.items():
            self._preset.addItem(label, preset)

        self._scope = QLabel("Export範囲: shot未選択")
        self._scope.setObjectName("exportScope")
        self._scope.setWordWrap(True)
        self._scope.setStyleSheet("font-weight: 600; color: #173b6c;")

        self._counts = QLabel("初期選択 0 / 0 ｜ 注意 0")
        self._counts.setObjectName("exportCandidateCounts")
        self._counts.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        header = QFrame()
        header.setObjectName("exportHeader")
        header.setStyleSheet(
            "QFrame#exportHeader {"
            " background: #eef4ff; border-bottom: 1px solid #b7cdf5;"
            " padding: 3px;"
            "}"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 5, 8, 5)
        header_layout.addWidget(self._figure_type)
        header_layout.addWidget(self._preset)
        header_layout.addWidget(self._scope, 3)
        header_layout.addWidget(self._counts, 2)

        self._candidates = QTreeWidget()
        self._candidates.setObjectName("exportCandidateTable")
        self._candidates.setHeaderLabels(
            ["採用", "No.", "Sweep", "状態", "方式数", "Revision", "理由・警告"]
        )
        self._candidates.setAlternatingRowColors(True)
        self._candidates.setUniformRowHeights(True)
        self._candidates.itemChanged.connect(self._candidate_changed)
        candidate_header = self._candidates.header()
        for column in (0, 1, 3, 4, 5):
            candidate_header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        candidate_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        candidate_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        self._preview = QLabel("論文図プレビューを準備しています")
        self._preview.setObjectName("exportPreviewPlaceholder")
        self._preview.setWordWrap(True)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumSize(0, 0)
        self._preview.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )
        self._preview.setStyleSheet(
            "background: white; color: #667085; border: 1px solid #d0d5dd; padding: 20px;"
        )

        self._artifact_checks: dict[ExportArtifactKind, QCheckBox] = {}
        output_group = QGroupBox("出力bundle")
        output_layout = QVBoxLayout(output_group)
        for artifact in ExportArtifactKind:
            checkbox = QCheckBox(_artifact_label(artifact))
            checkbox.setObjectName(f"exportArtifact_{artifact.name.lower()}")
            checkbox.setChecked(True)
            if artifact is ExportArtifactKind.MANIFEST:
                checkbox.setEnabled(False)
            self._artifact_checks[artifact] = checkbox
            output_layout.addWidget(checkbox)

        self._filename = QLineEdit("probe-analysis-figure")
        self._filename.setObjectName("exportFilenameStem")
        self._filename.setPlaceholderText("ファイル名（拡張子なし）")
        output_layout.addWidget(QLabel("出力ファイル名"))
        output_layout.addWidget(self._filename)

        self._provenance = QLabel(
            "manifestへ入力identity、Revision、解析設定、algorithm/schema/code version、"
            "採用点と除外理由を保存します。"
        )
        self._provenance.setObjectName("exportProvenancePolicy")
        self._provenance.setWordWrap(True)
        output_layout.addWidget(self._provenance)

        self._preview_button = QPushButton("プレビューを更新")
        self._preview_button.setObjectName("exportPreviewButton")
        self._preview_button.setEnabled(False)
        output_layout.addWidget(self._preview_button)

        self._render_button = QPushButton("図bundleを作成")
        self._render_button.setObjectName("exportRenderButton")
        self._render_button.setEnabled(False)
        output_layout.addWidget(self._render_button)
        output_layout.addStretch(1)

        left = QSplitter(Qt.Orientation.Vertical)
        left.setObjectName("exportRecipeAndCandidates")
        left.setChildrenCollapsible(False)
        left.addWidget(self._preview)
        left.addWidget(self._candidates)
        left.setStretchFactor(0, 3)
        left.setStretchFactor(1, 2)
        left.setSizes([420, 280])

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setObjectName("exportWorkspaceBody")
        body.setChildrenCollapsible(False)
        body.addWidget(left)
        body.addWidget(output_group)
        body.setStretchFactor(0, 4)
        body.setStretchFactor(1, 1)
        body.setSizes([850, 260])

        self._policy = QLabel(
            "Exportは解析値を変更・再計算しません。現在のRevisionと一致する有効／要確認だけを"
            "初期選択し、stale・失敗・除外は警告付きで残します。解析sessionの保存と、"
            "論文図bundleの出力は別の操作です。"
        )
        self._policy.setObjectName("exportPolicy")
        self._policy.setWordWrap(True)
        self._policy.setStyleSheet(
            "background: #f8fafc; color: #475467; padding: 6px 8px; border-top: 1px solid #d0d5dd;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(body, 1)
        layout.addWidget(self._policy)

        self._figure_type.currentIndexChanged.connect(self._recipe_changed)
        self._preset.currentIndexChanged.connect(self._recipe_changed)
        self._preview_button.clicked.connect(self._request_preview)
        self._render_button.clicked.connect(self._request_render)
        for checkbox in self._artifact_checks.values():
            checkbox.toggled.connect(self._recipe_changed)

        self.render_candidates(None)

    @property
    def candidate_count(self) -> int:
        return self._candidates.topLevelItemCount()

    @property
    def checked_candidate_count(self) -> int:
        return sum(
            item.checkState(0) is Qt.CheckState.Checked
            for item in (
                self._candidates.topLevelItem(index)
                for index in range(self._candidates.topLevelItemCount())
            )
            if item is not None
        )

    @property
    def scope_text(self) -> str:
        return self._scope.text()

    @property
    def count_text(self) -> str:
        return self._counts.text()

    @property
    def policy_text(self) -> str:
        return self._policy.text()

    @property
    def renderer_constructed(self) -> bool:
        return True

    @property
    def request(self) -> ExportWorkspaceRequest:
        figure_type = ExportFigureType(str(self._figure_type.currentData()))
        preset = ExportPreset(str(self._preset.currentData()))
        artifacts = tuple(
            artifact for artifact, checkbox in self._artifact_checks.items() if checkbox.isChecked()
        )
        sweep_ids = tuple(
            str(item.data(0, EXPORT_SWEEP_ID_ROLE))
            for item in (
                self._candidates.topLevelItem(index)
                for index in range(self._candidates.topLevelItemCount())
            )
            if item is not None and item.checkState(0) is Qt.CheckState.Checked
        )
        return ExportWorkspaceRequest(
            figure_type=figure_type,
            preset=preset,
            artifacts=artifacts,
            sweep_ids=sweep_ids,
            filename_stem=self._filename.text().strip(),
        )

    def show_preview(self, image: QImage, message: str = "") -> None:
        pixmap = QPixmap.fromImage(image)
        target = self._preview.contentsRect().size()
        self._preview.setPixmap(
            pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._preview.setStyleSheet(
            "background: white; color: #667085; border: 1px solid #d0d5dd; padding: 8px;"
        )
        self._preview.setToolTip(message)

    def show_error(self, message: str) -> None:
        self._preview.setPixmap(QPixmap())
        self._preview.setText(message)
        self._preview.setStyleSheet(
            "background: #fff; color: #b42318; border: 1px solid #fda29b; padding: 20px;"
        )

    def show_exported(self, message: str) -> None:
        self._scope.setText(message)

    def render_candidates(
        self,
        snapshot: ExportCandidateSnapshot | None,
        *,
        empty_message: str = "解析結果を確定すると候補を選べます",
    ) -> None:
        self._snapshot = snapshot
        self._updating = True
        self._candidates.clear()
        if snapshot is None:
            self._scope.setText(f"Export範囲: shot未選択 ｜ {empty_message}")
            self._counts.setText("初期選択 0 / 0 ｜ 注意 0")
            self._preview_button.setEnabled(False)
            self._render_button.setEnabled(False)
            self._updating = False
            return

        shots = "、".join(snapshot.shot_ids)
        self._scope.setText(f"Export範囲: shot {shots} ｜ current revision優先")
        self._counts.setText(
            f"初期選択 {snapshot.default_candidate_count:,} / "
            f"{len(snapshot.candidates):,} ｜ 注意 {snapshot.warning_count:,}"
        )
        for candidate in snapshot.candidates:
            self._candidates.addTopLevelItem(_candidate_item(candidate))
        self._filename.setText(f"{snapshot.shot_ids[0]}-analysis")
        self._preview_button.setEnabled(bool(snapshot.candidates))
        self._render_button.setEnabled(bool(snapshot.candidates))
        self._updating = False
        if snapshot.candidates:
            self._preview.setPixmap(QPixmap())
            self._preview.setText("設定を確認して「プレビューを更新」を押してください")

    def _candidate_changed(self, _item: QTreeWidgetItem, _column: int) -> None:
        if self._updating or self._snapshot is None:
            return
        self._counts.setText(
            f"選択 {self.checked_candidate_count:,} / "
            f"{len(self._snapshot.candidates):,} ｜ "
            f"注意 {self._snapshot.warning_count:,}"
        )
        self._preview.setPixmap(QPixmap())
        self._preview.setText("設定を確認して「プレビューを更新」を押してください")

    def _recipe_changed(self, _value: object = None) -> None:
        if not self._updating and self._snapshot is not None:
            self._preview.setPixmap(QPixmap())
            self._preview.setText("設定が変わりました。プレビューを更新してください")

    def _request_preview(self) -> None:
        try:
            request = self.request
        except ValueError as error:
            self.show_error(str(error))
            return
        self.preview_requested.emit(request)

    def _request_render(self) -> None:
        try:
            request = self.request
        except ValueError as error:
            self.show_error(str(error))
            return
        self.render_requested.emit(request)


def _candidate_item(candidate: ExportCandidate) -> QTreeWidgetItem:
    status_label, color = _STATUS_LABELS[candidate.status]
    item = QTreeWidgetItem(
        [
            "",
            str(candidate.number),
            candidate.sweep_id,
            status_label,
            str(len(candidate.available_methods)),
            "一致" if candidate.current_revision else "古い",
            candidate.reason,
        ]
    )
    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
    item.setCheckState(
        0,
        (Qt.CheckState.Checked if candidate.selected_by_default else Qt.CheckState.Unchecked),
    )
    item.setForeground(3, QBrush(QColor(color)))
    item.setData(0, EXPORT_SWEEP_ID_ROLE, candidate.sweep_id)
    return item


def _artifact_label(artifact: ExportArtifactKind) -> str:
    return {
        ExportArtifactKind.SVG: "SVG（vector）",
        ExportArtifactKind.PDF: "PDF（vector）",
        ExportArtifactKind.PNG: "PNG（raster）",
        ExportArtifactKind.SOURCE_CSV: "source CSV",
        ExportArtifactKind.MANIFEST: "manifest（再現情報）",
    }[artifact]
