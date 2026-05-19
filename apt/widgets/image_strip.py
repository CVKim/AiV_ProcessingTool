"""Horizontal thumbnail strip of loaded images.

Each card shows a tiny preview + filename + a remove button. Clicking the
card selects it (active image used for parameter tuning). Emits:

    imageSelected(int)   - row index of the clicked card
    imageRemoved(int)    - row index whose × button was pressed
"""

from __future__ import annotations

import os

import numpy as np
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from apt.widgets.image_preview import _ndarray_to_pixmap


CARD_WIDTH = 140
CARD_HEIGHT = 116


class _ThumbCard(QFrame):
    clicked = pyqtSignal()
    removed = pyqtSignal()

    def __init__(self, image: np.ndarray, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setFrameShape(QFrame.NoFrame)
        self._active = False
        self._apply_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addStretch(1)
        self._close = QPushButton("×")
        self._close.setFixedSize(18, 18)
        self._close.setCursor(Qt.PointingHandCursor)
        self._close.setStyleSheet(
            "QPushButton { background-color: rgba(0,0,0,140); color: #EDEDEF; "
            "border: none; border-radius: 9px; font-weight: 700; }"
            "QPushButton:hover { background-color: #E5484D; color: #0B0B0E; }"
        )
        self._close.clicked.connect(self.removed.emit)
        header.addWidget(self._close)
        layout.addLayout(header)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setMinimumHeight(60)
        self._image_label.setStyleSheet("background: transparent;")
        layout.addWidget(self._image_label, 1)

        self._name_label = QLabel(name)
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setStyleSheet("color: #EDEDEF; font-size: 10px; background: transparent;")
        self._name_label.setToolTip(name)
        layout.addWidget(self._name_label)

        self._set_pixmap_from(image)

    def _set_pixmap_from(self, image: np.ndarray) -> None:
        pixmap = _ndarray_to_pixmap(image)
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(CARD_WIDTH - 8, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._image_label.setPixmap(scaled)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_style()

    def _apply_style(self) -> None:
        if self._active:
            self.setStyleSheet(
                "_ThumbCard { background-color: #1D1F26; border: 2px solid #FF7029; border-radius: 6px; }"
            )
        else:
            self.setStyleSheet(
                "_ThumbCard { background-color: #15161B; border: 1px solid #2A2D35; border-radius: 6px; }"
            )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ImageStrip(QWidget):
    imageSelected = pyqtSignal(int)
    imageRemoved = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: list[_ThumbCard] = []
        self._active_index: int = -1

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel("<b>Images</b>  <span style='color:#9A9CA3;'>(none loaded)</span>")
        self._title.setTextFormat(Qt.RichText)
        header.addWidget(self._title)
        header.addStretch(1)
        outer.addLayout(header)

        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QFrame.NoFrame)
        scroller.setFixedHeight(CARD_HEIGHT + 18)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroller.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._container = QWidget()
        self._row = QHBoxLayout(self._container)
        self._row.setContentsMargins(2, 2, 2, 2)
        self._row.setSpacing(8)
        self._row.addStretch(1)
        scroller.setWidget(self._container)
        outer.addWidget(scroller)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # -- API -----------------------------------------------------------
    def set_images(self, entries: list[tuple[np.ndarray, str]]) -> None:
        """Replace the whole strip with the given (preview, name) entries."""
        # Drop existing cards.
        for card in self._cards:
            self._row.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        # The trailing stretch is the last item; insert cards before it.
        for index, (preview, name) in enumerate(entries):
            card = _ThumbCard(preview, name)
            card.clicked.connect(lambda i=index: self.imageSelected.emit(i))
            card.removed.connect(lambda i=index: self.imageRemoved.emit(i))
            self._row.insertWidget(self._row.count() - 1, card)
            self._cards.append(card)
        self._refresh_title(len(entries))
        if entries:
            self.set_active(min(max(self._active_index, 0), len(entries) - 1))
        else:
            self._active_index = -1

    def set_active(self, index: int) -> None:
        self._active_index = index
        for i, card in enumerate(self._cards):
            card.set_active(i == index)

    # -- Internals -----------------------------------------------------
    def _refresh_title(self, count: int) -> None:
        if count == 0:
            self._title.setText(
                "<b>Images</b>  <span style='color:#9A9CA3;'>(none loaded)</span>"
            )
        else:
            self._title.setText(
                f"<b>Images</b>  <span style='color:#9A9CA3;'>({count} loaded · "
                f"click a card to set the active preview source)</span>"
            )
