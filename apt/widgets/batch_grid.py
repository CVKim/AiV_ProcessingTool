"""Grid view of a preprocessing leaf node's output across all loaded images.

Used inside the Preprocessing inspector's "All images" tab. The host calls
:meth:`BatchResultGrid.set_results` with the list of (caption, image-or-None)
pairs whenever the selected leaf or the image set changes.
"""

from __future__ import annotations

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from apt.widgets.image_preview import _ndarray_to_pixmap


THUMB_WIDTH = 200
THUMB_HEIGHT = 150
COLUMNS = 3


class _ResultCard(QFrame):
    def __init__(
        self,
        caption: str,
        image: np.ndarray | None,
        error: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(THUMB_WIDTH, THUMB_HEIGHT + 28)
        self.setStyleSheet(
            "_ResultCard { background-color: #15161B; border: 1px solid #2A2D35;"
            " border-radius: 6px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setMinimumHeight(THUMB_HEIGHT - 4)
        self._image_label.setStyleSheet(
            "background-color: #08080A; border: 1px solid #2A2D35; border-radius: 4px;"
        )
        if error:
            self._image_label.setText(f"⚠ {error}")
            self._image_label.setStyleSheet(
                "background-color: #1D1F26; border: 1px solid #E5484D; border-radius: 4px;"
                " color: #E5484D; padding: 6px;"
            )
            self._image_label.setWordWrap(True)
        elif image is not None:
            pixmap = _ndarray_to_pixmap(image)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    THUMB_WIDTH - 12, THUMB_HEIGHT - 8,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
                self._image_label.setPixmap(scaled)
        else:
            self._image_label.setText("(no result)")
            self._image_label.setStyleSheet(
                "background-color: #08080A; border: 1px solid #2A2D35; border-radius: 4px;"
                " color: #9A9CA3;"
            )
        layout.addWidget(self._image_label, 1)

        cap = QLabel(caption)
        cap.setAlignment(Qt.AlignCenter)
        cap.setStyleSheet("color: #EDEDEF; font-size: 10px; background: transparent;")
        cap.setToolTip(caption)
        f = QFont(); f.setPointSize(9)
        cap.setFont(f)
        layout.addWidget(cap)


class BatchResultGrid(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: list[_ResultCard] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self._header = QLabel("(no node selected)")
        self._header.setStyleSheet("color: #9A9CA3; font-size: 11px;")
        outer.addWidget(self._header)

        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QFrame.NoFrame)
        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(8)
        scroller.setWidget(self._container)
        outer.addWidget(scroller, 1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_header(self, text: str) -> None:
        self._header.setText(text)

    def set_results(
        self,
        entries: list[tuple[str, np.ndarray | None, str | None]],
    ) -> None:
        """``entries`` is a list of ``(caption, image_or_none, error_or_none)``."""
        # Drop existing cards.
        for card in self._cards:
            self._grid.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        for index, (caption, image, error) in enumerate(entries):
            card = _ResultCard(caption, image, error)
            row, col = divmod(index, COLUMNS)
            self._grid.addWidget(card, row, col, Qt.AlignTop | Qt.AlignLeft)
            self._cards.append(card)
        # Stretch a final spacer so cards stay left-aligned at top.
        self._grid.setRowStretch(self._grid.rowCount(), 1)
        self._grid.setColumnStretch(COLUMNS, 1)
