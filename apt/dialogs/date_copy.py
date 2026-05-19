from __future__ import annotations

from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
)

from apt.constants import OP_DATE_COPY
from apt.dialogs.base import BaseTaskPanel
from apt.widgets import FormatSelector, FOVInput, PathPicker


class DateBasedCopyPanel(BaseTaskPanel):
    TITLE = "Date-Based Copy"
    SUBTITLE = "지정한 일시 이후 수정된 폴더 N개(또는 폴더 내 이미지)를 복사합니다."

    def build_form(self, form: QFormLayout) -> None:
        mode_row = QHBoxLayout()
        self.mode_folder = QCheckBox("Folder")
        self.mode_image = QCheckBox("Image")
        self.mode_folder.setChecked(True)
        self.mode_folder.stateChanged.connect(self._toggle_mode)
        self.mode_image.stateChanged.connect(self._toggle_mode)
        mode_row.addWidget(self.mode_folder)
        mode_row.addWidget(self.mode_image)
        mode_row.addStretch(1)
        form.addRow(QLabel("<b>Mode</b>"), mode_row)

        self.datetime_edit = QDateTimeEdit()
        self.datetime_edit.setCalendarPopup(True)
        self.datetime_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.datetime_edit.setDateTime(QDateTime.currentDateTime())
        form.addRow(QLabel("<b>Date and Time</b>"), self.datetime_edit)

        random_row = QHBoxLayout()
        self.strong_random = QCheckBox("Strong Random")
        self.conditional_random = QCheckBox("Conditional Random")
        self.strong_random.stateChanged.connect(self._on_strong_changed)
        self.conditional_random.stateChanged.connect(self._on_conditional_changed)
        random_row.addWidget(self.strong_random)
        random_row.addWidget(self.conditional_random)
        random_row.addStretch(1)
        form.addRow(QLabel("<b>Random Options</b>"), random_row)

        self.random_count = QSpinBox()
        self.random_count.setRange(1, 1000)
        self.random_count.setEnabled(False)
        form.addRow(QLabel("<b>Random Count</b>"), self.random_count)

        self.count_input = QSpinBox()
        self.count_input.setRange(1, 1000)
        self.count_input.setValue(1)
        form.addRow(QLabel("<b>Number of Folders to Copy</b>"), self.count_input)

        self.fov_input = FOVInput()
        self.fov_input.setEnabled(False)
        form.addRow(QLabel("<b>FOV Numbers</b>"), self.fov_input)

        self.source_picker = PathPicker("Select Source Path", "Select Source Folder")
        form.addRow(QLabel("<b>Source Path</b>"), self.source_picker)

        self.target_picker = PathPicker("Select Target Path", "Select Target Folder")
        form.addRow(QLabel("<b>Target Path</b>"), self.target_picker)

        self.format_selector = FormatSelector()
        form.addRow(QLabel("<b>Image Formats</b>"), self.format_selector)

    # -- toggles --------------------------------------------------------
    def _toggle_mode(self, _state: int) -> None:
        sender = self.sender()
        if sender is self.mode_folder and self.mode_folder.isChecked():
            self.mode_image.setChecked(False)
            self.fov_input.setEnabled(False)
        elif sender is self.mode_image and self.mode_image.isChecked():
            self.mode_folder.setChecked(False)
            self.fov_input.setEnabled(True)
        elif self.mode_folder.isChecked() and self.mode_image.isChecked():
            self.mode_image.setChecked(False)
            self.fov_input.setEnabled(False)

    def _on_strong_changed(self, state: int) -> None:
        if state == Qt.Checked:
            self.conditional_random.setChecked(False)
            self.random_count.setEnabled(False)

    def _on_conditional_changed(self, state: int) -> None:
        if state == Qt.Checked:
            self.strong_random.setChecked(False)
            self.random_count.setEnabled(True)
        else:
            self.random_count.setEnabled(False)

    # -- task wiring ----------------------------------------------------
    def get_parameters(self) -> dict:
        if self.mode_folder.isChecked():
            mode = "folder"
        elif self.mode_image.isChecked():
            mode = "image"
        else:
            mode = "folder"

        fov_numbers: list[str] = []
        if mode == "image":
            raw = self.fov_input.value()
            if raw:
                for part in (p.strip() for p in raw.split(",") if p.strip()):
                    if "/" in part:
                        try:
                            start, end = part.split("/", 1)
                            start_i = int(start.strip())
                            end_i = int(end.strip())
                            if start_i <= end_i:
                                fov_numbers.extend(str(n) for n in range(start_i, end_i + 1))
                        except ValueError:
                            continue
                    elif part.isdigit():
                        fov_numbers.append(part)

        dt = self.datetime_edit.dateTime()
        return {
            "operation": OP_DATE_COPY,
            "mode": mode,
            "source": self.source_picker.text(),
            "target": self.target_picker.text(),
            "year": dt.date().year(),
            "month": dt.date().month(),
            "day": dt.date().day(),
            "hour": dt.time().hour(),
            "minute": dt.time().minute(),
            "second": dt.time().second(),
            "count": self.count_input.value(),
            "fov_numbers": fov_numbers,
            "formats": self.format_selector.selected(),
            "strong_random": self.strong_random.isChecked(),
            "conditional_random": self.conditional_random.isChecked(),
            "random_count": self.random_count.value() if self.conditional_random.isChecked() else 0,
        }

    def validate_parameters(self, params: dict) -> bool:
        missing: list[str] = []
        if not params["source"]:
            missing.append("Source Path")
        if not params["target"]:
            missing.append("Target Path")
        if params["mode"] == "image" and not params["fov_numbers"]:
            missing.append("FOV Numbers")
        if not params["formats"]:
            missing.append("Image Formats")
        if params.get("strong_random") and params.get("conditional_random"):
            missing.append("Strong Random과 Conditional Random은 동시에 선택할 수 없습니다.")
        invalid = self.validate_paths(params, ("source",))
        return self.warn_missing(missing, invalid)
