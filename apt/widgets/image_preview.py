"""QLabel-based image preview that auto-fits numpy arrays to the widget."""

from __future__ import annotations

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel, QSizePolicy, QWidget


class ImagePreview(QLabel):
    """Display a numpy uint8 image (grayscale or BGR) scaled to fit."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(160, 120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(
            "QLabel { background-color: #08080A; border: 1px solid #2A2D35; border-radius: 4px;"
            " color: #9A9CA3; }"
        )
        self.setText("(no image)")
        self._source: np.ndarray | None = None

    def set_image(self, image: np.ndarray | None) -> None:
        self._source = image
        if image is None:
            self.setText("(no image)")
            self.setPixmap(QPixmap())
            return
        pixmap = _ndarray_to_pixmap(image)
        if pixmap.isNull():
            self.setText("(invalid image)")
            return
        self.setText("")
        self._rescale(pixmap)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._source is not None:
            self._rescale(_ndarray_to_pixmap(self._source))

    def _rescale(self, pixmap: QPixmap) -> None:
        if pixmap.isNull() or self.width() < 2 or self.height() < 2:
            self.setPixmap(pixmap)
            return
        scaled = pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.setPixmap(scaled)


def _ndarray_to_pixmap(image: np.ndarray) -> QPixmap:
    """Convert a numpy uint8 image to a QPixmap (assumes BGR for 3-channel)."""
    if image is None or image.size == 0:
        return QPixmap()
    img = image
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    if img.ndim == 2:
        h, w = img.shape
        bytes_per_line = w
        # Copy to ensure contiguous memory before Qt holds the buffer.
        buf = np.ascontiguousarray(img)
        qimg = QImage(buf.data, w, h, bytes_per_line, QImage.Format_Grayscale8)
    elif img.ndim == 3 and img.shape[2] == 3:
        # OpenCV is BGR; QImage expects RGB for Format_RGB888.
        rgb = np.ascontiguousarray(img[:, :, ::-1])
        h, w, _ = rgb.shape
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
    elif img.ndim == 3 and img.shape[2] == 4:
        rgba = np.ascontiguousarray(img[:, :, [2, 1, 0, 3]])
        h, w, _ = rgba.shape
        qimg = QImage(rgba.data, w, h, 4 * w, QImage.Format_RGBA8888)
    else:
        return QPixmap()
    # Detach from the numpy buffer by copying — otherwise the pixmap dies when
    # ``buf`` is garbage-collected.
    return QPixmap.fromImage(qimg.copy())
