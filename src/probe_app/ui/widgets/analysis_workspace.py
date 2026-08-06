from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from probe_app.domain.models.analysis_result import (
    ANALYSIS_STAGE_ORDER,
    AnalysisStage,
    AnalysisStatus,
    SweepAnalysisRecord,
)
from probe_app.domain.models.sweep import Sweep, SweepDirection
from probe_app.ui.widgets.fit_analysis_panel import FitAnalysisPanel
from probe_app.ui.widgets.preprocessing_panel import PreprocessingPanel
from probe_app.ui.widgets.sweep_iv_plot import SweepIVPlot

_STAGE_TITLES = {
    AnalysisStage.PREPROCESSING: "1  平滑化・微分",
    AnalysisStage.POTENTIAL: "2  V_f・Phi",
    AnalysisStage.SATURATION: "3  飽和域 fit",
    AnalysisStage.TEMPERATURE: "4  T_i model fit",
    AnalysisStage.QUALITY: "5  品質確認",
}

_STATUS_PRESENTATION = {
    AnalysisStatus.NOT_RUN: ("—  未実行", "#667085", "#f2f4f7"),
    AnalysisStatus.RUNNING: ("…  実行中", "#175cd3", "#eff8ff"),
    AnalysisStatus.VALID: ("✓  完了", "#067647", "#ecfdf3"),
    AnalysisStatus.REVIEW: ("!  要確認", "#b54708", "#fffaeb"),
    AnalysisStatus.BAD: ("×  不適", "#b42318", "#fef3f2"),
    AnalysisStatus.ERROR: ("×  エラー", "#b42318", "#fef3f2"),
    AnalysisStatus.STALE: ("↻  再計算必要", "#b54708", "#fff4e5"),
    AnalysisStatus.EXCLUDED: ("⊘  除外", "#475467", "#f2f4f7"),
}


class AnalysisWorkspace(QWidget):
    """Level 3–6 analysis shell with one shared selected-Sweep context."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("analysisWorkspace")

        self.plot = SweepIVPlot()
        self.plot.setObjectName("analysisIVPlot")
        self.preprocessing_panel = PreprocessingPanel()
        self.preprocessing_panel.setObjectName("analysisPreprocessingControls")
        self.fit_panel = FitAnalysisPanel()
        self.fit_panel.setObjectName("analysisFitControls")

        self._context = QLabel("解析対象: Sweep未選択")
        self._context.setObjectName("analysisContext")
        self._context.setWordWrap(True)
        self._context.setStyleSheet("font-weight: 600; color: #173b6c;")

        self._revision = QLabel("Revision: 未作成")
        self._revision.setObjectName("analysisRevisionStatus")
        self._revision.setWordWrap(True)
        self._revision.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        header = QFrame()
        header.setObjectName("analysisHeader")
        header.setStyleSheet(
            "QFrame#analysisHeader {"
            " background: #eef4ff; border-bottom: 1px solid #b7cdf5;"
            " padding: 3px;"
            "}"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 5, 8, 5)
        header_layout.addWidget(self._context, 3)
        header_layout.addWidget(self._revision, 2)

        stage_group = QGroupBox("解析工程")
        stage_group.setObjectName("analysisStageRail")
        stage_layout = QVBoxLayout(stage_group)
        stage_layout.setContentsMargins(7, 9, 7, 9)
        stage_layout.setSpacing(6)
        self._stage_labels: dict[AnalysisStage, QLabel] = {}
        for stage in ANALYSIS_STAGE_ORDER:
            label = QLabel()
            label.setObjectName(f"analysisStage_{stage.value}")
            label.setWordWrap(True)
            label.setMinimumHeight(50)
            self._stage_labels[stage] = label
            stage_layout.addWidget(label)
        stage_layout.addStretch(1)

        inspector = QWidget()
        inspector.setObjectName("analysisInspector")
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_layout.addWidget(self.preprocessing_panel)
        inspector_layout.addWidget(self.fit_panel)
        inspector_layout.addStretch(1)

        inspector_scroll = QScrollArea()
        inspector_scroll.setObjectName("analysisInspectorScroll")
        inspector_scroll.setWidgetResizable(True)
        inspector_scroll.setWidget(inspector)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setObjectName("analysisWorkspaceBody")
        body.setChildrenCollapsible(False)
        body.addWidget(stage_group)
        body.addWidget(self.plot)
        body.addWidget(inspector_scroll)
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 6)
        body.setStretchFactor(2, 2)
        body.setSizes([145, 760, 265])

        self._impact = QLabel(
            "前処理やFit設定を変更しても自動再計算しません。"
            "明示ボタンを押した時だけ新しいRevisionで再評価します。"
        )
        self._impact.setObjectName("analysisImpactNotice")
        self._impact.setWordWrap(True)
        self._impact.setStyleSheet(
            "background: #f8fafc; color: #475467; padding: 5px 8px; border-top: 1px solid #d0d5dd;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(body, 1)
        layout.addWidget(self._impact)

        self.render_state(None, None)

    @property
    def context_text(self) -> str:
        return self._context.text()

    @property
    def revision_text(self) -> str:
        return self._revision.text()

    @property
    def impact_text(self) -> str:
        return self._impact.text()

    def stage_text(self, stage: AnalysisStage) -> str:
        return self._stage_labels[stage].text()

    def render_state(
        self,
        sweep: Sweep | None,
        record: SweepAnalysisRecord | None,
        *,
        empty_message: str = "Sweep分割後に一覧から解析対象を選択してください",
    ) -> None:
        if sweep is None:
            self._context.setText(f"解析対象: Sweep未選択 ｜ {empty_message}")
            self._revision.setText("Revision: 未作成")
            self._revision.setStyleSheet("color: #667085;")
            self._impact.setText(
                "Sweepを選択すると、前処理から品質確認までの解析工程を開始できます。"
            )
            self._render_stages(None)
            return

        direction = "上昇" if sweep.direction is SweepDirection.UP else "下降"
        self._context.setText(
            f"解析対象: {sweep.sweep_id} ｜ {direction} ｜ {sweep.point_count:,} 点"
        )
        if record is None:
            self._revision.setText("Revision: 未作成 ｜ 前処理は未実行")
            self._revision.setStyleSheet("color: #667085;")
            self._impact.setText(
                "設定を確認し「前処理を再計算」を押してください。"
                "タブを切り替えただけでは計算しません。"
            )
        else:
            status_text, color, _ = _STATUS_PRESENTATION[record.status]
            self._revision.setText(f"Revision: {record.revision.cache_key[:10]}… ｜ {status_text}")
            self._revision.setStyleSheet(f"color: {color}; font-weight: 600;")
            if record.status is AnalysisStatus.STALE:
                self._impact.setText(f"この結果は再計算が必要です。理由: {record.message}")
            elif record.status is AnalysisStatus.ERROR:
                self._impact.setText(
                    f"前処理に失敗しました。設定を修正して明示的に再実行してください。"
                    f" 詳細: {record.message}"
                )
            else:
                self._impact.setText(
                    "前処理設定を変更して再計算すると、後続の電位・飽和域・温度・"
                    "品質結果も新しいRevisionで再評価されます。"
                )
        self._render_stages(record)

    def _render_stages(self, record: SweepAnalysisRecord | None) -> None:
        for stage in ANALYSIS_STAGE_ORDER:
            result = record.stage_result(stage) if record is not None else None
            if stage is not AnalysisStage.PREPROCESSING and result is None:
                status = AnalysisStatus.NOT_RUN
                text, color, background = _STATUS_PRESENTATION[status]
            else:
                status = result.status if result is not None else AnalysisStatus.NOT_RUN
                text, color, background = _STATUS_PRESENTATION[status]
            label = self._stage_labels[stage]
            label.setText(f"{_STAGE_TITLES[stage]}\n{text}")
            label.setStyleSheet(
                f"background: {background}; color: {color}; padding: 7px;"
                " border: 1px solid #d0d5dd; border-radius: 4px;"
                " font-weight: 600;"
            )
