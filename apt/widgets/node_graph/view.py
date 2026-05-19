"""QGraphicsView with mouse-wheel zoom, middle-button pan and dotted grid."""

from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QGraphicsView

GRID_SIZE = 22
GRID_COLOR_MINOR = QColor(255, 255, 255, 12)
GRID_COLOR_MAJOR = QColor(255, 255, 255, 26)


class NodeView(QGraphicsView):
    MIN_SCALE = 0.25
    MAX_SCALE = 2.5

    def __init__(self, scene, parent=None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#0B0B0E"))
        self._panning = False
        self._pan_anchor = None

    # Draw a dotted grid behind every paint so the canvas feels like a real
    # workspace instead of an empty void.
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        super().drawBackground(painter, rect)
        left = int(rect.left()) - (int(rect.left()) % GRID_SIZE)
        top = int(rect.top()) - (int(rect.top()) % GRID_SIZE)

        # Minor lines (every GRID_SIZE), major every 5x.
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)

        minor_pen = QPen(GRID_COLOR_MINOR, 1)
        major_pen = QPen(GRID_COLOR_MAJOR, 1)

        x = left
        while x < rect.right():
            painter.setPen(major_pen if (x // GRID_SIZE) % 5 == 0 else minor_pen)
            painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
            x += GRID_SIZE
        y = top
        while y < rect.bottom():
            painter.setPen(major_pen if (y // GRID_SIZE) % 5 == 0 else minor_pen)
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
            y += GRID_SIZE
        painter.restore()

    def fit_to_content(self) -> None:
        """Center the view on the bounding rect of all items, with margin."""
        items_rect = self.scene().itemsBoundingRect()
        if items_rect.isEmpty():
            return
        margin = 80
        rect = items_rect.adjusted(-margin, -margin, margin, margin)
        self.fitInView(rect, Qt.KeepAspectRatio)
        # Clamp scale within bounds after fit-in-view.
        scale = self.transform().m11()
        if scale > self.MAX_SCALE:
            factor = self.MAX_SCALE / scale
            self.scale(factor, factor)

    def wheelEvent(self, event) -> None:  # noqa: N802
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        new_scale = self.transform().m11() * factor
        if new_scale < self.MIN_SCALE or new_scale > self.MAX_SCALE:
            return
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_anchor = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._panning and self._pan_anchor is not None:
            delta = event.pos() - self._pan_anchor
            self._pan_anchor = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self._pan_anchor = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
