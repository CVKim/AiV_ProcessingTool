"""Graphics item for a single node in the preprocessing graph.

A :class:`NodeItem` is a rounded rectangle with:
    * a title bar (operation label)
    * 0–2 input ports on the left
    * 1 output port on the right (origin and 1-input ops both have one)

The node carries its pipeline ``node_id`` so the scene can map graphics
clicks back to the data model.
"""

from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
)


NODE_WIDTH = 160
NODE_HEIGHT = 64
PORT_RADIUS = 7

COLOR_NODE_FILL = QColor("#1D1F26")
COLOR_NODE_FILL_SELECTED = QColor("#2A2D35")
COLOR_NODE_TITLE = QColor("#FF7029")
COLOR_NODE_TITLE_ORIGIN = QColor("#33B66B")
COLOR_NODE_TEXT = QColor("#EDEDEF")
COLOR_NODE_BORDER = QColor("#3A3D45")
COLOR_NODE_BORDER_SELECTED = QColor("#FF7029")
COLOR_PORT_IN = QColor("#5BA9F5")
COLOR_PORT_OUT = QColor("#33B66B")
COLOR_PORT_HOVER = QColor("#FFFFFF")


class PortItem(QGraphicsEllipseItem):
    """Connection port — either input (left) or output (right) of a node."""

    def __init__(self, parent: "NodeItem", kind: str, index: int) -> None:
        super().__init__(-PORT_RADIUS, -PORT_RADIUS, PORT_RADIUS * 2, PORT_RADIUS * 2, parent)
        self.kind = kind          # "in" | "out"
        self.index = index
        self.node = parent
        self.setBrush(QBrush(COLOR_PORT_IN if kind == "in" else COLOR_PORT_OUT))
        self.setPen(QPen(QColor("#0B0B0E"), 1))
        self.setAcceptHoverEvents(True)
        self.setZValue(2)

    def scene_pos(self) -> QPointF:
        return self.mapToScene(QPointF(0, 0))

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        self.setBrush(QBrush(COLOR_PORT_HOVER))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        self.setBrush(QBrush(COLOR_PORT_IN if self.kind == "in" else COLOR_PORT_OUT))
        super().hoverLeaveEvent(event)


class NodeItem(QGraphicsRectItem):
    """Rounded-rectangle node with a title bar and ports."""

    def __init__(self, node_id: str, title: str, num_inputs: int, is_origin: bool = False) -> None:
        super().__init__(0, 0, NODE_WIDTH, NODE_HEIGHT)
        self.node_id = node_id
        self.is_origin = is_origin
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(1)

        self.setBrush(QBrush(COLOR_NODE_FILL))
        self.setPen(QPen(COLOR_NODE_BORDER, 1.4))

        # Title bar (top stripe)
        self._title_band = QGraphicsRectItem(0, 0, NODE_WIDTH, 22, self)
        self._title_band.setBrush(
            QBrush(COLOR_NODE_TITLE_ORIGIN if is_origin else COLOR_NODE_TITLE)
        )
        self._title_band.setPen(QPen(Qt.NoPen))

        # Title text
        self._title = QGraphicsSimpleTextItem(title, self)
        f = QFont()
        f.setBold(True)
        f.setPointSize(9)
        self._title.setFont(f)
        self._title.setBrush(QBrush(QColor("#0B0B0E")))
        self._title.setPos(8, 4)

        # Subtitle (node id, dim)
        self._subtitle = QGraphicsSimpleTextItem(node_id, self)
        sf = QFont()
        sf.setPointSize(8)
        self._subtitle.setFont(sf)
        self._subtitle.setBrush(QBrush(QColor("#9A9CA3")))
        self._subtitle.setPos(8, 32)

        # Ports
        self.inputs: list[PortItem] = []
        for i in range(num_inputs):
            port = PortItem(self, "in", i)
            self.inputs.append(port)
            self._place_port(port, i, num_inputs, side="left")

        # Origin has only an output; all op nodes also have one output.
        self.output: PortItem = PortItem(self, "out", 0)
        self._place_port(self.output, 0, 1, side="right")

        # Listeners notified when the node moves (for edges to redraw).
        self._move_listeners: list = []

    def add_move_listener(self, callback) -> None:
        self._move_listeners.append(callback)

    def remove_move_listener(self, callback) -> None:
        if callback in self._move_listeners:
            self._move_listeners.remove(callback)

    def _place_port(self, port: PortItem, index: int, total: int, side: str) -> None:
        x = 0 if side == "left" else NODE_WIDTH
        # Distribute vertically below the title band.
        bottom = NODE_HEIGHT
        top = 28
        if total == 1:
            y = (top + bottom) / 2
        else:
            step = (bottom - top) / (total + 1)
            y = top + (index + 1) * step
        port.setPos(x, y)

    def itemChange(self, change, value):  # noqa: N802
        if change == QGraphicsItem.ItemPositionHasChanged:
            for cb in list(self._move_listeners):
                cb()
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None):
        # Rounded body
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 8, 8)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillPath(path, COLOR_NODE_FILL_SELECTED if self.isSelected() else COLOR_NODE_FILL)
        painter.setPen(
            QPen(COLOR_NODE_BORDER_SELECTED if self.isSelected() else COLOR_NODE_BORDER, 1.6)
        )
        painter.drawPath(path)
        painter.restore()

    def boundingRect(self) -> QRectF:  # noqa: N802
        # Expand a touch so ports drawn outside the rect aren't clipped.
        return self.rect().adjusted(-PORT_RADIUS, -2, PORT_RADIUS, 2)

    def update_title(self, title: str) -> None:
        self._title.setText(title)
