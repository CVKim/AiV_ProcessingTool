"""Read-only log console with timestamps and a Clear button."""

from __future__ import annotations

from datetime import datetime

from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogConsole(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(QLabel("<b>Logs</b>"))
        header.addStretch(1)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear)
        header.addWidget(self.clear_button)

        self.text = QTextEdit()
        self.text.setObjectName("LogConsole")
        self.text.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self.text, 1)

    # -- API ------------------------------------------------------------
    def append(self, message: str) -> None:
        if not message:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        self.text.append(f"[{stamp}] {message}")

    def clear(self) -> None:  # noqa: D401
        self.text.clear()
