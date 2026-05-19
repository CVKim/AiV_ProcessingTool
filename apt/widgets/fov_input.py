"""FOV-number text input — accepts ``1,2,3`` or ``1,2,3/5`` (ranges)."""

from __future__ import annotations

from PyQt5.QtWidgets import QLineEdit, QWidget


class FOVInput(QLineEdit):
    """QLineEdit with the common AIVEX FOV placeholder."""

    PLACEHOLDER = "FOV Number(s), e.g. 1,2,3 or 1,2,3/5"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(self.PLACEHOLDER)

    def value(self) -> str:
        return self.text().strip()
