from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from probe_app.domain.models.analysis_result import AnalysisStatus
from probe_app.domain.models.summary import (
    SUMMARY_METHOD_ORDER,
    SummaryMethod,
    SummaryMetric,
    SummaryRow,
    SummarySnapshot,
)
from probe_app.domain.models.sweep import SweepDirection
from probe_app.ui.widgets.summary_trend_plot import SummaryTrendPlot

SUMMARY_SWEEP_ID_ROLE = int(Qt.ItemDataRole.UserRole)

_STATUS_PRESENTATION = {
    AnalysisStatus.NOT_RUN: ("未実行", "#667085", "#f2f4f7"),
    AnalysisStatus.RUNNING: ("実行中", "#175cd3", "#eff8ff"),
    AnalysisStatus.VALID: ("有効", "#067647", "#ecfdf3"),
    AnalysisStatus.REVIEW: ("要確認", "#b54708", "#fffaeb"),
    AnalysisStatus.BAD: ("不適", "#b42318", "#fef3f2"),
    AnalysisStatus.ERROR: ("エラー", "#b42318", "#fef3f2"),
    AnalysisStatus.STALE: ("再計算必要", "#b54708", "#fff4e5"),
    AnalysisStatus.EXCLUDED: ("除外", "#475467", "#f2f4f7"),
}

_METHOD_LABELS = {
    SummaryMethod.FILTERED_LOG: "Filtered / log交点",
    SummaryMethod.FILTERED_DERIVATIVE: "Filtered / dI/dV",
    SummaryMethod.RAW_LOG: "Raw / log交点",
    SummaryMethod.RAW_DERIVATIVE: "Raw / 多窓dI/dV",
}


class SummaryWorkspace(QWidget):
    """Read-only Summary shell that never triggers numerical analysis."""

    sweep_selected = Signal(str)
    open_analysis_requested = Signal(str)
    exclusion_requested = Signal(str, str)
    restore_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("summaryWorkspace")
        self._snapshot: SummarySnapshot | None = None
        self._rows: dict[str, SummaryRow] = {}

        self._scope = QComboBox()
        self._scope.setObjectName("summaryScope")
        self._scope.addItem("現在のshot")
        self._scope.setEnabled(False)
        self._scope.setToolTip(
            "複数shot・位置集計は位置metadata契約の確定後に追加します"
        )

        self._context = QLabel("集計範囲: shot未選択")
        self._context.setObjectName("summaryContext")
        self._context.setWordWrap(True)
        self._context.setStyleSheet("font-weight: 600; color: #173b6c;")

        self._denominator = QLabel("既定集計: 0 / 0 Sweep")
        self._denominator.setObjectName("summaryDenominator")
        self._denominator.setWordWrap(True)
        self._denominator.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        header = QFrame()
        header.setObjectName("summaryHeader")
        header.setStyleSheet(
            "QFrame#summaryHeader {"
            " background: #eef4ff; border-bottom: 1px solid #b7cdf5;"
            " padding: 3px;"
            "}"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 5, 8, 5)
        header_layout.addWidget(self._scope)
        header_layout.addWidget(self._context, 3)
        header_layout.addWidget(self._denominator, 2)

        self._status_labels: dict[AnalysisStatus, QLabel] = {}
        status_bar = QFrame()
        status_bar.setObjectName("summaryStatusCounts")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(8, 6, 8, 6)
        status_layout.setSpacing(5)
        for status in AnalysisStatus:
            label = QLabel()
            label.setObjectName(f"summaryStatus_{status.value}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumWidth(72)
            self._status_labels[status] = label
            status_layout.addWidget(label)

        self._ti_plot = SummaryTrendPlot(SummaryMetric.TI)
        self._ti_plot.setObjectName("summaryTiTrendPlot")
        self._phi_plot = SummaryTrendPlot(SummaryMetric.PHI)
        self._phi_plot.setObjectName("summaryPhiTrendPlot")
        self._ti_plot.sweep_selected.connect(self._plot_sweep_selected)
        self._phi_plot.sweep_selected.connect(self._plot_sweep_selected)

        trend_plots = QSplitter(Qt.Orientation.Horizontal)
        trend_plots.setObjectName("summaryTrendPlots")
        trend_plots.setChildrenCollapsible(False)
        trend_plots.addWidget(self._ti_plot)
        trend_plots.addWidget(self._phi_plot)
        trend_plots.setStretchFactor(0, 1)
        trend_plots.setStretchFactor(1, 1)
        trend_plots.setSizes([580, 580])

        self._averages = QTreeWidget()
        self._averages.setObjectName("summaryAverageTable")
        self._averages.setHeaderLabels(
            [
                "方式",
                "T_i 平均 [eV]",
                "T_i SD [eV]",
                "T_i 採用数",
                "Phi 平均 [V]",
                "Phi SD [V]",
                "Phi 採用数",
            ]
        )
        self._averages.setAlternatingRowColors(True)
        self._averages.setUniformRowHeights(True)
        self._averages.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._averages.setMaximumHeight(165)
        average_header = self._averages.header()
        average_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, self._averages.columnCount()):
            average_header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        average_group = QGroupBox(
            "方式別平均（current revision・有効/要確認、T_iは0–5 eV）"
        )
        average_group.setObjectName("summaryAverages")
        average_layout = QVBoxLayout(average_group)
        average_layout.addWidget(self._averages)

        trend_page = QWidget()
        trend_page_layout = QVBoxLayout(trend_page)
        trend_page_layout.setContentsMargins(6, 6, 6, 6)
        trend_page_layout.addWidget(trend_plots, 1)
        trend_page_layout.addWidget(average_group)

        self._tree = QTreeWidget()
        self._tree.setObjectName("summarySweepTable")
        self._tree.setHeaderLabels(
            [
                "No.",
                "Sweep",
                "方向",
                "開始 [ms]",
                "終了 [ms]",
                "状態",
                "T_i方式数",
                "Phi方式数",
                "Revision",
                "理由・注記",
            ]
        )
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.itemSelectionChanged.connect(self._selection_changed)
        tree_header = self._tree.header()
        for column in (0, 2, 3, 4, 5, 6, 7, 8):
            tree_header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        tree_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        tree_header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)

        self._selected = QLabel("Sweepを選択すると4方式の状態を確認できます")
        self._selected.setObjectName("summarySelectedSweep")
        self._selected.setWordWrap(True)

        self._methods = QTreeWidget()
        self._methods.setObjectName("summaryMethodTable")
        self._methods.setHeaderLabels(
            ["方式", "状態", "Phi [V]", "T_i [eV]", "K [V⁻¹]", "Kの由来"]
        )
        self._methods.setAlternatingRowColors(True)
        self._methods.setUniformRowHeights(True)
        self._methods.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        method_header = self._methods.header()
        for column in range(self._methods.columnCount() - 1):
            method_header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        method_header.setSectionResizeMode(
            self._methods.columnCount() - 1,
            QHeaderView.ResizeMode.Stretch,
        )

        self._open_analysis = QPushButton("解析で確認")
        self._open_analysis.setObjectName("openSummarySweepInAnalysis")
        self._open_analysis.setEnabled(False)
        self._open_analysis.clicked.connect(self._request_analysis)

        self._exclusion_reason = QLineEdit()
        self._exclusion_reason.setObjectName("summaryExclusionReason")
        self._exclusion_reason.setPlaceholderText(
            "例: 放電由来の異常波形、ノイズ混入、測定条件外"
        )
        self._exclusion_reason.returnPressed.connect(self._request_exclusion)

        self._exclude = QPushButton("集計から除外")
        self._exclude.setObjectName("excludeSummarySweep")
        self._exclude.setEnabled(False)
        self._exclude.clicked.connect(self._request_exclusion)

        self._restore = QPushButton("除外を解除")
        self._restore.setObjectName("restoreSummarySweep")
        self._restore.setEnabled(False)
        self._restore.clicked.connect(self._request_restore)

        self._exclusion_feedback = QLabel()
        self._exclusion_feedback.setObjectName("summaryExclusionFeedback")
        self._exclusion_feedback.setWordWrap(True)

        exclusion_actions = QHBoxLayout()
        exclusion_actions.addWidget(self._exclude)
        exclusion_actions.addWidget(self._restore)
        exclusion_actions.addStretch(1)

        detail_group = QGroupBox("選択Sweepの4方式")
        detail_layout = QVBoxLayout(detail_group)
        detail_layout.addWidget(self._selected)
        detail_layout.addWidget(self._methods, 1)
        detail_layout.addWidget(QLabel("集計から除外する理由"))
        detail_layout.addWidget(self._exclusion_reason)
        detail_layout.addLayout(exclusion_actions)
        detail_layout.addWidget(self._exclusion_feedback)
        detail_layout.addWidget(self._open_analysis)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.setObjectName("summaryWorkspaceBody")
        body.setChildrenCollapsible(False)
        body.addWidget(self._tree)
        body.addWidget(detail_group)
        body.setStretchFactor(0, 3)
        body.setStretchFactor(1, 2)
        body.setSizes([700, 430])

        self._views = QTabWidget()
        self._views.setObjectName("summaryViews")
        self._views.addTab(trend_page, "推移・平均")
        self._views.addTab(body, "Sweep一覧・詳細")

        self._policy = QLabel(
            "表示だけでは解析を再計算しません。既定集計には現在のRevisionと一致し、"
            "有効または要確認の結果だけを使います。T_i平均は0 < T_i < 5 eVに限定します。"
            "未実行・失敗・古い結果・除外も一覧から消さず、分母と理由を表示します。"
        )
        self._policy.setObjectName("summaryPolicy")
        self._policy.setWordWrap(True)
        self._policy.setStyleSheet(
            "background: #f8fafc; color: #475467; padding: 6px 8px;"
            " border-top: 1px solid #d0d5dd;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(status_bar)
        layout.addWidget(self._views, 1)
        layout.addWidget(self._policy)

        self.render_snapshot(None)

    @property
    def row_count(self) -> int:
        return self._tree.topLevelItemCount()

    @property
    def selected_sweep_id(self) -> str | None:
        item: QTreeWidgetItem | None = self._tree.currentItem()
        if item is None:
            return None
        value = item.data(0, SUMMARY_SWEEP_ID_ROLE)
        return value if isinstance(value, str) else None

    @property
    def context_text(self) -> str:
        return self._context.text()

    @property
    def denominator_text(self) -> str:
        return self._denominator.text()

    @property
    def policy_text(self) -> str:
        return self._policy.text()

    @property
    def exclusion_feedback_text(self) -> str:
        return self._exclusion_feedback.text()

    @property
    def average_row_count(self) -> int:
        return self._averages.topLevelItemCount()

    @property
    def ti_plot_point_count(self) -> int:
        return self._ti_plot.plotted_point_count

    @property
    def phi_plot_point_count(self) -> int:
        return self._phi_plot.plotted_point_count

    def status_text(self, status: AnalysisStatus) -> str:
        return self._status_labels[status].text()

    def show_exclusion_error(self, message: str) -> None:
        self._exclusion_feedback.setText(message)
        self._exclusion_feedback.setStyleSheet("color: #b42318;")

    def render_snapshot(
        self,
        snapshot: SummarySnapshot | None,
        *,
        selected_sweep_id: str | None = None,
        empty_message: str = "Sweep分割後に解析結果を集計します",
    ) -> None:
        self._snapshot = snapshot
        self._rows = {}
        self._tree.blockSignals(True)
        self._tree.clear()
        try:
            if snapshot is None:
                self._context.setText(f"集計範囲: shot未選択 ｜ {empty_message}")
                self._denominator.setText("既定集計: 0 / 0 Sweep")
                self._render_status_counts(())
                self._render_trends(None)
                self._render_detail(None)
                return

            scope = snapshot.scope
            scope_label = "、".join(scope.shot_ids)
            revision_policy = (
                "現在のRevisionのみ"
                if scope.current_revision_only
                else "全Revision"
            )
            self._context.setText(
                f"集計範囲: shot {scope_label} ｜ {revision_policy} ｜ "
                f"{len(snapshot.rows):,} Sweep"
            )
            self._denominator.setText(
                f"既定集計: {snapshot.aggregate_row_count:,} / "
                f"{len(snapshot.rows):,} Sweep"
                "（current revision・有効/要確認）"
            )
            self._render_status_counts(snapshot.status_counts)
            self._render_trends(
                snapshot,
                selected_sweep_id=selected_sweep_id,
            )
            for row in snapshot.rows:
                self._rows[row.sweep_id] = row
                item = self._row_item(row)
                self._tree.addTopLevelItem(item)

            target = selected_sweep_id
            if target is None and snapshot.rows:
                target = snapshot.rows[0].sweep_id
            if target is not None:
                self._select_item(target)
            self._render_detail(self._rows.get(target) if target is not None else None)
        finally:
            self._tree.blockSignals(False)

    def select_sweep(self, sweep_id: str) -> bool:
        self._tree.blockSignals(True)
        try:
            selected = self._select_item(sweep_id)
        finally:
            self._tree.blockSignals(False)
        if selected:
            self._render_detail(self._rows[sweep_id])
            self._select_trend_sweep(sweep_id)
        return selected

    def _select_item(self, sweep_id: str) -> bool:
        for index in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(index)
            if item is not None and item.data(0, SUMMARY_SWEEP_ID_ROLE) == sweep_id:
                self._tree.setCurrentItem(item)
                self._tree.scrollToItem(item)
                return True
        return False

    def _row_item(self, row: SummaryRow) -> QTreeWidgetItem:
        status_label, color, _ = _STATUS_PRESENTATION[row.status]
        item = QTreeWidgetItem(
            [
                str(row.number),
                row.sweep_id,
                "↑ 上昇" if row.direction is SweepDirection.UP else "↓ 下降",
                _format_value(row.start_ms),
                _format_value(row.stop_ms),
                status_label,
                f"{row.ti_value_count} / {len(SUMMARY_METHOD_ORDER)}",
                f"{row.phi_value_count} / {len(SUMMARY_METHOD_ORDER)}",
                f"{row.revision_key[:10]}…" if row.revision_key else "—",
                row.exclusion_reason or row.message or "—",
            ]
        )
        item.setData(0, SUMMARY_SWEEP_ID_ROLE, row.sweep_id)
        item.setForeground(5, QBrush(QColor(color)))
        item.setToolTip(
            1,
            f"{row.sweep_id}\n{row.point_count:,} 点\n"
            f"current revision: {'yes' if row.current_revision else 'no'}",
        )
        return item

    def _render_status_counts(
        self,
        counts: tuple[tuple[AnalysisStatus, int], ...],
    ) -> None:
        count_map = dict(counts)
        for status, label in self._status_labels.items():
            title, color, background = _STATUS_PRESENTATION[status]
            label.setText(f"{title}\n{count_map.get(status, 0):,}")
            label.setStyleSheet(
                f"background: {background}; color: {color}; padding: 5px;"
                " border: 1px solid #d0d5dd; border-radius: 4px;"
                " font-weight: 600;"
            )

    def _selection_changed(self) -> None:
        sweep_id = self.selected_sweep_id
        row = self._rows.get(sweep_id) if sweep_id is not None else None
        self._render_detail(row)
        self._select_trend_sweep(sweep_id)
        if sweep_id is not None:
            self.sweep_selected.emit(sweep_id)

    def _plot_sweep_selected(self, sweep_id: str) -> None:
        if self.select_sweep(sweep_id):
            self.sweep_selected.emit(sweep_id)

    def _select_trend_sweep(self, sweep_id: str | None) -> None:
        self._ti_plot.select_sweep(sweep_id)
        self._phi_plot.select_sweep(sweep_id)

    def _render_trends(
        self,
        snapshot: SummarySnapshot | None,
        *,
        selected_sweep_id: str | None = None,
    ) -> None:
        self._averages.clear()
        self._ti_plot.render_snapshot(
            snapshot,
            selected_sweep_id=selected_sweep_id,
        )
        self._phi_plot.render_snapshot(
            snapshot,
            selected_sweep_id=selected_sweep_id,
        )
        if snapshot is None:
            return
        ti_stats = {
            statistic.method: statistic
            for statistic in snapshot.metric_statistics(SummaryMetric.TI)
        }
        phi_stats = {
            statistic.method: statistic
            for statistic in snapshot.metric_statistics(SummaryMetric.PHI)
        }
        for method in SUMMARY_METHOD_ORDER:
            ti = ti_stats[method]
            phi = phi_stats[method]
            self._averages.addTopLevelItem(
                QTreeWidgetItem(
                    [
                        _METHOD_LABELS[method],
                        _format_optional(ti.mean),
                        _format_optional(ti.sample_std),
                        f"{ti.count} / {ti.scope_count}",
                        _format_optional(phi.mean),
                        _format_optional(phi.sample_std),
                        f"{phi.count} / {phi.scope_count}",
                    ]
                )
            )

    def _render_detail(self, row: SummaryRow | None) -> None:
        self._methods.clear()
        if row is None:
            self._selected.setText("Sweepを選択すると4方式の状態を確認できます")
            self._open_analysis.setEnabled(False)
            self._exclusion_reason.clear()
            self._exclusion_reason.setEnabled(False)
            self._exclude.setEnabled(False)
            self._restore.setEnabled(False)
            self._exclusion_feedback.clear()
            return
        status_label, _, _ = _STATUS_PRESENTATION[row.status]
        aggregate_target = (
            row.current_revision
            and row.status in (AnalysisStatus.VALID, AnalysisStatus.REVIEW)
        )
        self._selected.setText(
            f"{row.sweep_id}\n状態: {status_label} ｜ "
            f"既定集計: {'対象' if aggregate_target else '対象外'}"
        )
        has_current_result = row.current_revision and bool(row.revision_key)
        is_excluded = row.status is AnalysisStatus.EXCLUDED
        self._exclusion_reason.setEnabled(has_current_result and not is_excluded)
        self._exclusion_reason.setText(
            row.exclusion_reason if is_excluded else ""
        )
        self._exclude.setEnabled(has_current_result and not is_excluded)
        self._restore.setEnabled(has_current_result and is_excluded)
        if is_excluded:
            self._exclusion_feedback.setText(
                f"除外理由: {row.exclusion_reason}"
            )
            self._exclusion_feedback.setStyleSheet("color: #475467;")
        elif has_current_result:
            self._exclusion_feedback.setText(
                "除外・復元は集計表示だけを更新し、解析は再実行しません。"
            )
            self._exclusion_feedback.setStyleSheet("color: #475467;")
        else:
            self._exclusion_feedback.setText(
                "現在のRevisionの解析結果がないため、除外操作はできません。"
            )
            self._exclusion_feedback.setStyleSheet("color: #b54708;")
        method_map = {method.method: method for method in row.methods}
        for method_id in SUMMARY_METHOD_ORDER:
            method = method_map.get(method_id)
            status = method.status if method is not None else AnalysisStatus.NOT_RUN
            status_text, color, _ = _STATUS_PRESENTATION[status]
            item = QTreeWidgetItem(
                [
                    _METHOD_LABELS[method_id],
                    status_text,
                    _format_optional(method.phi_v if method is not None else None),
                    _format_optional(method.ti_ev if method is not None else None),
                    _format_optional(method.k_per_v if method is not None else None),
                    (method.k_source if method is not None and method.k_source else "—"),
                ]
            )
            item.setForeground(1, QBrush(QColor(color)))
            if method is not None:
                item.setToolTip(1, method.message)
            self._methods.addTopLevelItem(item)
        self._open_analysis.setEnabled(True)

    def _request_analysis(self) -> None:
        sweep_id = self.selected_sweep_id
        if sweep_id is not None:
            self.open_analysis_requested.emit(sweep_id)

    def _request_exclusion(self) -> None:
        sweep_id = self.selected_sweep_id
        if sweep_id is None or not self._exclude.isEnabled():
            return
        reason = self._exclusion_reason.text().strip()
        if not reason:
            self._exclusion_feedback.setText(
                "除外理由を入力してください。理由なしでは集計から外しません。"
            )
            self._exclusion_feedback.setStyleSheet("color: #b54708;")
            self._exclusion_reason.setFocus()
            return
        self._exclusion_feedback.clear()
        self.exclusion_requested.emit(sweep_id, reason)

    def _request_restore(self) -> None:
        sweep_id = self.selected_sweep_id
        if sweep_id is not None and self._restore.isEnabled():
            self.restore_requested.emit(sweep_id)


def _format_optional(value: float | None) -> str:
    return "—" if value is None else _format_value(value)


def _format_value(value: float) -> str:
    return f"{value:.8g}"
