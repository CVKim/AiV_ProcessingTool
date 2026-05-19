"""Sidebar for the AIVEX Processing Tool main window.

Displays the brand block + grouped navigation buttons. Emits ``navigated(int)``
with the corresponding stacked-page index whenever the user selects a button.
"""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Sidebar(QFrame):
    navigated = pyqtSignal(int)

    def __init__(
        self,
        sections: list[tuple[str, list[tuple[str, int]]]],
        parent: QWidget | None = None,
    ) -> None:
        """``sections``: list of ``(section_title, [(button_label, page_index), ...])``."""
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand = QLabel("AIVEX")
        brand.setObjectName("BrandLabel")
        layout.addWidget(brand)
        tagline = QLabel("PROCESSING TOOL")
        tagline.setObjectName("BrandSub")
        layout.addWidget(tagline)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []

        for section_title, buttons in sections:
            section_label = QLabel(section_title.upper())
            section_label.setObjectName("SectionLabel")
            layout.addWidget(section_label)
            for label, page_index in buttons:
                btn = QPushButton(label)
                btn.setObjectName("NavButton")
                btn.setCheckable(True)
                btn.clicked.connect(lambda _checked, idx=page_index: self.navigated.emit(idx))
                self._group.addButton(btn, page_index)
                layout.addWidget(btn)
                self._buttons.append(btn)

        layout.addStretch(1)

        footer = QLabel("© AIVEX")
        footer.setObjectName("BrandSub")
        layout.addWidget(footer)

    def select(self, page_index: int) -> None:
        button = self._group.button(page_index)
        if button is not None:
            button.setChecked(True)
