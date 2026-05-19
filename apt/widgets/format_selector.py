"""Image-format checkbox group used by sorting / copy / crop dialogs."""

from __future__ import annotations

from PyQt5.QtWidgets import QCheckBox, QHBoxLayout, QWidget

from apt.constants import FORMAT_CHOICES


class FormatSelector(QWidget):
    """Horizontal row of checkboxes for the AIVEX image formats.

    Exposes ``.selected()`` to retrieve the worker-compatible list of format
    tokens (matches what the legacy dialogs produced).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._boxes: list[tuple[QCheckBox, str]] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        for label, token in FORMAT_CHOICES:
            box = QCheckBox(label)
            layout.addWidget(box)
            self._boxes.append((box, token))
        layout.addStretch(1)

    def selected(self) -> list[str]:
        return [token for box, token in self._boxes if box.isChecked()]

    def set_checked(self, tokens: list[str]) -> None:
        tokens_lower = {t.lower() for t in tokens}
        for box, token in self._boxes:
            box.setChecked(token.lower() in tokens_lower)

    def clear(self) -> None:
        for box, _ in self._boxes:
            box.setChecked(False)
