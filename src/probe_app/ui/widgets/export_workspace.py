from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
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


class ExportWorkspace(QWidget):
    """Read-only Level 8 shell; editing a figure never changes analysis."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("exportWorkspace")
        self._snapshot: ExportCandidateSnapshot | None = None

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
        self._counts.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

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
        candidate_header = self._candidates.header()
        for column in (0, 1, 3, 4, 5):
            candidate_header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        candidate_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        candidate_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        self._preview = QLabel(
            "<h3>論文図プレビュー</h3>"
            "<p>図テンプレートと対象結果を確定する画面です。</p>"
            "<p>SVG / PDF / PNGの描画はLevel 8 rendererで追加します。</p>"
        )
        self._preview.setObjectName("exportPreviewPlaceholder")
        self._preview.setWordWrap(True)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            "background: white; color: #667085; border: 1px solid #d0d5dd;"
            " padding: 20px;"
        )

        self._artifact_checks: dict[ExportArtifactKind, QCheckBox] = {}
        output_group = QGroupBox("出力bundle")
        output_layout = QVBoxLayout(output_group)
        for artifact in ExportArtifactKind:
            checkbox = QCheckBox(_artifact_label(artifact))
            checkbox.setObjectName(f"exportArtifact_{artifact.name.lower()}")
            checkbox.setChecked(True)
            self._artifact_checks[artifact] = checkbox
            output_layout.addWidget(checkbox)

        self._provenance = QLabel(
            "manifestへ入力identity、Revision、解析設定、algorithm/schema/code version、"
            "採用点と除外理由を保存します。"
        )
        self._provenance.setObjectName("exportProvenancePolicy")
        self._provenance.setWordWrap(True)
        output_layout.addWidget(self._provenance)

        self._render_button = QPushButton("図bundleを作成（Level 8）")
        self._render_button.setObjectName("exportRenderButton")
        self._render_button.setEnabled(False)
        self._render_button.setToolTip(
            "このIssueでは仕様と安全な選択境界を固定し、実描画はLevel 8で追加します"
        )
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
            "background: #f8fafc; color: #475467; padding: 6px 8px;"
            " border-top: 1px solid #d0d5dd;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(body, 1)
        layout.addWidget(self._policy)

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
        """The heavy renderer stays absent until the Level 8 implementation."""

        return False

    def render_candidates(
        self,
        snapshot: ExportCandidateSnapshot | None,
        *,
        empty_message: str = "解析結果を確定すると候補を選べます",
    ) -> None:
        self._snapshot = snapshot
        self._candidates.clear()
        if snapshot is None:
            self._scope.setText(f"Export範囲: shot未選択 ｜ {empty_message}")
            self._counts.setText("初期選択 0 / 0 ｜ 注意 0")
            return

        shots = "、".join(snapshot.shot_ids)
        self._scope.setText(
            f"Export範囲: shot {shots} ｜ current revision優先"
        )
        self._counts.setText(
            f"初期選択 {snapshot.default_candidate_count:,} / "
            f"{len(snapshot.candidates):,} ｜ 注意 {snapshot.warning_count:,}"
        )
        for candidate in snapshot.candidates:
            self._candidates.addTopLevelItem(_candidate_item(candidate))


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
        (
            Qt.CheckState.Checked
            if candidate.selected_by_default
            else Qt.CheckState.Unchecked
        ),
    )
    item.setForeground(3, QBrush(QColor(color)))
    return item


def _artifact_label(artifact: ExportArtifactKind) -> str:
    return {
        ExportArtifactKind.SVG: "SVG（vector）",
        ExportArtifactKind.PDF: "PDF（vector）",
        ExportArtifactKind.PNG: "PNG（raster）",
        ExportArtifactKind.SOURCE_CSV: "source CSV",
        ExportArtifactKind.MANIFEST: "manifest（再現情報）",
    }[artifact]
