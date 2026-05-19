from __future__ import annotations

from PyQt5.QtWidgets import QFormLayout, QLabel

from apt.constants import OP_SIMULATION
from apt.dialogs.base import BaseTaskPanel
from apt.widgets import FormatSelector, PathPicker


class SimulationFolderingPanel(BaseTaskPanel):
    TITLE = "Simulation Foldering"
    SUBTITLE = "시뮬레이션용 폴더 구조 생성 (현재 자리표시자 — 작업 로직은 worker에 정의)."

    def build_form(self, form: QFormLayout) -> None:
        self.source_picker = PathPicker("Select Source Path", "Select Source Folder")
        form.addRow(QLabel("<b>Source Path</b>"), self.source_picker)
        self.target_picker = PathPicker("Select Target Path", "Select Target Folder")
        form.addRow(QLabel("<b>Target Path</b>"), self.target_picker)
        self.format_selector = FormatSelector()
        form.addRow(QLabel("<b>Image Formats</b>"), self.format_selector)

    def get_parameters(self) -> dict:
        return {
            "operation": OP_SIMULATION,
            "source": self.source_picker.text(),
            "target": self.target_picker.text(),
            "formats": self.format_selector.selected(),
        }

    def validate_parameters(self, params: dict) -> bool:
        missing: list[str] = []
        if not params["source"]:
            missing.append("Source Path")
        if not params["target"]:
            missing.append("Target Path")
        if not params["formats"]:
            missing.append("Image Formats")
        invalid = self.validate_paths(params, ("source", "target"))
        return self.warn_missing(missing, invalid)
