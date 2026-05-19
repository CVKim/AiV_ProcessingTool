"""Path picker widget — replaces the QPushButton + QLineEdit + select_xxx
boilerplate that appeared in every legacy dialog.
"""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PathPicker(QWidget):
    """Folder (or file) picker with a label, button and editable line.

    Emits ``pathChanged(str)`` whenever the path is set or typed.
    """

    pathChanged = pyqtSignal(str)

    def __init__(
        self,
        button_label: str = "Select Path",
        dialog_caption: str | None = None,
        placeholder: str = "",
        pick_file: bool = False,
        file_filter: str = "All files (*.*)",
        read_only: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._pick_file = pick_file
        self._caption = dialog_caption or button_label
        self._filter = file_filter

        self.button = QPushButton(button_label)
        self.button.clicked.connect(self._open_dialog)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setReadOnly(read_only)
        self.edit.textChanged.connect(self.pathChanged.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self.button, 1)
        layout.addLayout(top)
        layout.addWidget(self.edit)

    # -- API ------------------------------------------------------------
    def text(self) -> str:
        return self.edit.text().strip()

    def set_text(self, value: str) -> None:
        self.edit.setText(value)

    def clear(self) -> None:
        self.edit.clear()

    def set_enabled(self, enabled: bool) -> None:  # noqa: D401
        self.edit.setEnabled(enabled)
        self.button.setEnabled(enabled)

    # -- Internal -------------------------------------------------------
    def _open_dialog(self) -> None:
        if self._pick_file:
            path, _ = QFileDialog.getOpenFileName(self, self._caption, "", self._filter)
        else:
            path = QFileDialog.getExistingDirectory(
                self,
                self._caption,
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
            )
        if path:
            self.edit.setText(path)
