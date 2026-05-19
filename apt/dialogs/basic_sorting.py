from __future__ import annotations

import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCheckBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit

from apt.constants import OP_BASIC_SORTING
from apt.dialogs.base import BaseTaskPanel
from apt.widgets import FormatSelector, FOVInput, PathPicker


class BasicSortingPanel(BaseTaskPanel):
    TITLE = "Basic Sorting"
    SUBTITLE = (
        "Inner ID list 폴더에서 정의된 ID 기준으로 source의 이미지를 prefix를 붙여 평탄화 복사합니다. "
        "Double Path는 Code/InnerID 2단계 트리, Only Defect는 기준 폴더의 FOV만 추출 모드입니다."
    )

    def build_form(self, form: QFormLayout) -> None:
        self.inner_id_list = PathPicker("Select Inner ID List Path", "Select Inner ID List Path")
        form.addRow(QLabel("<b>Inner ID List Path</b>"), self.inner_id_list)

        options_row = QHBoxLayout()
        self.double_path_checkbox = QCheckBox("Double Path Folder (Code/InnerID)")
        self.only_defect_checkbox = QCheckBox("Only Defect Image Sorting")
        options_row.addWidget(self.double_path_checkbox)
        options_row.addWidget(self.only_defect_checkbox)
        options_row.addStretch(1)
        form.addRow(QLabel("<b>Path Options</b>"), options_row)
        self.only_defect_checkbox.stateChanged.connect(self._toggle_only_defect)

        self.source_picker = PathPicker("Select Matching Path", "Select Source Folder")
        form.addRow(QLabel("<b>Source Path</b>"), self.source_picker)

        self.target_picker = PathPicker("Select Target Path", "Select Target Folder")
        form.addRow(QLabel("<b>Target Path</b>"), self.target_picker)

        self.fov_input = FOVInput()
        form.addRow(QLabel("<b>FOV Number(s)</b>"), self.fov_input)

        self.use_inner_id_checkbox = QCheckBox("Use Inner ID (direct input)")
        self.use_inner_id_checkbox.stateChanged.connect(self._toggle_use_inner_id)
        form.addRow(QLabel("<b>Inner ID</b>"), self.use_inner_id_checkbox)

        self.inner_id_input = QLineEdit()
        self.inner_id_input.setPlaceholderText("Enter Inner ID")
        self.inner_id_input.setEnabled(False)
        form.addRow("", self.inner_id_input)

        self.format_selector = FormatSelector()
        form.addRow(QLabel("<b>Image Formats</b>"), self.format_selector)

    # -- option toggles -------------------------------------------------
    def _toggle_only_defect(self, state: int) -> None:
        if state == Qt.Checked:
            self.fov_input.setEnabled(False)
            self.fov_input.clear()
            self.append_log(
                "Only Defect Image Sorting 모드 ON — FOV는 Inner ID List Path 파일명 기준 자동 추출됩니다."
            )
        else:
            self.fov_input.setEnabled(True)

    def _toggle_use_inner_id(self, state: int) -> None:
        if state == Qt.Checked:
            self.inner_id_input.setEnabled(True)
            self.inner_id_list.set_enabled(False)
            self.inner_id_list.clear()
        else:
            self.inner_id_input.setEnabled(False)
            self.inner_id_input.clear()
            self.inner_id_list.set_enabled(True)

    # -- task wiring ----------------------------------------------------
    def get_parameters(self) -> dict:
        return {
            "operation": OP_BASIC_SORTING,
            "source": self.source_picker.text(),
            "target": self.target_picker.text(),
            "inner_id_list": self.inner_id_list.text(),
            "use_inner_id": self.use_inner_id_checkbox.isChecked(),
            "inner_id": self.inner_id_input.text().strip(),
            "fov_number": self.fov_input.value(),
            "formats": self.format_selector.selected(),
            "double_path_folder": self.double_path_checkbox.isChecked(),
            "only_defect_sorting": self.only_defect_checkbox.isChecked(),
        }

    def validate_parameters(self, params: dict) -> bool:
        missing: list[str] = []
        if not params["inner_id_list"] and not params["use_inner_id"]:
            missing.append("Inner ID List Path 또는 Inner ID")
        if not params["target"]:
            missing.append("Target Path")
        if not params["formats"]:
            missing.append("Image Formats")
        if not params["inner_id_list"] and params["use_inner_id"] and not params["inner_id"]:
            missing.append("Inner ID")

        invalid = self.validate_paths(params, ("source", "inner_id_list"))
        target = params.get("target", "")
        if target and not os.path.isdir(target):
            try:
                os.makedirs(target, exist_ok=True)
            except OSError as exc:
                invalid.append(f"Target Path 생성 실패: {target} | 에러: {exc}")
        return self.warn_missing(missing, invalid)
