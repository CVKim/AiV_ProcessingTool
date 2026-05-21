"""Zoomable, pannable image viewer.

A ``QGraphicsView``-based replacement for :class:`ImagePreview` that adds
mouse-wheel zoom (anchored under the cursor), drag-to-pan, and a
double-click toggle between *fit-to-window* and *1:1 original size*. The
current zoom percentage is shown as a small overlay in the top-right
corner.

Drop-in replacement for ``ImagePreview``: same ``set_image(ndarray|None)``
API, same dark background / orange selection palette.
"""

from __future__ import annotations

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QLabel,
    QSizePolicy,
)

from apt.widgets.image_preview import _ndarray_to_pixmap


MIN_SCALE = 0.05
MAX_SCALE = 16.0
ZOOM_STEP = 1.15


class ZoomableImageView(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item = QGraphicsPixmapItem()
        self._pixmap_item.setTransformationMode(Qt.SmoothTransformation)
        self._scene.addItem(self._pixmap_item)

        # Placeholder text when no image is loaded.
        self._placeholder = QGraphicsSimpleTextItem("(no image)")
        self._placeholder.setBrush(QBrush(QColor("#9A9CA3")))
        self._scene.addItem(self._placeholder)

        self.setBackgroundBrush(QColor("#08080A"))
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(
            "QGraphicsView { background-color: #08080A; border: 1px solid #2A2D35;"
            " border-radius: 4px; }"
        )
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(160, 120)
        self.setMouseTracking(True)
        self.setToolTip(
            "Wheel = zoom\n"
            "Drag = pan\n"
            "Double-click = toggle fit / 1:1"
        )

        # Overlay zoom label (child of the viewport so it doesn't move with
        # the scene transform).
        self._zoom_label = QLabel(self.viewport())
        self._zoom_label.setStyleSheet(
            "QLabel { background-color: rgba(11, 11, 14, 0.75);"
            " color: #EDEDEF; padding: 2px 6px; border-radius: 3px;"
            " font-family: Consolas; font-size: 10px; font-weight: 700; }"
        )
        self._zoom_label.setText("—")
        self._zoom_label.adjustSize()
        self._zoom_label.move(8, 8)
        self._zoom_label.raise_()

        self._source_shape: tuple[int, ...] | None = None
        self._has_image = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_image(self, image: np.ndarray | None) -> None:
        if image is None:
            self._pixmap_item.setPixmap(QPixmap())
            self._placeholder.setText("(no image)")
            self._placeholder.setVisible(True)
            self._has_image = False
            self._source_shape = None
            self._update_zoom_label()
            return

        pixmap = _ndarray_to_pixmap(image)
        if pixmap.isNull():
            self._pixmap_item.setPixmap(QPixmap())
            self._placeholder.setText("(invalid image)")
            self._placeholder.setVisible(True)
            self._has_image = False
            self._source_shape = None
            self._update_zoom_label()
            return

        shape = tuple(image.shape)
        shape_changed = shape != self._source_shape
        self._source_shape = shape
        self._placeholder.setVisible(False)
        self._pixmap_item.setPixmap(pixmap)
        # Make the scene's bounding rect match the pixmap so fit / scroll
        # bars behave sanely even when the pixmap shrinks.
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self._has_image = True

        # Only refit when the image dimensions change. Tweaking a filter
        # parameter usually keeps the same WxH, so the user's zoom is kept.
        if shape_changed:
            self.zoom_to_fit()
        self._update_zoom_label()

    def zoom_to_fit(self) -> None:
        if not self._has_image:
            return
        rect = self._pixmap_item.boundingRect()
        if rect.isEmpty():
            return
        self.fitInView(rect, Qt.KeepAspectRatio)
        self._update_zoom_label()

    def zoom_to_100(self) -> None:
        if not self._has_image:
            return
        self.resetTransform()
        self.centerOn(self._pixmap_item.boundingRect().center())
        self._update_zoom_label()

    def current_zoom(self) -> float:
        return float(self.transform().m11())

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------
    def wheelEvent(self, event) -> None:  # noqa: N802
        if not self._has_image:
            return
        factor = ZOOM_STEP if event.angleDelta().y() > 0 else 1 / ZOOM_STEP
        new_scale = self.current_zoom() * factor
        if new_scale < MIN_SCALE or new_scale > MAX_SCALE:
            event.ignore()
            return
        self.scale(factor, factor)
        self._update_zoom_label()
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if not self._has_image:
            return
        # Toggle: if we're already at (or very close to) 1:1, fit; otherwise
        # snap to 1:1 centred on the click position.
        if abs(self.current_zoom() - 1.0) < 0.01:
            self.zoom_to_fit()
        else:
            self.resetTransform()
            self.centerOn(self.mapToScene(event.pos()))
            self._update_zoom_label()
        event.accept()

    # ------------------------------------------------------------------
    # Resize handling — refit only if user was at fit zoom already, so
    # manual zoom levels survive window resizes.
    # ------------------------------------------------------------------
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # Keep the zoom overlay pinned to the top-right of the viewport.
        self._zoom_label.move(self.viewport().width() - self._zoom_label.width() - 8, 8)
        # Re-centre the placeholder when no image is loaded.
        if not self._has_image:
            r = self._scene.sceneRect()
            if r.isEmpty():
                self._scene.setSceneRect(0, 0, self.viewport().width(), self.viewport().height())
            self._placeholder.setPos(
                (self.viewport().width() - self._placeholder.boundingRect().width()) / 2,
                (self.viewport().height() - self._placeholder.boundingRect().height()) / 2,
            )

    # ------------------------------------------------------------------
    # Overlay refresh
    # ------------------------------------------------------------------
    def _update_zoom_label(self) -> None:
        if not self._has_image:
            self._zoom_label.setText("—")
        else:
            pct = self.current_zoom() * 100.0
            self._zoom_label.setText(f"{pct:.0f}%")
        self._zoom_label.adjustSize()
        self._zoom_label.move(self.viewport().width() - self._zoom_label.width() - 8, 8)
