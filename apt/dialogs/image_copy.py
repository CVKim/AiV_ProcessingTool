from __future__ import annotations

from PyQt5.QtWidgets import QFormLayout, QLabel

from apt.constants import OP_IMAGE_COPY
from apt.dialogs.base import BaseTaskPanel
from apt.widgets import FormatSelector, PathPicker


class ImageFormatCopyPanel(BaseTaskPanel):
    TITLE = "Image Format Copy"
    SUBTITLE = "Source 폴더 바로 아래의 파일 중 선택한 포맷만 Target으로 복사합니다."

    def build_form(self, form: QFormLayout) -> None:
        self.source_picker = PathPicker("Select Source Path", "Select Source Folder")
        form.addRow(QLabel("<b>Source Path</b>"), self.source_picker)
        self.target_picker = PathPicker("Select Target Path", "Select Target Folder")
        form.addRow(QLabel("<b>Target Path</b>"), self.target_picker)
        self.format_selector = FormatSelector()
        form.addRow(QLabel("<b>Image Formats</b>"), self.format_selector)

    def get_parameters(self) -> dict:
        return {
            "operation": OP_IMAGE_COPY,
            "sources": [self.source_picker.text()],
            "targets": [self.target_picker.text()],
            "formats": self.format_selector.selected(),
        }

    def validate_parameters(self, params: dict) -> bool:
        missing: list[str] = []
        if not params["sources"][0]:
            missing.append("Source Path")
        if not params["targets"][0]:
            missing.append("Target Path")
        if not params["formats"]:
            missing.append("Image Formats")
        invalid: list[str] = []
        import os
        if params["sources"][0] and not os.path.isdir(params["sources"][0]):
            invalid.append("Source Path이(가) 유효하지 않습니다.")
        return self.warn_missing(missing, invalid)
