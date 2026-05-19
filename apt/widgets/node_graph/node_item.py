"""Graphics item for a single node in the preprocessing graph.

A :class:`NodeItem` is a rounded card with:
    * a category-coloured title bar (with op icon + label)
    * a parameter summary line (auto-updated)
    * input ports on the left, output port on the right

The node carries its pipeline ``node_id`` so the scene can map graphics
clicks back to the data model.
"""

from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt5.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
)

from apt.preprocessing import ORIGIN_STYLE, short_hint, style_for
from apt.preprocessing.operations import get_operation


NODE_WIDTH = 200
NODE_HEIGHT = 96
TITLE_HEIGHT = 30
PORT_RADIUS = 8

# Snap step (px) used when ``snap_enabled`` is true. Matches the dotted-grid
# spacing drawn by NodeView so visual lines line up with stop points.
SNAP_STEP = 22

COLOR_NODE_FILL = QColor("#13141A")
COLOR_NODE_FILL_HOVER = QColor("#181A22")
COLOR_NODE_BORDER = QColor("#2E3140")
COLOR_NODE_BORDER_SELECTED = QColor("#FF7029")
COLOR_NODE_TEXT = QColor("#EDEDEF")
COLOR_NODE_TEXT_DIM = QColor("#9A9CA3")
COLOR_PORT_HOVER = QColor("#FFFFFF")


class PortItem(QGraphicsEllipseItem):
    """Connection port — either input (left) or output (right) of a node."""

    def __init__(self, parent: "NodeItem", kind: str, index: int) -> None:
        super().__init__(-PORT_RADIUS, -PORT_RADIUS, PORT_RADIUS * 2, PORT_RADIUS * 2, parent)
        self.kind = kind          # "in" | "out"
        self.index = index
        self.node = parent
        self._base_color = parent.accent_color
        self.setBrush(QBrush(self._base_color))
        self.setPen(QPen(QColor("#0B0B0E"), 1.4))
        self.setAcceptHoverEvents(True)
        self.setZValue(2)

    def scene_pos(self) -> QPointF:
        return self.mapToScene(QPointF(0, 0))

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        self.setBrush(QBrush(COLOR_PORT_HOVER))
        self.setRect(-PORT_RADIUS - 1, -PORT_RADIUS - 1, (PORT_RADIUS + 1) * 2, (PORT_RADIUS + 1) * 2)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        self.setBrush(QBrush(self._base_color))
        self.setRect(-PORT_RADIUS, -PORT_RADIUS, PORT_RADIUS * 2, PORT_RADIUS * 2)
        super().hoverLeaveEvent(event)


class NodeItem(QGraphicsRectItem):
    """Rounded-rectangle node with title bar, params summary and ports."""

    # Snap toggle owned by the scene; flipped via NodeScene.set_snap_enabled.
    snap_enabled: bool = True

    def __init__(
        self,
        node_id: str,
        op_key: str,
        is_origin: bool = False,
    ) -> None:
        super().__init__(0, 0, NODE_WIDTH, NODE_HEIGHT)
        self.node_id = node_id
        self.op_key = op_key
        self.is_origin = is_origin

        if is_origin:
            style = ORIGIN_STYLE
            self.label = "Origin"
            num_inputs = 0
        else:
            op = get_operation(op_key)
            style = style_for(op.category)
            self.label = op.label
            num_inputs = op.inputs
        self.accent_color = QColor(style.color)
        self.icon = style.icon

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(1)

        # Drop shadow — gives nodes depth on the dark canvas.
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

        self.setBrush(QBrush(COLOR_NODE_FILL))
        self.setPen(QPen(COLOR_NODE_BORDER, 1.2))

        # Title bar background (drawn in paint to support gradient + accent strip).
        # Texts are children so they reposition with the node automatically.
        self._icon = QGraphicsSimpleTextItem(self.icon, self)
        icon_font = QFont()
        icon_font.setPointSize(14)
        icon_font.setBold(True)
        self._icon.setFont(icon_font)
        self._icon.setBrush(QBrush(QColor("#0B0B0E")))
        self._icon.setPos(10, 6)

        self._title = QGraphicsSimpleTextItem(self.label, self)
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        self._title.setFont(title_font)
        self._title.setBrush(QBrush(QColor("#0B0B0E")))
        self._title.setPos(34, 8)

        self._subtitle = QGraphicsSimpleTextItem(node_id, self)
        sub_font = QFont()
        sub_font.setPointSize(8)
        self._subtitle.setFont(sub_font)
        self._subtitle.setBrush(QBrush(COLOR_NODE_TEXT_DIM))
        self._subtitle.setPos(12, TITLE_HEIGHT + 8)

        self._params_text = QGraphicsSimpleTextItem("", self)
        params_font = QFont()
        params_font.setPointSize(8)
        params_font.setItalic(True)
        self._params_text.setFont(params_font)
        self._params_text.setBrush(QBrush(COLOR_NODE_TEXT))
        self._params_text.setPos(12, TITLE_HEIGHT + 26)

        # Ports
        self.inputs: list[PortItem] = []
        for i in range(num_inputs):
            port = PortItem(self, "in", i)
            self.inputs.append(port)
            self._place_port(port, i, num_inputs, side="left")

        self.output: PortItem = PortItem(self, "out", 0)
        self._place_port(self.output, 0, 1, side="right")

        # Move listeners notified when the node moves (for edges to redraw).
        self._move_listeners: list = []

    def add_move_listener(self, callback) -> None:
        self._move_listeners.append(callback)

    def remove_move_listener(self, callback) -> None:
        if callback in self._move_listeners:
            self._move_listeners.remove(callback)

    def set_params_summary(self, text: str) -> None:
        self._params_text.setText(text or "(defaults)" if not self.is_origin else "")

    def update_params(self, params: dict) -> None:
        self.set_params_summary(short_hint(self.op_key, params))

    def _place_port(self, port: PortItem, index: int, total: int, side: str) -> None:
        x = 0 if side == "left" else NODE_WIDTH
        bottom = NODE_HEIGHT
        top = TITLE_HEIGHT
        if total == 1:
            y = top + (bottom - top) / 2
        else:
            step = (bottom - top) / (total + 1)
            y = top + (index + 1) * step
        port.setPos(x, y)

    def itemChange(self, change, value):  # noqa: N802
        if change == QGraphicsItem.ItemPositionChange and self.snap_enabled:
            # Hold Shift while dragging to bypass the snap and place freely.
            mods = QGuiApplication.keyboardModifiers()
            if not (mods & Qt.ShiftModifier):
                x = round(value.x() / SNAP_STEP) * SNAP_STEP
                y = round(value.y() / SNAP_STEP) * SNAP_STEP
                return QPointF(x, y)
        if change == QGraphicsItem.ItemSelectedHasChanged and value:
            # Bring selected node above its peers so its ports / title
            # aren't hidden by overlapping nodes during drag operations.
            self.setZValue(3)
        elif change == QGraphicsItem.ItemSelectedHasChanged and not value:
            self.setZValue(1)
        if change == QGraphicsItem.ItemPositionHasChanged:
            for cb in list(self._move_listeners):
                cb()
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        # Body
        body_path = QPainterPath()
        body_path.addRoundedRect(rect, 10, 10)
        painter.fillPath(body_path, COLOR_NODE_FILL_HOVER if self.isSelected() else COLOR_NODE_FILL)

        # Title bar (clipped to top rounded corners only by drawing a rect+roundtop trick)
        title_rect = QRectF(rect.x(), rect.y(), rect.width(), TITLE_HEIGHT)
        title_path = QPainterPath()
        title_path.addRoundedRect(title_rect, 10, 10)
        # Mask the bottom corners so only the top is rounded.
        bottom_cover = QPainterPath()
        bottom_cover.addRect(rect.x(), rect.y() + TITLE_HEIGHT - 10, rect.width(), 10)
        title_path = title_path.united(bottom_cover).intersected(body_path)

        grad = QLinearGradient(0, 0, 0, TITLE_HEIGHT)
        grad.setColorAt(0.0, self.accent_color.lighter(110))
        grad.setColorAt(1.0, self.accent_color)
        painter.fillPath(title_path, QBrush(grad))

        # Accent stripe under the title
        stripe = QRectF(rect.x(), rect.y() + TITLE_HEIGHT, rect.width(), 2)
        painter.fillRect(stripe, QBrush(self.accent_color.darker(140)))

        # Border (selection ring)
        pen_color = COLOR_NODE_BORDER_SELECTED if self.isSelected() else COLOR_NODE_BORDER
        pen_width = 2.0 if self.isSelected() else 1.2
        painter.setPen(QPen(pen_color, pen_width))
        painter.drawPath(body_path)

    def boundingRect(self) -> QRectF:  # noqa: N802
        # Expand a touch so ports drawn outside the rect aren't clipped.
        return self.rect().adjusted(-PORT_RADIUS - 2, -2, PORT_RADIUS + 2, 4)

    def update_title(self, title: str) -> None:
        self.label = title
        self._title.setText(title)
