"""Bezier connection between two ports."""

from __future__ import annotations

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsPathItem


COLOR_EDGE_DEFAULT = QColor("#5BA9F5")
COLOR_EDGE_TEMP = QColor("#FF7029")


class EdgeItem(QGraphicsPathItem):
    """Cubic bezier from ``src_port`` (output) to ``dst_port`` (input)."""

    def __init__(self, src_port, dst_port, temporary: bool = False) -> None:
        super().__init__()
        self.src_port = src_port
        self.dst_port = dst_port
        self.temporary = temporary
        # Tint the edge with the source node's accent color so the flow
        # visually matches the category.
        if temporary:
            edge_color = COLOR_EDGE_TEMP
        else:
            edge_color = getattr(src_port.node, "accent_color", COLOR_EDGE_DEFAULT)
        pen = QPen(edge_color, 2.5)
        pen.setCapStyle(0)  # FlatCap
        self.setPen(pen)
        self.setZValue(0)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self._free_end: QPointF | None = None
        if not temporary:
            self.src_port.node.add_move_listener(self.refresh)
            self.dst_port.node.add_move_listener(self.refresh)
        self.refresh()

    def set_free_end(self, scene_pos: QPointF) -> None:
        """Update the trailing end while the user is dragging a temp edge."""
        self._free_end = scene_pos
        self.refresh()

    def refresh(self) -> None:
        if self.src_port is None:
            return
        start = self.src_port.scene_pos()
        if self.dst_port is not None:
            end = self.dst_port.scene_pos()
        elif self._free_end is not None:
            end = self._free_end
        else:
            end = start
        path = QPainterPath(start)
        dx = max(40.0, abs(end.x() - start.x()) * 0.5)
        c1 = QPointF(start.x() + dx, start.y())
        c2 = QPointF(end.x() - dx, end.y())
        path.cubicTo(c1, c2, end)
        self.setPath(path)

    def detach(self) -> None:
        if not self.temporary and self.src_port is not None and self.dst_port is not None:
            self.src_port.node.remove_move_listener(self.refresh)
            self.dst_port.node.remove_move_listener(self.refresh)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        # Selection highlight
        if self.isSelected() and not self.temporary:
            pen = QPen(QColor("#FF7029"), 3)
        else:
            pen = self.pen()
        painter.setPen(pen)
        painter.drawPath(self.path())
