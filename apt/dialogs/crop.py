from __future__ import annotations

from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
)

from apt.constants import OP_CROP
from apt.dialogs.base import BaseTaskPanel
from apt.widgets import FormatSelector, FOVInput, PathPicker


class CropPanel(BaseTaskPanel):
    TITLE = "Crop"
    SUBTITLE = (
        "이미지 트리에서 FOV(선택)에 해당하는 파일을 크롭합니다. "
        "BMP에 동명의 JSON이 있으면 라벨 좌표도 함께 보정됩니다."
    )

    def build_form(self, form: QFormLayout) -> None:
        self.source_picker = PathPicker("Select Source Path", "Select Source Folder")
        form.addRow(QLabel("<b>Source Path</b>"), self.source_picker)
        self.target_picker = PathPicker("Select Target Path", "Select Target Folder")
        form.addRow(QLabel("<b>Target Path</b>"), self.target_picker)
        self.fov_input = FOVInput()
        form.addRow(QLabel("<b>FOV Number(s)</b>"), self.fov_input)

        self.coords_mode = QComboBox()
        self.coords_mode.addItems(
            ["ltrb (Left/Top/Right/Bottom)", "xywh (StartX/StartY/Width/Height)"]
        )
        self.coords_mode.currentIndexChanged.connect(self._on_coords_mode_changed)
        form.addRow(QLabel("<b>Coords Mode</b>"), self.coords_mode)

        crop_row = QHBoxLayout()
        self.lx = QLineEdit(); self.lx.setPlaceholderText("LEFT_TOP_X")
        self.ly = QLineEdit(); self.ly.setPlaceholderText("LEFT_TOP_Y")
        self.rx = QLineEdit(); self.rx.setPlaceholderText("RIGHT_BOTTOM_X")
        self.ry = QLineEdit(); self.ry.setPlaceholderText("RIGHT_BOTTOM_Y")
        for label, edit in (("LeftX", self.lx), ("TopY", self.ly), ("RightX", self.rx), ("BotY", self.ry)):
            crop_row.addWidget(QLabel(f"{label}:"))
            crop_row.addWidget(edit)
        form.addRow(QLabel("<b>Crop Area (Pixels)</b>"), crop_row)

        self.format_selector = FormatSelector()
        form.addRow(QLabel("<b>Image Formats</b>"), self.format_selector)

    def _on_coords_mode_changed(self, idx: int) -> None:
        if idx == 0:
            self.lx.setPlaceholderText("LEFT_TOP_X")
            self.ly.setPlaceholderText("LEFT_TOP_Y")
            self.rx.setPlaceholderText("RIGHT_BOTTOM_X")
            self.ry.setPlaceholderText("RIGHT_BOTTOM_Y")
        else:
            self.lx.setPlaceholderText("START_X")
            self.ly.setPlaceholderText("START_Y")
            self.rx.setPlaceholderText("WIDTH")
            self.ry.setPlaceholderText("HEIGHT")

    def get_parameters(self) -> dict:
        return {
            "operation": OP_CROP,
            "source": self.source_picker.text(),
            "target": self.target_picker.text(),
            "formats": self.format_selector.selected(),
            "fov_number": self.fov_input.value(),
            "left_top_x": self.lx.text().strip(),
            "left_top_y": self.ly.text().strip(),
            "right_bottom_x": self.rx.text().strip(),
            "right_bottom_y": self.ry.text().strip(),
            "coords_mode": "xywh" if self.coords_mode.currentIndex() == 1 else "ltrb",
        }

    def validate_parameters(self, params: dict) -> bool:
        missing: list[str] = []
        if not params["source"]:
            missing.append("Source Path")
        if not params["target"]:
            missing.append("Target Path")
        if not params["formats"]:
            missing.append("Image Formats")
        for key, desc in (
            ("left_top_x", "Left Top X"),
            ("left_top_y", "Left Top Y"),
            ("right_bottom_x", "Right Bottom X"),
            ("right_bottom_y", "Right Bottom Y"),
        ):
            val = params.get(key, "")
            if not val:
                missing.append(desc)
            else:
                try:
                    int(val)
                except ValueError:
                    missing.append(f"{desc} (정수 필요)")
        invalid = self.validate_paths(params, ("source", "target"))
        return self.warn_missing(missing, invalid)
