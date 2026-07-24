from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from probe_app.domain.models.raw_series import RawSeriesDescriptor
from probe_app.domain.models.series_role import (
    AssignedSeries,
    SeriesRole,
    SeriesRoleAssignments,
    SignalTransform,
    legacy_current_transform,
    legacy_sweep_voltage_transform,
)


class RoleAssignmentPanel(QWidget):
    """Always-visible editor for physical roles and device conversions."""

    assignments_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._updating = False
        self._shot_id: str | None = None

        self._shot_label = QLabel("shot未選択")
        self._current_series = QComboBox()
        self._voltage_series = QComboBox()
        self._current_scale = self._scale_spinbox(1.0 / 20.0)
        self._voltage_scale = self._scale_spinbox(100.0)
        self._current_sign = self._sign_combo(-1.0)
        self._voltage_sign = self._sign_combo(1.0)
        self._summary = QLabel("役割を選択してください")
        self._summary.setWordWrap(True)
        self._persistence_status = QLabel("設定はまだ保存されていません")
        self._persistence_status.setWordWrap(True)

        form = QFormLayout()
        form.addRow("対象shot", self._shot_label)
        form.addRow("current系列", self._current_series)
        form.addRow("current倍率", self._current_scale)
        form.addRow("current符号", self._current_sign)
        form.addRow("sweep voltage系列", self._voltage_series)
        form.addRow("voltage倍率", self._voltage_scale)
        form.addRow("voltage符号", self._voltage_sign)

        group = QGroupBox("解析系列の役割")
        group_layout = QVBoxLayout(group)
        group_layout.addLayout(form)
        group_layout.addWidget(self._summary)
        group_layout.addWidget(self._persistence_status)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 8)
        layout.addWidget(group)

        self._current_series.currentIndexChanged.connect(
            lambda: self._series_changed(SeriesRole.CURRENT)
        )
        self._voltage_series.currentIndexChanged.connect(
            lambda: self._series_changed(SeriesRole.SWEEP_VOLTAGE)
        )
        for control in (
            self._current_scale,
            self._voltage_scale,
            self._current_sign,
            self._voltage_sign,
        ):
            if isinstance(control, QDoubleSpinBox):
                control.valueChanged.connect(self._settings_changed)
            else:
                control.currentIndexChanged.connect(self._settings_changed)
        self.clear_context()

    @staticmethod
    def _scale_spinbox(value: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setDecimals(8)
        control.setRange(0.00000001, 1_000_000_000.0)
        control.setValue(value)
        control.setToolTip("headerで校正したRaw値へ追加で掛ける倍率")
        return control

    @staticmethod
    def _sign_combo(value: float) -> QComboBox:
        control = QComboBox()
        control.addItem("+1", 1.0)
        control.addItem("-1", -1.0)
        control.setCurrentIndex(control.findData(value))
        return control

    def clear_context(self) -> None:
        self._updating = True
        try:
            self._shot_id = None
            self._shot_label.setText("shot未選択")
            self._replace_series_items(self._current_series, ())
            self._replace_series_items(self._voltage_series, ())
            self._summary.setText("Raw系列を選択すると役割を設定できます")
            self._persistence_status.setStyleSheet("color: #556070;")
            self._persistence_status.setText("設定はまだ保存されていません")
            self._set_controls_enabled(False)
        finally:
            self._updating = False

    def set_context(
        self,
        shot_id: str,
        descriptors: Sequence[RawSeriesDescriptor],
        assignments: SeriesRoleAssignments,
    ) -> None:
        self._updating = True
        try:
            self._shot_id = shot_id
            self._shot_label.setText(shot_id)
            self._replace_series_items(self._current_series, descriptors)
            self._replace_series_items(self._voltage_series, descriptors)
            self._apply_assignment(SeriesRole.CURRENT, assignments)
            self._apply_assignment(SeriesRole.SWEEP_VOLTAGE, assignments)
            self._set_controls_enabled(True)
            self._render_summary(assignments)
        finally:
            self._updating = False

    def set_persistence_status(self, message: str, *, error: bool = False) -> None:
        color = "#b42318" if error else "#556070"
        self._persistence_status.setStyleSheet(f"color: {color};")
        self._persistence_status.setText(message)

    @property
    def shot_id(self) -> str | None:
        return self._shot_id

    def series_id_for_role(self, role: SeriesRole) -> str | None:
        combo = self._combo_for_role(role)
        data = combo.currentData()
        return None if data is None else str(data)

    def select_series(self, role: SeriesRole, series_id: str | None) -> None:
        combo = self._combo_for_role(role)
        index = combo.findData(series_id)
        if index < 0:
            raise ValueError(f"series is not available for {role.value}: {series_id}")
        combo.setCurrentIndex(index)

    def assignments(self) -> SeriesRoleAssignments:
        items: list[AssignedSeries] = []
        current_id = self.series_id_for_role(SeriesRole.CURRENT)
        if current_id is not None:
            items.append(
                AssignedSeries(
                    role=SeriesRole.CURRENT,
                    series_id=current_id,
                    transform=SignalTransform(
                        scale=self._current_scale.value(),
                        sign=float(self._current_sign.currentData()),
                        output_unit="A",
                    ),
                )
            )
        voltage_id = self.series_id_for_role(SeriesRole.SWEEP_VOLTAGE)
        if voltage_id is not None:
            items.append(
                AssignedSeries(
                    role=SeriesRole.SWEEP_VOLTAGE,
                    series_id=voltage_id,
                    transform=SignalTransform(
                        scale=self._voltage_scale.value(),
                        sign=float(self._voltage_sign.currentData()),
                        output_unit="V",
                    ),
                )
            )
        return SeriesRoleAssignments(tuple(items))

    def _replace_series_items(
        self,
        combo: QComboBox,
        descriptors: Sequence[RawSeriesDescriptor],
    ) -> None:
        combo.clear()
        combo.addItem("未割当", None)
        for descriptor in descriptors:
            combo.addItem(descriptor.display_name, descriptor.series_id)
            index = combo.count() - 1
            combo.setItemData(index, descriptor.series_id, Qt.ItemDataRole.ToolTipRole)

    def _apply_assignment(
        self,
        role: SeriesRole,
        assignments: SeriesRoleAssignments,
    ) -> None:
        combo = self._combo_for_role(role)
        assignment = assignments.for_role(role)
        if assignment is None:
            combo.setCurrentIndex(0)
            transform = (
                legacy_current_transform(sign=-1.0)
                if role is SeriesRole.CURRENT
                else legacy_sweep_voltage_transform()
            )
        else:
            index = combo.findData(assignment.series_id)
            combo.setCurrentIndex(index if index >= 0 else 0)
            transform = assignment.transform
        scale, sign = self._transform_controls(role)
        scale.setValue(transform.scale)
        sign.setCurrentIndex(sign.findData(transform.sign))

    def _series_changed(self, changed_role: SeriesRole) -> None:
        if self._updating:
            return
        changed_id = self.series_id_for_role(changed_role)
        other_role = (
            SeriesRole.SWEEP_VOLTAGE
            if changed_role is SeriesRole.CURRENT
            else SeriesRole.CURRENT
        )
        if changed_id is not None and changed_id == self.series_id_for_role(other_role):
            self._updating = True
            try:
                self._combo_for_role(other_role).setCurrentIndex(0)
            finally:
                self._updating = False
        self._emit_assignments()

    def _settings_changed(self) -> None:
        if not self._updating:
            self._emit_assignments()

    def _emit_assignments(self) -> None:
        assignments = self.assignments()
        self._render_summary(assignments)
        self._persistence_status.setText("設定を保存しています…")
        self.assignments_changed.emit(assignments)

    def _render_summary(self, assignments: SeriesRoleAssignments) -> None:
        current = assignments.for_role(SeriesRole.CURRENT)
        voltage = assignments.for_role(SeriesRole.SWEEP_VOLTAGE)
        current_text = current.series_id if current is not None else "未割当"
        voltage_text = voltage.series_id if voltage is not None else "未割当"
        ready = "解析準備OK" if assignments.is_complete else "2つの役割を選択してください"
        self._summary.setText(
            f"current: {current_text}\n"
            f"sweep voltage: {voltage_text}\n"
            f"{ready}"
        )

    def _set_controls_enabled(self, enabled: bool) -> None:
        for control in (
            self._current_series,
            self._voltage_series,
            self._current_scale,
            self._voltage_scale,
            self._current_sign,
            self._voltage_sign,
        ):
            control.setEnabled(enabled)

    def _combo_for_role(self, role: SeriesRole) -> QComboBox:
        return self._current_series if role is SeriesRole.CURRENT else self._voltage_series

    def _transform_controls(
        self,
        role: SeriesRole,
    ) -> tuple[QDoubleSpinBox, QComboBox]:
        if role is SeriesRole.CURRENT:
            return self._current_scale, self._current_sign
        return self._voltage_scale, self._voltage_sign
