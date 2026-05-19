"""NG Count panel — bespoke layout (table + summary), shares lifecycle with base."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from apt.constants import OP_NG_COUNT
from apt.dialogs.base import BaseTaskPanel
from apt.widgets import PathPicker


class NGCountPanel(BaseTaskPanel):
    TITLE = "NG Count"
    SUBTITLE = "NG 폴더의 Cam_*/Defect 통계를 계산하고 클립보드에 복사할 수 있습니다."

    def build_form(self, form: QFormLayout) -> None:
        self.ng_picker = PathPicker("Select NG Folder", "Select NG Folder", read_only=True)
        form.addRow(QLabel("<b>NG Folder</b>"), self.ng_picker)

        # Result group (table + summary + copy)
        result_group = QGroupBox("NG Count Results")
        result_layout = QVBoxLayout(result_group)
        header_row = QHBoxLayout()
        self.summary_label = QLabel("<b>대기 중…</b>")
        self.summary_label.setTextFormat(Qt.RichText)
        self.copy_button = QPushButton("Copy")
        self.copy_button.setFixedWidth(72)
        self.copy_button.clicked.connect(self._copy_table_to_clipboard)
        header_row.addWidget(self.summary_label, 1)
        header_row.addWidget(self.copy_button)
        result_layout.addLayout(header_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["CamNum", "Defect Name", "Count"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setMinimumHeight(180)
        result_layout.addWidget(self.table)

        form.addRow(result_group)

    # -- task lifecycle overrides --------------------------------------
    def get_parameters(self) -> dict:
        return {"operation": OP_NG_COUNT, "ng_folder": self.ng_picker.text()}

    def validate_parameters(self, params: dict) -> bool:
        ng = params.get("ng_folder", "")
        if not ng:
            QMessageBox.warning(self, "입력 오류", "NG 폴더를 선택해야 합니다.")
            return False
        return True

    def start_task(self) -> None:
        # Reset visible state before running.
        self.table.setRowCount(0)
        self.summary_label.setText("<b>실행 중…</b>")
        super().start_task()

    def update_ng_count_table(self, data) -> None:  # type: ignore[override]
        rows, total_top_folders, total_cams, total_defects = data
        self.table.setRowCount(len(rows))
        for row, (cam, defect, count) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(str(cam)))
            self.table.setItem(row, 1, QTableWidgetItem(str(defect)))
            self.table.setItem(row, 2, QTableWidgetItem(str(count)))
        summary = (
            f"Total Folder — {total_top_folders}, "
            f"Search Cam Count — {total_cams}, "
            f"Defect Count — {total_defects}"
        )
        self.summary_label.setText(f"<b>{summary}</b>")

    def _copy_table_to_clipboard(self) -> None:
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "복사 오류", "복사할 데이터가 없습니다.")
            return
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        lines = ["\t".join(headers)]
        for row in range(self.table.rowCount()):
            cells = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                cells.append(item.text() if item is not None else "")
            lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "복사 완료", "Copy to the clipboard")
