"""Dynamic form widget driven by a list of :class:`ParamSpec`.

Emits ``valueChanged(name, value)`` whenever the user tweaks a control. The
host (e.g. the Preprocessing panel) wires this signal into the pipeline's
``set_param``.
"""

from __future__ import annotations

from typing import Any

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from apt.preprocessing.operations import ParamSpec


class ParameterForm(QWidget):
    valueChanged = pyqtSignal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._title = QLabel("(no node selected)")
        self._title.setStyleSheet("font-weight: 700; color: #FF7029;")
        self._layout.addWidget(self._title)
        self._form_host = QWidget()
        self._form_layout = QFormLayout(self._form_host)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._form_layout.setSpacing(6)
        self._layout.addWidget(self._form_host)
        self._layout.addStretch(1)

    def show_params(self, title: str, params: tuple[ParamSpec, ...], values: dict[str, Any]) -> None:
        """Render ``params`` with current ``values``. Clears previous fields."""
        self._title.setText(title)
        # Clear existing rows.
        while self._form_layout.rowCount():
            self._form_layout.removeRow(0)
        if not params:
            placeholder = QLabel("This operation has no parameters.")
            placeholder.setStyleSheet("color: #9A9CA3; font-size: 11px;")
            self._form_layout.addRow(placeholder)
            return
        for spec in params:
            widget = self._build_widget(spec, values.get(spec.name, spec.default))
            label = QLabel(spec.label)
            if spec.hint:
                label.setToolTip(spec.hint)
            self._form_layout.addRow(label, widget)

    def clear(self) -> None:
        self._title.setText("(no node selected)")
        while self._form_layout.rowCount():
            self._form_layout.removeRow(0)

    # ------------------------------------------------------------------
    def _build_widget(self, spec: ParamSpec, value: Any) -> QWidget:
        if spec.kind == "int":
            spin = QSpinBox()
            spin.setRange(int(spec.min if spec.min is not None else -2**31),
                          int(spec.max if spec.max is not None else 2**31 - 1))
            spin.setSingleStep(int(spec.step or 1))
            spin.setValue(int(value))
            spin.valueChanged.connect(lambda v, n=spec.name: self.valueChanged.emit(n, int(v)))
            return spin
        if spec.kind == "float":
            spin = QDoubleSpinBox()
            spin.setRange(float(spec.min if spec.min is not None else -1e9),
                          float(spec.max if spec.max is not None else 1e9))
            spin.setSingleStep(float(spec.step or 0.1))
            spin.setDecimals(3 if (spec.step and spec.step < 0.1) else 2)
            spin.setValue(float(value))
            spin.valueChanged.connect(lambda v, n=spec.name: self.valueChanged.emit(n, float(v)))
            return spin
        if spec.kind == "bool":
            box = QCheckBox()
            box.setChecked(bool(value))
            box.stateChanged.connect(
                lambda state, n=spec.name: self.valueChanged.emit(n, bool(state))
            )
            return box
        if spec.kind == "choice":
            combo = QComboBox()
            for choice in spec.choices or ():
                combo.addItem(choice)
            if value in (spec.choices or ()):
                combo.setCurrentText(str(value))
            combo.currentTextChanged.connect(
                lambda v, n=spec.name: self.valueChanged.emit(n, str(v))
            )
            return combo
        return QLabel(f"(unsupported kind: {spec.kind})")
