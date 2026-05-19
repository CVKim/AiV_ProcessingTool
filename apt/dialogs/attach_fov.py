from __future__ import annotations

import os

from PyQt5.QtWidgets import QFormLayout, QLabel

from apt.constants import OP_ATTACH_FOV
from apt.dialogs.base import BaseTaskPanel
from apt.widgets import FOVInput, PathPicker


class AttachFOVPanel(BaseTaskPanel):
    TITLE = "Attach FOV"
    SUBTITLE = (
        "두 폴더에서 동일 FOV 번호를 가진 fov*.jpg 이미지를 찾아 좌우로 붙입니다."
    )

    def build_form(self, form: QFormLayout) -> None:
        self.search1_picker = PathPicker("Select Search Folder #1", "Select Search Folder #1")
        form.addRow(QLabel("<b>Search Folder Path #1</b>"), self.search1_picker)
        self.search2_picker = PathPicker("Select Search Folder #2", "Select Search Folder #2")
        form.addRow(QLabel("<b>Search Folder Path #2</b>"), self.search2_picker)
        self.target_picker = PathPicker("Select Target Path", "Select Target Folder")
        form.addRow(QLabel("<b>Target Path</b>"), self.target_picker)
        self.fov_input = FOVInput()
        form.addRow(QLabel("<b>FOV Number(s)</b>"), self.fov_input)

    def get_parameters(self) -> dict:
        return {
            "operation": OP_ATTACH_FOV,
            "search1": self.search1_picker.text(),
            "search2": self.search2_picker.text(),
            "target": self.target_picker.text(),
            "fov_number": self.fov_input.value(),
        }

    def validate_parameters(self, params: dict) -> bool:
        missing: list[str] = []
        for key, label in (("search1", "Search Folder Path #1"),
                           ("search2", "Search Folder Path #2"),
                           ("target", "Target Path")):
            if not params[key]:
                missing.append(label)
        invalid: list[str] = []
        for key in ("search1", "search2", "target"):
            v = params[key]
            if v and not os.path.isdir(v):
                invalid.append(f"{key} 경로가 유효하지 않습니다.")
        return self.warn_missing(missing, invalid)
