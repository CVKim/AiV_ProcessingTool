from __future__ import annotations

import logging
import os
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from apt.constants import OP_NG_SORTING
from apt.dialogs.base import BaseTaskPanel
from apt.widgets import FormatSelector, PathPicker


class NGSortingPanel(BaseTaskPanel):
    TITLE = "NG Folder Sorting"
    SUBTITLE = (
        "여러 NG 폴더(Source #1)와 Matching 폴더(Source #2)의 Inner ID 교집합을 찾아, "
        "선택한 포맷의 이미지를 Target에 정리합니다."
    )

    def build_form(self, form: QFormLayout) -> None:
        self.add_button = QPushButton("Add NG Folder…")
        self.add_button.clicked.connect(self._open_subfolder_picker)
        form.addRow(QLabel("<b>Source Path #1 (NG Folders)</b>"), self.add_button)

        self.source1_list = QListWidget()
        self.source1_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.source1_list.setMinimumHeight(110)
        form.addRow("", self.source1_list)

        self.remove_button = QPushButton("Remove Selected Folder")
        self.remove_button.clicked.connect(self._remove_selected)
        form.addRow("", self.remove_button)

        self.source2_picker = PathPicker("Select Matching Folder", "Select Matching Folder")
        form.addRow(QLabel("<b>Source Path #2 (Matching Folder)</b>"), self.source2_picker)

        self.target_picker = PathPicker("Select Target Path", "Select Target Folder")
        form.addRow(QLabel("<b>Target Path</b>"), self.target_picker)

        self.format_selector = FormatSelector()
        form.addRow(QLabel("<b>Image Formats</b>"), self.format_selector)

    # -- subfolder picker dialog (carried over from legacy) -----------
    def _open_subfolder_picker(self) -> None:
        parent_folder = QFileDialog.getExistingDirectory(
            self, "Select Parent Folder", "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if not parent_folder:
            return
        try:
            with os.scandir(parent_folder) as it:
                subfolders = [
                    entry.name for entry in it
                    if entry.is_dir() and entry.name.lower() not in {"ok", "ng"}
                ]
        except Exception as exc:
            logging.error("서브폴더 목록 가져오기 중 오류", exc_info=True)
            QMessageBox.warning(self, "오류", f"서브폴더 목록 가져오기 중 오류:\n{exc}")
            return
        if not subfolders:
            QMessageBox.information(self, "정보", "선택한 폴더 내에 서브 폴더가 없습니다.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Subfolders")
        dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)

        table = QTableWidget(len(subfolders), 2)
        table.setHorizontalHeaderLabels(["Folder Name", "Last Modified"])
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.MultiSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSortingEnabled(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for row, folder in enumerate(subfolders):
            name_item = QTableWidgetItem(folder)
            name_item.setFlags(name_item.flags() ^ Qt.ItemIsEditable)
            table.setItem(row, 0, name_item)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(os.path.join(parent_folder, folder)))
                mtime_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                mtime_str = "N/A"
            date_item = QTableWidgetItem(mtime_str)
            date_item.setFlags(date_item.flags() ^ Qt.ItemIsEditable)
            table.setItem(row, 1, date_item)

        layout.addWidget(QLabel("Select subfolders to add:"))
        layout.addWidget(table)

        buttons = QHBoxLayout()
        ok = QPushButton("OK")
        cancel = QPushButton("Cancel")
        ok.clicked.connect(dialog.accept)
        cancel.clicked.connect(dialog.reject)
        buttons.addStretch(1)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

        if dialog.exec_() != QDialog.Accepted:
            return

        existing = {self.source1_list.item(i).text() for i in range(self.source1_list.count())}
        for index in table.selectionModel().selectedRows():
            row = index.row()
            sub_name = table.item(row, 0).text()
            full_path = os.path.join(parent_folder, sub_name)
            if full_path in existing:
                QMessageBox.information(self, "정보", f"이미 추가된 폴더입니다:\n{full_path}")
            else:
                self.source1_list.addItem(full_path)

    def _remove_selected(self) -> None:
        items = self.source1_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "선택 오류", "제거할 폴더를 선택하세요.")
            return
        for item in items:
            self.source1_list.takeItem(self.source1_list.row(item))

    # -- task wiring ----------------------------------------------------
    def get_parameters(self) -> dict:
        sources1 = [self.source1_list.item(i).text() for i in range(self.source1_list.count())]
        return {
            "operation": OP_NG_SORTING,
            "inputs": sources1,
            "source2": self.source2_picker.text(),
            "target": self.target_picker.text(),
            "formats": self.format_selector.selected(),
        }

    def validate_parameters(self, params: dict) -> bool:
        missing: list[str] = []
        if not params["inputs"]:
            missing.append("Source Path #1에 최소 하나의 폴더를 추가해야 합니다.")
        if not params["source2"]:
            missing.append("Source Path #2를 선택해야 합니다.")
        if not params["target"]:
            missing.append("Target Path를 선택해야 합니다.")
        if not params["formats"]:
            missing.append("Image Formats")
        return self.warn_missing(missing)
