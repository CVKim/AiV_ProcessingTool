from __future__ import annotations

import os

from PyQt5.QtWidgets import QFormLayout, QLabel

from apt.constants import OP_BTJ
from apt.dialogs.base import BaseTaskPanel
from apt.widgets import PathPicker


class BMPtoJPGPanel(BaseTaskPanel):
    TITLE = "BMP to JPG (BTJ)"
    SUBTITLE = (
        "Source 폴더 내 모든 .bmp 파일을 재귀로 찾아 .jpg로 변환합니다. "
        "Target 미입력 시 Source 옆에 ``<Source>_JPG`` 폴더가 자동 생성됩니다."
    )

    def build_form(self, form: QFormLayout) -> None:
        self.source_picker = PathPicker(
            "Select Source Path (BMP files)", "Select Source Folder (BMP files)"
        )
        form.addRow(QLabel("<b>Source Path</b>"), self.source_picker)
        self.target_picker = PathPicker(
            "Select Target Path (Optional)", "Select Target Folder (Optional)"
        )
        form.addRow(QLabel("<b>Target Path (optional)</b>"), self.target_picker)

        note = QLabel("※ Target 미입력 시, Source 뒤에 '_JPG' 폴더가 자동 생성됩니다.")
        note.setStyleSheet("color: #9A9CA3; font-size: 11px;")
        form.addRow("", note)

    def get_parameters(self) -> dict:
        return {
            "operation": OP_BTJ,
            "source": self.source_picker.text(),
            "target": self.target_picker.text(),
        }

    def validate_parameters(self, params: dict) -> bool:
        missing: list[str] = []
        if not params["source"]:
            missing.append("Source Path (BMP 폴더)")
        invalid: list[str] = []
        if params["source"] and not os.path.isdir(params["source"]):
            invalid.append("Source Path이(가) 유효하지 않습니다.")
        return self.warn_missing(missing, invalid)
