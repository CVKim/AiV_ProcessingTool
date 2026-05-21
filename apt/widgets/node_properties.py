"""Compact properties panel for the currently selected pipeline node.

Mirrors the per-node info pane in commercial vision tools (Cognex-style):
Name · Type · Status · Time · Inputs / Outputs / Output shape. The host
panel calls :meth:`NodePropertiesPanel.show_node` whenever the selection or
the pipeline state changes.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from apt.preprocessing import Node, Pipeline, format_time_ms, status_color
from apt.preprocessing.operations import get_operation


_STATUS_LABELS = {
    "idle":    "Idle",
    "success": "Success",
    "cached":  "Cached",
    "error":   "Error",
}


class NodePropertiesPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(4)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        outer.addLayout(form)

        mono = QFont("Consolas")
        mono.setPointSize(9)

        def _value() -> QLabel:
            lab = QLabel("—")
            lab.setFont(mono)
            lab.setStyleSheet("color: #EDEDEF; background: transparent;")
            lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
            return lab

        self._name = _value()
        self._type = _value()
        # Status row: pip + label
        status_row = QFrame()
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(6)
        self._status_pip = QLabel()
        self._status_pip.setFixedSize(10, 10)
        self._status_label = QLabel("—")
        self._status_label.setFont(mono)
        self._status_label.setStyleSheet("background: transparent;")
        status_layout.addWidget(self._status_pip)
        status_layout.addWidget(self._status_label)
        status_layout.addStretch(1)

        self._time = _value()
        self._io = _value()
        self._output_shape = _value()

        form.addRow(self._key("NAME"), self._name)
        form.addRow(self._key("TYPE"), self._type)
        form.addRow(self._key("STATUS"), status_row)
        form.addRow(self._key("TIME"), self._time)
        form.addRow(self._key("I / O"), self._io)
        form.addRow(self._key("SHAPE"), self._output_shape)

        # Error message (only visible when status == "error")
        self._error_label = QLabel("")
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet(
            "background: rgba(229, 72, 77, 0.12); color: #E5484D;"
            " border-left: 3px solid #E5484D; padding: 6px 8px;"
            " border-radius: 3px;"
        )
        self._error_label.hide()
        outer.addWidget(self._error_label)

        self._set_pip_color(status_color("idle"))

    # -- API ----------------------------------------------------------
    def clear(self) -> None:
        self._name.setText("—")
        self._type.setText("—")
        self._status_label.setText("—")
        self._status_label.setStyleSheet("background: transparent; color: #9A9CA3;")
        self._set_pip_color(status_color("idle"))
        self._time.setText("—")
        self._io.setText("—")
        self._output_shape.setText("—")
        self._error_label.hide()

    def show_node(
        self,
        node: Node,
        downstream_consumer_count: int,
    ) -> None:
        self._name.setText(node.id)
        if node.op_key == "origin":
            self._type.setText("Origin")
        else:
            try:
                op = get_operation(node.op_key)
                self._type.setText(f"{op.label}  ({op.category})")
            except KeyError:
                self._type.setText(node.op_key)

        status = node.last_status or "idle"
        color = status_color(status)
        self._status_label.setText(_STATUS_LABELS.get(status, status.capitalize()))
        self._status_label.setStyleSheet(
            f"background: transparent; color: {color}; font-weight: 700;"
        )
        self._set_pip_color(color)

        self._time.setText(format_time_ms(node.last_time_ms, status))

        wired_inputs = sum(1 for src in node.inputs if src)
        self._io.setText(
            f"{wired_inputs} in  /  {downstream_consumer_count} out"
        )

        if node.last_output_shape:
            shape = node.last_output_shape
            if len(shape) == 2:
                h, w = shape
                self._output_shape.setText(f"{w}×{h}  ·  1 ch")
            elif len(shape) == 3:
                h, w, c = shape
                self._output_shape.setText(f"{w}×{h}  ·  {c} ch")
            else:
                self._output_shape.setText(" × ".join(str(s) for s in shape))
        else:
            self._output_shape.setText("—")

        if status == "error" and node.last_error:
            self._error_label.setText(f"⚠ {node.last_error}")
            self._error_label.show()
        else:
            self._error_label.hide()

    # -- internals ----------------------------------------------------
    @staticmethod
    def _key(text: str) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet(
            "color: #9A9CA3; font-size: 10px; font-weight: 700;"
            " letter-spacing: 1px; background: transparent;"
        )
        return lab

    def _set_pip_color(self, color: str) -> None:
        self._status_pip.setStyleSheet(
            f"background-color: {color}; border-radius: 5px;"
        )

    @staticmethod
    def count_downstream(pipeline: Pipeline, node_id: str) -> int:
        return sum(
            1 for n in pipeline.nodes() if node_id in n.inputs
        )
