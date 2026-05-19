"""Operation picker sidebar for the Preprocessing panel.

A scrollable list of category groups, each holding card-style buttons for
the operations belonging to that category. A search box at the top filters
the cards in real time.

Emits ``opActivated(op_key)`` when the user double-clicks (or hits Enter on)
a card.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from apt.preprocessing import OPERATIONS, style_for


_HINT_BY_KEY: dict[str, str] = {
    "resize": "Change width/height, or scale by factor",
    "rotate": "Rotate around centre (optionally grow canvas)",
    "flip": "Horizontal / vertical / both",
    "to_gray": "Convert to single-channel grayscale",
    "invert": "Bitwise inversion (255 - x)",
    "brightness_contrast": "Linear: out = x · contrast + brightness",
    "gamma": "Per-pixel power transform",
    "gaussian_blur": "Smooth with a Gaussian kernel",
    "median_blur": "Smooth with median (good vs salt-and-pepper)",
    "bilateral": "Edge-preserving smoothing",
    "box_blur": "Simple averaging filter",
    "sharpen": "Unsharp mask",
    "threshold_binary": "Hard cutoff at a fixed threshold",
    "threshold_otsu": "Auto threshold using Otsu's method",
    "threshold_adaptive": "Per-region threshold (gaussian or mean)",
    "canny": "Canny edge detector",
    "sobel": "Sobel gradient (x / y / magnitude)",
    "laplacian": "Laplacian edge detector",
    "erode": "Shrink bright regions",
    "dilate": "Grow bright regions",
    "open": "Erode then dilate (removes specks)",
    "close": "Dilate then erode (closes holes)",
    "equalize_hist": "Global histogram equalisation",
    "clahe": "Contrast-limited adaptive equalisation",
    "blend": "α·A + (1-α)·B",
    "add": "Saturating A + B",
    "subtract": "Saturating A - B",
    "max": "Per-pixel max(A, B)",
    "min": "Per-pixel min(A, B)",
}


class OpCard(QPushButton):
    """One operation in the sidebar — a button styled as a card."""

    def __init__(self, op, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.op = op
        style = style_for(op.category)
        self._accent = style.color
        self._hint = _HINT_BY_KEY.get(op.key, "")
        text_html = (
            f"<div style='line-height:1.25; padding-left:8px;'>"
            f"<div style='font-weight:700; color:#EDEDEF;'>"
            f"{op.label}</div>"
            f"<div style='font-size:10px; color:#9A9CA3;'>"
            f"{self._hint or op.category}</div>"
            f"</div>"
        )
        # QPushButton doesn't render HTML in setText, so embed a child QLabel.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(0)
        body = QLabel(text_html)
        body.setTextFormat(Qt.RichText)
        body.setStyleSheet("background: transparent;")
        layout.addWidget(body, 1)
        self.setText("")  # icon-only — content is in the label
        self._tokens = " ".join(
            [op.key, op.label, op.category, self._hint]
        ).lower()
        self.setStyleSheet(self._stylesheet(self._accent))
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(46)

    def matches(self, query: str) -> bool:
        if not query:
            return True
        return query.lower() in self._tokens

    @staticmethod
    def _stylesheet(accent: str) -> str:
        return (
            "QPushButton {"
            f" background-color: #15161B;"
            f" border: 1px solid #2A2D35;"
            f" border-left: 4px solid {accent};"
            f" border-radius: 4px;"
            f" padding: 0;"
            f" text-align: left;"
            "}"
            "QPushButton:hover {"
            f" background-color: #1D1F26;"
            f" border-color: {accent};"
            "}"
            "QPushButton:pressed {"
            f" background-color: #0B0B0E;"
            "}"
        )


class OpPicker(QWidget):
    opActivated = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QLabel("<b>Operations</b>")
        header.setStyleSheet("font-size: 13px;")
        layout.addWidget(header)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter (e.g. blur, edge, threshold)…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_filter)
        layout.addWidget(self.search)

        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(0)  # NoFrame
        container = QWidget()
        self._list_layout = QVBoxLayout(container)
        self._list_layout.setContentsMargins(0, 0, 6, 0)
        self._list_layout.setSpacing(6)
        scroller.setWidget(container)
        layout.addWidget(scroller, 1)

        hint = QLabel("Double-click a card to add it to the graph.")
        hint.setStyleSheet("color: #9A9CA3; font-size: 10px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Build groups
        self._cards: list[OpCard] = []
        self._headers: list[tuple[QLabel, list[OpCard]]] = []
        current_category: str | None = None
        current_cards: list[OpCard] = []
        current_header: QLabel | None = None

        for op in OPERATIONS:
            if op.category != current_category:
                if current_header is not None:
                    self._headers.append((current_header, current_cards))
                current_category = op.category
                current_cards = []
                style = style_for(op.category)
                current_header = self._make_category_header(op.category, style.color, style.hint)
                self._list_layout.addWidget(current_header)
            card = OpCard(op)
            card.installEventFilter(self)  # for double-click handling
            self._list_layout.addWidget(card)
            self._cards.append(card)
            current_cards.append(card)
        if current_header is not None:
            self._headers.append((current_header, current_cards))
        self._list_layout.addStretch(1)

    def _make_category_header(self, name: str, color: str, hint: str) -> QLabel:
        text = (
            f"<div style='padding:8px 0 4px 0;'>"
            f"<span style='color:{color}; font-weight:800; letter-spacing:1px;'>"
            f"{name.upper()}</span>"
            f"<span style='color:#6E7079; font-size:10px;'>  ·  {hint}</span>"
            f"</div>"
        )
        label = QLabel(text)
        label.setTextFormat(Qt.RichText)
        return label

    # Double-click on a card → activate.
    def eventFilter(self, obj, event):  # noqa: N802
        from PyQt5.QtCore import QEvent
        if isinstance(obj, OpCard) and event.type() == QEvent.MouseButtonDblClick:
            self.opActivated.emit(obj.op.key)
            return True
        return super().eventFilter(obj, event)

    def selected_op_key(self) -> str | None:
        for card in self._cards:
            if card.hasFocus():
                return card.op.key
        return None

    # ------------------------------------------------------------------
    def _on_filter(self, text: str) -> None:
        for header, cards in self._headers:
            any_visible = False
            for card in cards:
                visible = card.matches(text)
                card.setVisible(visible)
                if visible:
                    any_visible = True
            header.setVisible(any_visible)
