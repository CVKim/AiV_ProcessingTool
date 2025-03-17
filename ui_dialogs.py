# ui_dialogs.py
import sys
import os
import logging
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFormLayout, QLineEdit, QProgressBar, QFileDialog, QMessageBox, QLabel,
    QListWidget, QTableWidget, QTableWidgetItem, QHeaderView, QDateTimeEdit,
    QTextEdit, QDialog, QSpinBox, QCheckBox
)
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtGui import QIcon
from worker import WorkerThread
from PyQt5.QtCore import QThreadPool
logging.basicConfig(filename='error.log', level=logging.ERROR,
                    format='%(asctime)s:%(levelname)s:%(message)s')

# ---------------------------------------------------------
# 공통 베이스 Dialog
class BaseTaskDialog(QDialog):
    def __init__(self, title):
        super().__init__()
        self.setWindowTitle(title)
        self.setFixedSize(800, 800)
        self.worker = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        self.specific_layout = QFormLayout()
        form_layout.addRow(self.specific_layout)
        layout.addLayout(form_layout)

        log_layout = QHBoxLayout()
        log_label = QLabel("<b>Logs:</b>")
        self.clear_log_button = QPushButton("Clear")
        self.clear_log_button.clicked.connect(self.clear_logs)
        log_layout.addWidget(log_label)
        log_layout.addStretch()
        log_layout.addWidget(self.clear_log_button)
        layout.addLayout(log_layout)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #F5F5F5;
                font-family: Consolas;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border: 1px solid #CCC;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.log_area)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 10px;
                text-align: center;
                height: 30px;
            }
            QProgressBar::chunk {
                background-color: #8B0000;
                width: 20px;
            }
        """)
        layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_task)
        self.start_button.setStyleSheet("background-color: #FF7029; color: white; padding: 10px; font-size: 14px; border-radius: 5px;")
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_task)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("background-color: #A9A9A9; color: white; padding: 10px; font-size: 14px; border-radius: 5px;")
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def append_log(self, message):
        self.log_area.append(message)

    def clear_logs(self):
        self.log_area.clear()

    def start_task(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "작업 중", "이미 작업이 진행 중입니다.")
            return
        self.log_area.append("------ 작업 시작 ------")
        self.progress_bar.setValue(0)
        params = self.get_parameters()
        if not self.validate_parameters(params):
            self.log_area.append("------ 작업 중지 ------")
            return
        self.worker = WorkerThread(params)
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.append_log)
        if params.get('operation') == 'ng_count':
            self.worker.ng_count_result.connect(self.update_ng_count_table)
        self.worker.finished.connect(self.task_finished)
        self.worker.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_task(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.append_log("Stop 신호를 보냈습니다.")
            self.stop_button.setEnabled(False)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def task_finished(self, message):
        self.append_log(message)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        if "완료" in message or "오류" in message or "중지" in message:
            self.append_log("------ 작업 종료 ------")

    def validate_parameters(self, params):
        missing_fields = []
        operation = params.get('operation', '')
        if operation != 'ng_count':
            if not params.get('source'):
                missing_fields.append("Source Path")
            # if not params.get('target'):
            #     missing_fields.append("Target Path")
        if operation not in ['ng_count', 'btj'] and not params.get('formats', []):
            missing_fields.append("Image Formats")
        if operation == 'ng_sorting' and not params.get('source2'):
            missing_fields.append("Source Path #2 (Matching Folder)")
        if operation == 'ng_count' and not params.get('ng_folder', ''):
            missing_fields.append("NG 폴더를 선택해야 합니다.")
        if params.get('strong_random', False) and params.get('conditional_random', False):
            missing_fields.append("Strong Random과 Conditional Random은 동시에 선택할 수 없습니다.")

        path_fields = ['source', 'target', 'inner_id_list', 'source2', 'ng_folder']
        invalid_paths = []
        for field in path_fields:
            path = params.get(field, '')
            if path and not os.path.isdir(path):
                invalid_paths.append(f"{field.capitalize()} Path이(가) 유효하지 않습니다.")
        if missing_fields or invalid_paths:
            QMessageBox.warning(self, "입력 오류", f"다음 항목을 확인하세요:\n" + "\n".join(missing_fields + invalid_paths))
            return False
        return True

    def get_parameters(self):
        return {}

    def update_ng_count_table(self, data):
        pass

# ---------------------------------------------------------
# 기존 Dialog들
class BasicSortingDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Basic Sorting 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        self.inner_id_list_button = QPushButton("Select Inner ID List Path")
        self.inner_id_list_button.clicked.connect(self.select_inner_id_list)
        self.inner_id_list_path = QLineEdit()
        self.inner_id_list_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Inner ID List Path:</b>"), self.inner_id_list_button)
        self.specific_layout.addRow("", self.inner_id_list_path)

        self.source_button = QPushButton("Select Matching Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        self.specific_layout.addRow("", self.source_path)

        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

        self.fov_input = QLineEdit()
        self.fov_input.setPlaceholderText("Enter FOV Number(s), separated by commas (e.g., 1,2,3 or 1,2,3/5)")
        self.specific_layout.addRow(QLabel("<b>FOV Number(s):</b>"), self.fov_input)

        self.inner_id_checkbox = QCheckBox("Use Inner ID")
        self.inner_id_checkbox.stateChanged.connect(self.toggle_inner_id)
        self.specific_layout.addRow(QLabel("<b>Inner ID:</b>"), self.inner_id_checkbox)

        self.inner_id_input = QLineEdit()
        self.inner_id_input.setPlaceholderText("Enter Inner ID")
        self.inner_id_input.setEnabled(False)
        self.specific_layout.addRow("", self.inner_id_input)

        self.format_bmp = QCheckBox("BMP")
        self.format_org_jpg = QCheckBox("org_jpg")
        self.format_fov_jpg = QCheckBox("fov_jpg")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_org_jpg)
        formats_layout.addWidget(self.format_fov_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)
        self.format_bmp.setChecked(True)

    def toggle_inner_id(self, state):
        if state == Qt.Checked:
            self.inner_id_input.setEnabled(True)
            self.inner_id_list_path.setEnabled(False)
            self.inner_id_list_button.setEnabled(False)
            self.inner_id_list_path.clear()
        else:
            self.inner_id_input.setEnabled(False)
            self.inner_id_input.clear()
            self.inner_id_list_path.setEnabled(True)
            self.inner_id_list_button.setEnabled(True)

    def select_inner_id_list(self):
        inner_id_list = QFileDialog.getExistingDirectory(self, "Select Inner ID List Path", "",
                                                          QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if inner_id_list:
            self.inner_id_list_path.setText(inner_id_list)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def select_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if source:
            self.source_path.setText(source)

    def get_parameters(self):
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_org_jpg.isChecked():
            formats.append("org_jpg")
        if self.format_fov_jpg.isChecked():
            formats.append("fov_jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")
        return {
            'operation': 'basic_sorting',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'inner_id_list': self.inner_id_list_path.text(),
            'use_inner_id': self.inner_id_checkbox.isChecked(),
            'inner_id': self.inner_id_input.text(),
            'fov_number': self.fov_input.text(),
            'formats': formats
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['inner_id_list'] and not params['use_inner_id']:
            missing_fields.append("Inner ID List Path 또는 Inner ID")
        # if not params['source']:
        #     missing_fields.append("Source Path")
        if not params['target']:
            missing_fields.append("Target Path")
        # if not params['fov_number']:
        #     missing_fields.append("FOV Number(s)")
        if not params['formats'] and params['operation'] != 'ng_count':
            missing_fields.append("Image Formats")
        if not params['inner_id_list'] and params['use_inner_id'] and not params['inner_id']:
            missing_fields.append("Inner ID")

        path_fields = ['source', 'inner_id_list']
        invalid_paths = []
        for field in path_fields:
            path = params.get(field, '')
            if path and not os.path.isdir(path):
                invalid_paths.append(f"{field.capitalize()} Path이(가) 유효하지 않습니다.")
        target_path = params.get('target', '')
        if target_path:
            if not os.path.isdir(target_path):
                try:
                    os.makedirs(target_path)
                except Exception as e:
                    invalid_paths.append(f"Target Path 생성 실패: {target_path} | 에러: {e}")
                    
        if missing_fields or invalid_paths:
            warning_messages = []
            if missing_fields:
                warning_messages.append("다음 필드를 입력해야 합니다:")
                warning_messages.extend(missing_fields)
            if invalid_paths:
                warning_messages.append("다음 경로가 유효하지 않습니다:")
                warning_messages.extend(invalid_paths)
            QMessageBox.warning(self, "입력 오류", "\n".join(warning_messages))
            return False
        return True

class NGSortingDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("NG Folder Sorting 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        self.add_source_button = QPushButton("Add NG Folder")
        self.add_source_button.clicked.connect(self.add_source_folder)
        self.source1_list = QListWidget()
        self.source1_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.specific_layout.addRow(QLabel("<b>Source Path #1 (NG Folders):</b>"), self.add_source_button)
        self.specific_layout.addRow("", self.source1_list)

        self.remove_source_button = QPushButton("Remove Selected Folder")
        self.remove_source_button.clicked.connect(self.remove_selected_source_folder)
        self.specific_layout.addRow("", self.remove_source_button)

        self.source2_button = QPushButton("Select Matching Folder")
        self.source2_button.clicked.connect(self.select_source2)
        self.source2_path = QLineEdit()
        self.source2_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Source Path #2 (Matching Folder):</b>"), self.source2_button)
        self.specific_layout.addRow("", self.source2_path)

        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

        self.format_bmp = QCheckBox("BMP")
        self.format_org_jpg = QCheckBox("org_jpg")
        self.format_fov_jpg = QCheckBox("fov_jpg")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_org_jpg)
        formats_layout.addWidget(self.format_fov_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)
        self.format_bmp.setChecked(True)

    def add_source_folder(self):
        parent_folder = QFileDialog.getExistingDirectory(self, "Select Parent Folder", "",
                                                         QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if parent_folder:
            try:
                with os.scandir(parent_folder) as it:
                    subfolders = [entry.name for entry in it if entry.is_dir() and entry.name.lower() not in ['ok', 'ng']]
                if not subfolders:
                    QMessageBox.information(self, "정보", "선택한 폴더 내에 서브 폴더가 없습니다.")
                    return
            except Exception as e:
                logging.error("서브폴더 목록 가져오기 중 오류", exc_info=True)
                QMessageBox.warning(self, "오류", f"서브폴더 목록 가져오기 중 오류가 발생했습니다:\n{str(e)}")
                return
            dialog = QDialog(self)
            dialog.setWindowTitle("Select Subfolders")
            dialog.setFixedSize(600, 400)
            dialog_layout = QVBoxLayout()

            table_widget = QTableWidget()
            table_widget.setRowCount(len(subfolders))
            table_widget.setColumnCount(2)
            table_widget.setHorizontalHeaderLabels(["Folder Name", "Last Modified Date"])
            table_widget.setSelectionBehavior(QTableWidget.SelectRows)
            table_widget.setSelectionMode(QTableWidget.MultiSelection)
            table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
            table_widget.setSortingEnabled(True)
            table_widget.horizontalHeader().setStretchLastSection(True)
            table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

            for row, folder in enumerate(subfolders):
                folder_name_item = QTableWidgetItem(folder)
                folder_name_item.setFlags(folder_name_item.flags() ^ Qt.ItemIsEditable)
                table_widget.setItem(row, 0, folder_name_item)

                folder_path = os.path.join(parent_folder, folder)
                try:
                    modified_timestamp = os.path.getmtime(folder_path)
                    modified_datetime = datetime.fromtimestamp(modified_timestamp)
                    modified_str = modified_datetime.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    modified_str = "N/A"
                    logging.error("폴더 수정 시간 가져오기 중 오류", exc_info=True)
                date_item = QTableWidgetItem(modified_str)
                date_item.setFlags(date_item.flags() ^ Qt.ItemIsEditable)
                table_widget.setItem(row, 1, date_item)

            dialog_layout.addWidget(QLabel("Select subfolders to add:"))
            dialog_layout.addWidget(table_widget)

            button_layout = QHBoxLayout()
            ok_button = QPushButton("OK")
            cancel_button = QPushButton("Cancel")
            ok_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            dialog_layout.addLayout(button_layout)

            dialog.setLayout(dialog_layout)

            if dialog.exec_() == QDialog.Accepted:
                selected_rows = table_widget.selectionModel().selectedRows()
                selected_subfolders = [table_widget.item(row.row(), 0).text() for row in selected_rows]
                for sub in selected_subfolders:
                    full_path = os.path.join(parent_folder, sub)
                    existing_items = [self.source1_list.item(i).text() for i in range(self.source1_list.count())]
                    if full_path not in existing_items:
                        self.source1_list.addItem(full_path)
                    else:
                        QMessageBox.information(self, "정보", f"이미 추가된 폴더입니다:\n{full_path}")

    def remove_selected_source_folder(self):
        selected_items = self.source1_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "선택 오류", "제거할 폴더를 선택하세요.")
            return
        for item in selected_items:
            self.source1_list.takeItem(self.source1_list.row(item))

    def select_source2(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Matching Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if folder:
            self.source2_path.setText(folder)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def get_parameters(self):
        sources1 = [self.source1_list.item(i).text() for i in range(self.source1_list.count())]
        source2 = self.source2_path.text()
        target = self.target_path.text()
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_org_jpg.isChecked():
            formats.append("org_jpg")
        if self.format_fov_jpg.isChecked():
            formats.append("fov_jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")
        return {
            'operation': 'ng_sorting',
            'inputs': sources1,
            'source2': source2,
            'target': target,
            'formats': formats
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['inputs']:
            missing_fields.append("Source Path #1에 최소 하나의 폴더를 추가해야 합니다.")
        if not params['source2']:
            missing_fields.append("Source Path #2를 선택해야 합니다.")
        if not params['target']:
            missing_fields.append("Target Path를 선택해야 합니다.")
        if not params['formats'] and params['operation'] != 'ng_count':
            missing_fields.append("Image Formats")

        if missing_fields:
            QMessageBox.warning(self, "입력 오류", f"다음 필드를 입력해야 합니다:\n" + "\n".join(missing_fields))
            return False
        return True

class DateBasedCopyDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Date-Based Copy 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        self.mode_folder_checkbox = QCheckBox("Folder")
        self.mode_image_checkbox = QCheckBox("Image")
        self.mode_folder_checkbox.setChecked(True)
        self.mode_folder_checkbox.stateChanged.connect(self.toggle_mode)
        self.mode_image_checkbox.stateChanged.connect(self.toggle_mode)
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(self.mode_folder_checkbox)
        mode_layout.addWidget(self.mode_image_checkbox)
        self.specific_layout.addRow(QLabel("<b>Mode:</b>"), mode_layout)

        self.datetime_edit = QDateTimeEdit(self)
        self.datetime_edit.setCalendarPopup(True)
        self.datetime_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.datetime_edit.setDateTime(QDateTime.currentDateTime())
        self.specific_layout.addRow(QLabel("<b>Date and Time:</b>"), self.datetime_edit)

        self.strong_random_checkbox = QCheckBox("Strong Random")
        self.conditional_random_checkbox = QCheckBox("Conditional Random")
        self.strong_random_checkbox.setChecked(False)
        self.conditional_random_checkbox.setChecked(False)
        self.strong_random_checkbox.stateChanged.connect(self.on_strong_random_changed)
        self.conditional_random_checkbox.stateChanged.connect(self.on_conditional_random_changed)
        random_layout = QHBoxLayout()
        random_layout.addWidget(self.strong_random_checkbox)
        random_layout.addWidget(self.conditional_random_checkbox)
        self.specific_layout.addRow(QLabel("<b>Random Options:</b>"), random_layout)

        self.random_count_spinbox = QSpinBox()
        self.random_count_spinbox.setRange(1, 1000)
        self.random_count_spinbox.setValue(1)
        self.random_count_spinbox.setEnabled(False)
        self.specific_layout.addRow(QLabel("<b>Random Count:</b>"), self.random_count_spinbox)

        self.count_input = QSpinBox()
        self.count_input.setRange(1, 1000)
        self.count_input.setValue(1)
        self.specific_layout.addRow(QLabel("<b>Number of Folders to Copy:</b>"), self.count_input)

        self.fov_numbers_label = QLabel("<b>FOV Numbers:</b>")
        self.fov_numbers_input = QLineEdit()
        self.fov_numbers_input.setPlaceholderText("Enter FOV Number(s), separated by commas (e.g., 1,2,3/5)")
        self.fov_numbers_input.setEnabled(False)
        self.specific_layout.addRow(self.fov_numbers_label, self.fov_numbers_input)

        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        self.specific_layout.addRow("", self.source_path)

        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

        self.format_bmp = QCheckBox("BMP")
        self.format_org_jpg = QCheckBox("org_jpg")
        self.format_fov_jpg = QCheckBox("fov_jpg")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_org_jpg)
        formats_layout.addWidget(self.format_fov_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)
        self.format_bmp.setChecked(True)

    def on_strong_random_changed(self, state):
        if state == Qt.Checked:
            self.conditional_random_checkbox.setChecked(False)
            self.random_count_spinbox.setEnabled(False)

    def on_conditional_random_changed(self, state):
        if state == Qt.Checked:
            self.strong_random_checkbox.setChecked(False)
            self.random_count_spinbox.setEnabled(True)
        else:
            self.random_count_spinbox.setEnabled(False)

    def toggle_mode(self, state):
        if self.sender() == self.mode_folder_checkbox and state == Qt.Checked:
            self.mode_image_checkbox.setChecked(False)
            self.fov_numbers_input.setEnabled(False)
        elif self.sender() == self.mode_image_checkbox and state == Qt.Checked:
            self.mode_folder_checkbox.setChecked(False)
            self.fov_numbers_input.setEnabled(True)
        elif self.mode_folder_checkbox.isChecked() and self.mode_image_checkbox.isChecked():
            self.mode_image_checkbox.setChecked(False)
            self.fov_numbers_input.setEnabled(False)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def select_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if source:
            self.source_path.setText(source)

    def get_parameters(self):
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_org_jpg.isChecked():
            formats.append("org_jpg")
        if self.format_fov_jpg.isChecked():
            formats.append("fov_jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")

        if self.mode_folder_checkbox.isChecked():
            mode = 'folder'
        elif self.mode_image_checkbox.isChecked():
            mode = 'image'
        else:
            mode = 'folder'
        fov_numbers = []
        if mode == 'image':
            fov_number_input = self.fov_numbers_input.text().strip()
            if fov_number_input:
                fov_numbers_raw = [num.strip() for num in fov_number_input.split(',') if num.strip()]
                for part in fov_numbers_raw:
                    if '/' in part:
                        try:
                            start, end = part.split('/')
                            start = int(start.strip())
                            end = int(end.strip())
                            if start > end:
                                continue
                            fov_numbers.extend([str(n) for n in range(start, end+1)])
                        except:
                            continue
                    else:
                        if part.isdigit():
                            fov_numbers.append(part)

        dt = self.datetime_edit.dateTime()
        year = dt.date().year()
        month = dt.date().month()
        day = dt.date().day()
        hour = dt.time().hour()
        minute = dt.time().minute()
        second = dt.time().second()

        return {
            'operation': 'date_copy',
            'mode': mode,
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'year': year,
            'month': month,
            'day': day,
            'hour': hour,
            'minute': minute,
            'second': second,
            'count': self.count_input.value(),
            'fov_numbers': fov_numbers,
            'formats': formats,
            'strong_random': self.strong_random_checkbox.isChecked(),
            'conditional_random': self.conditional_random_checkbox.isChecked(),
            'random_count': self.random_count_spinbox.value() if self.conditional_random_checkbox.isChecked() else 0
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['source']:
            missing_fields.append("Source Path")
        if not params['target']:
            missing_fields.append("Target Path")
        if params['mode'] == 'image' and not params['fov_numbers']:
            missing_fields.append("FOV Numbers")
        if not params['formats'] and params['operation'] != 'ng_count':
            missing_fields.append("Image Formats")
        if params.get('strong_random', False) and params.get('conditional_random', False):
            missing_fields.append("Strong Random과 Conditional Random은 동시에 선택할 수 없습니다.")

        # path_fields = ['source', 'target']
        # target 경로는 자동으로 만질어 지게 하기 위함
        path_fields = ['source']
        invalid_paths = []
        for field in path_fields:
            path = params.get(field, '')
            if path and not os.path.isdir(path):
                invalid_paths.append(f"{field.capitalize()} Path이(가) 유효하지 않습니다.")

        if missing_fields or invalid_paths:
            warning_messages = []
            if missing_fields:
                warning_messages.append("다음 필드를 입력해야 합니다:")
                warning_messages.extend(missing_fields)
            if invalid_paths:
                warning_messages.append("다음 경로가 유효하지 않습니다:")
                warning_messages.extend(invalid_paths)
            QMessageBox.warning(self, "입력 오류", "\n".join(warning_messages))
            return False
        return True

class ImageFormatCopyDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Image Format Copy 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        self.specific_layout.addRow("", self.source_path)

        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

        self.format_bmp = QCheckBox("BMP")
        self.format_org_jpg = QCheckBox("org_jpg")
        self.format_fov_jpg = QCheckBox("fov_jpg")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_org_jpg)
        formats_layout.addWidget(self.format_fov_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)
        self.format_bmp.setChecked(True)

    def select_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if source:
            self.source_path.setText(source)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def get_parameters(self):
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_org_jpg.isChecked():
            formats.append("org_jpg")
        if self.format_fov_jpg.isChecked():
            formats.append("fov_jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")
        return {
            'operation': 'image_copy',
            'sources': [self.source_path.text()],
            'targets': [self.target_path.text()],
            'formats': formats
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['sources'][0]:
            missing_fields.append("Source Path")
        if not params['targets'][0]:
            missing_fields.append("Target Path")
        if not params['formats'] and params['operation'] != 'ng_count':
            missing_fields.append("Image Formats")

        invalid_paths = []
        # sources, targets는 리스트로 들어가므로
        if params['sources'][0] and not os.path.isdir(params['sources'][0]):
            invalid_paths.append("Source Path이(가) 유효하지 않습니다.")
        # if params['targets'][0] and not os.path.isdir(params['targets'][0]):
        #     invalid_paths.append("Target Path이(가) 유효하지 않습니다.")

        if missing_fields or invalid_paths:
            warning_messages = []
            if missing_fields:
                warning_messages.append("다음 필드를 입력해야 합니다:")
                warning_messages.extend(missing_fields)
            if invalid_paths:
                warning_messages.append("다음 경로가 유효하지 않습니다:")
                warning_messages.extend(invalid_paths)
            QMessageBox.warning(self, "입력 오류", "\n".join(warning_messages))
            return False
        return True

class SimulationFolderingDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Simulation Foldering 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        self.specific_layout.addRow("", self.source_path)

        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

        self.format_bmp = QCheckBox("BMP")
        self.format_org_jpg = QCheckBox("org_jpg")
        self.format_fov_jpg = QCheckBox("fov_jpg")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_org_jpg)
        formats_layout.addWidget(self.format_fov_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)
        self.format_bmp.setChecked(True)

    def select_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if source:
            self.source_path.setText(source)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def get_parameters(self):
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_org_jpg.isChecked():
            formats.append("org_jpg")
        if self.format_fov_jpg.isChecked():
            formats.append("fov_jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")
        return {
            'operation': 'simulation_foldering',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'formats': formats
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['source']:
            missing_fields.append("Source Path")
        if not params['target']:
            missing_fields.append("Target Path")
        if not params['formats'] and params['operation'] != 'ng_count':
            missing_fields.append("Image Formats")

        path_fields = ['source', 'target']
        invalid_paths = []
        for field in path_fields:
            path = params.get(field, '')
            if path and not os.path.isdir(path):
                invalid_paths.append(f"{field.capitalize()} Path이(가) 유효하지 않습니다.")

        if missing_fields or invalid_paths:
            warning_messages = []
            if missing_fields:
                warning_messages.append("다음 필드를 입력해야 합니다:")
                warning_messages.extend(missing_fields)
            if invalid_paths:
                warning_messages.append("다음 경로가 유효하지 않습니다:")
                warning_messages.extend(invalid_paths)
            QMessageBox.warning(self, "입력 오류", "\n".join(warning_messages))
            return False
        return True

class NGCountDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NG Count 설정")
        self.setFixedSize(800, 600)
        self.worker = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        self.ng_folder_button = QPushButton("Select NG Folder")
        self.ng_folder_button.clicked.connect(self.select_ng_folder)
        self.ng_folder_path = QLineEdit()
        self.ng_folder_path.setReadOnly(False)
        form_layout.addRow(QLabel("<b>Counting - Select NG folder:</b>"), self.ng_folder_button)
        form_layout.addRow("", self.ng_folder_path)
        layout.addLayout(form_layout)

        ng_count_results_layout = QHBoxLayout()
        ng_count_label = QLabel("<b>NG Count Results:</b>")
        self.copy_button = QPushButton("Copy")
        self.copy_button.setFixedSize(60, 25)
        self.copy_button.clicked.connect(self.copy_table_to_clipboard)
        ng_count_results_layout.addWidget(ng_count_label)
        ng_count_results_layout.addStretch()
        ng_count_results_layout.addWidget(self.copy_button)
        layout.addLayout(ng_count_results_layout)

        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(3)
        self.table_widget.setHorizontalHeaderLabels(["CamNum", "Defect Name", "Count"])
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table_widget)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 10px;
                text-align: center;
                height: 30px;
            }
            QProgressBar::chunk {
                background-color: #8B0000;
                width: 20px;
            }
        """)
        layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_task)
        self.start_button.setStyleSheet("background-color: #FF7029; color: white; padding: 10px; font-size: 14px; border-radius: 5px;")
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_task)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("background-color: #A9A9A9; color: white; padding: 10px; font-size: 14px; border-radius: 5px;")
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def select_ng_folder(self):
        ng_folder = QFileDialog.getExistingDirectory(self, "Select NG Folder", "",
                                                     QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if ng_folder:
            self.ng_folder_path.setText(ng_folder)

    def start_task(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "작업 중", "이미 작업이 진행 중입니다.")
            return
        self.table_widget.setRowCount(0)
        self.progress_bar.setValue(0)
        ng_folder = self.ng_folder_path.text()
        if not ng_folder:
            QMessageBox.warning(self, "입력 오류", "NG 폴더를 선택해야 합니다.")
            return
        task = {'operation': 'ng_count', 'ng_folder': ng_folder}
        self.worker = WorkerThread(task)
        self.worker.progress.connect(self.update_progress)
        self.worker.ng_count_result.connect(self.update_ng_count_table)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.task_finished)
        self.worker.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_task(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.append_log("Stop 신호를 보냈습니다.")
            self.stop_button.setEnabled(False)

    def append_log(self, message):
        # NGCountDialog에서는 별도 log_area가 없으므로 pass
        pass

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_ng_count_table(self, data):
        self.table_widget.setRowCount(len(data))
        for row, (cam, defect, count) in enumerate(data):
            cam_item = QTableWidgetItem(cam)
            defect_item = QTableWidgetItem(defect)
            count_item = QTableWidgetItem(str(count))
            self.table_widget.setItem(row, 0, cam_item)
            self.table_widget.setItem(row, 1, defect_item)
            self.table_widget.setItem(row, 2, count_item)

    def task_finished(self, message):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        QMessageBox.information(self, "작업 완료", message)

    def copy_table_to_clipboard(self):
        if self.table_widget.rowCount() == 0:
            QMessageBox.warning(self, "복사 오류", "복사할 데이터가 없습니다.")
            return
        clipboard = QApplication.clipboard()
        data = []
        headers = [self.table_widget.horizontalHeaderItem(i).text() for i in range(self.table_widget.columnCount())]
        data.append('\t'.join(headers))
        for row in range(self.table_widget.rowCount()):
            row_data = []
            for column in range(self.table_widget.columnCount()):
                item = self.table_widget.item(row, column)
                if item is not None:
                    row_data.append(item.text())
                else:
                    row_data.append('')
            data.append('\t'.join(row_data))
        clipboard.setText('\n'.join(data))
        QMessageBox.information(self, "복사 완료", "Copy to the clipboard")

# ---------------------------------------------------------
# 여기서부터 새로 추가할 Dialog들 (MIMtoBMP, AttachFOV, Temp)

class AttachFOVDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Attach FOV 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        # Search #1
        self.search1_button = QPushButton("Select Search Folder #1")
        self.search1_button.clicked.connect(self.select_search1)
        self.search1_path = QLineEdit()
        self.search1_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Search Folder Path #1:</b>"), self.search1_button)
        self.specific_layout.addRow("", self.search1_path)

        # Search #2
        self.search2_button = QPushButton("Select Search Folder #2")
        self.search2_button.clicked.connect(self.select_search2)
        self.search2_path = QLineEdit()
        self.search2_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Search Folder Path #2:</b>"), self.search2_button)
        self.specific_layout.addRow("", self.search2_path)

        # Target
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

        # fov_number
        self.fov_input = QLineEdit()
        self.fov_input.setPlaceholderText("fov number(s) e.g., 1,2,3 or 1,2,3/5")
        self.specific_layout.addRow(QLabel("<b>FOV Number(s):</b>"), self.fov_input)

    def select_search1(self):
        path = QFileDialog.getExistingDirectory(self, "Select Search Folder #1", "",
                                                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if path:
            self.search1_path.setText(path)

    def select_search2(self):
        path = QFileDialog.getExistingDirectory(self, "Select Search Folder #2", "",
                                                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if path:
            self.search2_path.setText(path)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "",
                                                  QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def get_parameters(self):
        return {
            'operation': 'attach_fov',
            'search1': self.search1_path.text(),
            'search2': self.search2_path.text(),
            'target': self.target_path.text(),
            'fov_number': self.fov_input.text()
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['search1']:
            missing_fields.append("Search Folder Path #1")
        if not params['search2']:
            missing_fields.append("Search Folder Path #2")
        if not params['target']:
            missing_fields.append("Target Path")

        invalid_paths = []
        for key in ['search1', 'search2', 'target']:
            if params[key] and not os.path.isdir(params[key]):
                invalid_paths.append(f"{key} 경로가 유효하지 않습니다.")

        if missing_fields or invalid_paths:
            warning_messages = []
            if missing_fields:
                warning_messages.append("다음 필드를 입력해야 합니다:")
                warning_messages.extend(missing_fields)
            if invalid_paths:
                warning_messages.append("다음 경로가 유효하지 않습니다:")
                warning_messages.extend(invalid_paths)
            QMessageBox.warning(self, "입력 오류", "\n".join(warning_messages))
            return False
        return True

class MIMtoBMPDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("MIM to BMP 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        # (기능 상세 요구사항이 미정이므로 간단히 Source/Target만)
        self.source_button = QPushButton("Select Source Path (MIM files)")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        self.specific_layout.addRow("", self.source_path)

        self.target_button = QPushButton("Select Target Path (BMP out)")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

    def select_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Folder (MIM files)", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if source:
            self.source_path.setText(source)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder (BMP out)", "",
                                                 QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def get_parameters(self):
        return {
            'operation': 'mim_to_bmp',
            'source': self.source_path.text(),
            'target': self.target_path.text()
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['source']:
            missing_fields.append("Source Path")
        if not params['target']:
            missing_fields.append("Target Path")
        invalid_paths = []
        for field in ['source', 'target']:
            if params[field] and not os.path.isdir(params[field]):
                invalid_paths.append(f"{field.capitalize()} Path이(가) 유효하지 않습니다.")

        if missing_fields or invalid_paths:
            warning_messages = []
            if missing_fields:
                warning_messages.append("다음 필드를 입력해야 합니다:")
                warning_messages.extend(missing_fields)
            if invalid_paths:
                warning_messages.append("다음 경로가 유효하지 않습니다:")
                warning_messages.extend(invalid_paths)
            QMessageBox.warning(self, "입력 오류", "\n".join(warning_messages))
            return False
        return True

class bmptojpgDialog(BaseTaskDialog):
    """
    BMP TO JPG 기능: BMP->JPG 변환용 Dialog
    """
    def __init__(self):
        super().__init__("BMP TO JPG 설정 (BMP->JPG 변환)")
        self.init_specific_ui()

    def init_specific_ui(self):
        # Source Pathd
        self.source_button = QPushButton("Select Source Path (BMP files)")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        self.specific_layout.addRow("", self.source_path)

        # Target Path (선택사항: 비워두면 worker에서 자동 지정)
        self.target_button = QPushButton("Select Target Path (Optional)")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Target Path (optional):</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

        # 안내 라벨
        note_label = QLabel("※ Target 미입력 시, Source 뒤에 '_JPG' 폴더가 자동 생성됩니다.")
        note_label.setStyleSheet("color: #555; font-size: 11px;")
        self.specific_layout.addRow(note_label)

    def select_source(self):
        path = QFileDialog.getExistingDirectory(self, "Select Source Folder (BMP files)", "",
                                                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if path:
            self.source_path.setText(path)

    def select_target(self):
        path = QFileDialog.getExistingDirectory(self, "Select Target Folder (Optional)", "",
                                                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if path:
            self.target_path.setText(path)

    def get_parameters(self):
        return {
            'operation': 'btj',  # BMP->JPG 변환용
            'source': self.source_path.text().strip(),
            'target': self.target_path.text().strip(),
        }

    def validate_parameters(self, params):
        """
        - Source는 반드시 있어야 함
        - Target은 없어도 OK (없으면 worker에서 source+'_JPG' 폴더 생성)
        """
        missing_fields = []
        # Source 필요
        if not params['source']:
            missing_fields.append("Source Path (BMP 폴더)")

        # 경로 유효성 체크
        invalid_paths = []
        # Source는 꼭 존재해야 함
        if params['source'] and not os.path.isdir(params['source']):
            invalid_paths.append("Source Path이(가) 유효하지 않습니다.")

        if missing_fields or invalid_paths:
            warning_messages = []
            if missing_fields:
                warning_messages.append("다음 필드를 입력해야 합니다:")
                warning_messages.extend(missing_fields)
            if invalid_paths:
                warning_messages.append("다음 경로가 유효하지 않습니다:")
                warning_messages.extend(invalid_paths)
            QMessageBox.warning(self, "입력 오류", "\n".join(warning_messages))
            return False
        return True


# ---------------------------------------------------------
# MainWindow
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AiV Processing Tool 🗂️📂📁")
        
        if getattr(sys, 'frozen', False):
            application_path = sys._MEIPASS
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))

        icon_path = os.path.join(application_path, 'AiV_LOGO.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setFixedSize(1000, 200)
        self.initUI()
        self.dialogs = {}
        self.thread_pool = QThreadPool.globalInstance() 

    def initUI(self):
        main_layout = QVBoxLayout()
        self.setStyleSheet("background-color: #2E2E2E;")
        button_layout = QGridLayout()
        button_layout.setSpacing(20)

        def button_style():
            return """
                QPushButton {
                    background-color: #FF7029;
                    color: white;
                    font-size: 12px;
                    font-weight: bold;
                    border: 2px solid black;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #A52A2A;
                }
            """
        buttons = [
            ("NG Folder Sorting", self.open_ng_sorting),
            ("Date-Based Copy", self.open_date_copy),
            ("Image Format Copy", self.open_image_copy),
            ("Basic Sorting", self.open_basic_sorting),
            ("NG Count", self.open_ng_count),
            ("Simulation Foldering", self.open_simulation_foldering),
            ("Crop", self.open_crop),
            ("MIM to BMP", self.open_mim_to_bmp),
            ("Attach FOV", self.open_attach_fov),
            ("BMP TO JPG (BTJ)", self.open_btj),
        ]

        for i, (label, func) in enumerate(buttons):
            button = QPushButton(label)
            button.clicked.connect(func)
            button.setFixedSize(150, 60)
            button.setStyleSheet(button_style())
            button_layout.addWidget(button, i // 5, i % 5)
            
            

        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        
    def closeEvent(self, event):
        
        print("프로그램 종료 중... 실행 중인 작업 정리")
        self.thread_pool.clear()  
        self.thread_pool.waitForDone(1000)  # 최대 3초 동안 종료 시도

        sys.exit(0)  
        
        # self.ng_sorting_button = QPushButton("NG Folder Sorting")
        # self.ng_sorting_button.clicked.connect(self.open_ng_sorting)
        # self.ng_sorting_button.setFixedSize(150, 60)
        # self.ng_sorting_button.setStyleSheet(button_style())
        # button_layout.addWidget(self.ng_sorting_button, 0, 0)

        # self.date_copy_button = QPushButton("Date-Based Copy")
        # self.date_copy_button.clicked.connect(self.open_date_copy)
        # self.date_copy_button.setFixedSize(150, 60)
        # self.date_copy_button.setStyleSheet(button_style())
        # button_layout.addWidget(self.date_copy_button, 0, 1)

        # self.image_copy_button = QPushButton("Image Format Copy")
        # self.image_copy_button.clicked.connect(self.open_image_copy)
        # self.image_copy_button.setFixedSize(150, 60)
        # self.image_copy_button.setStyleSheet(button_style())
        # button_layout.addWidget(self.image_copy_button, 0, 2)

        # self.basic_sorting_button = QPushButton("Basic Sorting")
        # self.basic_sorting_button.clicked.connect(self.open_basic_sorting)
        # self.basic_sorting_button.setFixedSize(150, 60)
        # self.basic_sorting_button.setStyleSheet(button_style())
        # button_layout.addWidget(self.basic_sorting_button, 0, 3)

        # self.ng_count_button = QPushButton("NG Count")
        # self.ng_count_button.clicked.connect(self.open_ng_count)
        # self.ng_count_button.setFixedSize(150, 60)
        # self.ng_count_button.setStyleSheet(button_style())
        # button_layout.addWidget(self.ng_count_button, 0, 4)

        # self.simulation_button = QPushButton("Simulation Foldering")
        # self.simulation_button.clicked.connect(self.open_simulation_foldering)
        # self.simulation_button.setFixedSize(150, 60)
        # self.simulation_button.setStyleSheet(button_style())
        # button_layout.addWidget(self.simulation_button, 1, 0)

        # self.crop_button = QPushButton("Crop")
        # self.crop_button.clicked.connect(self.open_crop)
        # self.crop_button.setFixedSize(150, 60)
        # self.crop_button.setStyleSheet(button_style())
        # button_layout.addWidget(self.crop_button, 1, 1)

        # # --------------- 새로 추가: MIM to BMP, Attach FOV, TEMP ----------------
        # self.mim_to_bmp_button = QPushButton("MIM to BMP")
        # self.mim_to_bmp_button.clicked.connect(self.open_mim_to_bmp)
        # self.mim_to_bmp_button.setFixedSize(150, 60)
        # self.mim_to_bmp_button.setStyleSheet(button_style())
        # button_layout.addWidget(self.mim_to_bmp_button, 1, 2)

        # self.attach_fov_button = QPushButton("Attach FOV")
        # self.attach_fov_button.clicked.connect(self.open_attach_fov)
        # self.attach_fov_button.setFixedSize(150, 60)
        # self.attach_fov_button.setStyleSheet(button_style())
        # button_layout.addWidget(self.attach_fov_button, 1, 3)

        # self.temp_button = QPushButton("TEMP")
        # self.temp_button.clicked.connect(self.open_temp)
        # self.temp_button.setFixedSize(150, 60)
        # self.temp_button.setStyleSheet(button_style())
        # button_layout.addWidget(self.temp_button, 1, 4)
        # # -------------------------------------------------------------------------

        # main_layout.addLayout(button_layout)
        # self.setLayout(main_layout)

    def open_ng_sorting(self):
        if 'ng_sorting' not in self.dialogs:
            self.dialogs['ng_sorting'] = NGSortingDialog()
            self.dialogs['ng_sorting'].finished.connect(lambda: self.dialogs.pop('ng_sorting', None))
        self.dialogs['ng_sorting'].show()

    def open_ng_count(self):
        if 'ng_count' not in self.dialogs:
            self.dialogs['ng_count'] = NGCountDialog()
            self.dialogs['ng_count'].finished.connect(lambda: self.dialogs.pop('ng_count', None))
        self.dialogs['ng_count'].show()

    def open_date_copy(self):
        if 'date_copy' not in self.dialogs:
            self.dialogs['date_copy'] = DateBasedCopyDialog()
            self.dialogs['date_copy'].finished.connect(lambda: self.dialogs.pop('date_copy', None))
        self.dialogs['date_copy'].show()

    def open_image_copy(self):
        if 'image_copy' not in self.dialogs:
            self.dialogs['image_copy'] = ImageFormatCopyDialog()
            self.dialogs['image_copy'].finished.connect(lambda: self.dialogs.pop('image_copy', None))
        self.dialogs['image_copy'].show()

    def open_simulation_foldering(self):
        if 'simulation_foldering' not in self.dialogs:
            self.dialogs['simulation_foldering'] = SimulationFolderingDialog()
            self.dialogs['simulation_foldering'].finished.connect(lambda: self.dialogs.pop('simulation_foldering', None))
        self.dialogs['simulation_foldering'].show()

    def open_basic_sorting(self):
        if 'basic_sorting' not in self.dialogs:
            self.dialogs['basic_sorting'] = BasicSortingDialog()
            self.dialogs['basic_sorting'].finished.connect(lambda: self.dialogs.pop('basic_sorting', None))
        self.dialogs['basic_sorting'].show()

    def open_crop(self):
        if 'crop' not in self.dialogs:
            from ui_dialogs import CropDialog
            self.dialogs['crop'] = CropDialog()
            self.dialogs['crop'].finished.connect(lambda: self.dialogs.pop('crop', None))
        self.dialogs['crop'].show()

    # ---------------------- 새로 추가된 버튼/다이얼로그 연결 ----------------------
    def open_mim_to_bmp(self):
        if 'mim_to_bmp' not in self.dialogs:
            self.dialogs['mim_to_bmp'] = MIMtoBMPDialog()
            self.dialogs['mim_to_bmp'].finished.connect(lambda: self.dialogs.pop('mim_to_bmp', None))
        self.dialogs['mim_to_bmp'].show()

    def open_attach_fov(self):
        if 'attach_fov' not in self.dialogs:
            self.dialogs['attach_fov'] = AttachFOVDialog()
            self.dialogs['attach_fov'].finished.connect(lambda: self.dialogs.pop('attach_fov', None))
        self.dialogs['attach_fov'].show()

    def open_btj(self):
        if 'btj' not in self.dialogs:
            self.dialogs['btj'] = bmptojpgDialog()
            self.dialogs['btj'].finished.connect(lambda: self.dialogs.pop('btj', None))
        self.dialogs['btj'].show()


# ---------------------------------------------------------
# 아래 CropDialog 는 기존에 존재하는 것이므로 그대로 둡니다.
class CropDialog(BaseTaskDialog):
    def __init__(self):
        super().__init__("Crop 설정")
        self.init_specific_ui()

    def init_specific_ui(self):
        # Source Path
        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        self.specific_layout.addRow("", self.source_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(False)
        self.specific_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        self.specific_layout.addRow("", self.target_path)

        # FOV Number(s)
        self.fov_input = QLineEdit()
        self.fov_input.setPlaceholderText("FOV Number(s), e.g., 1,2,3 or 1,2,3/5")
        self.specific_layout.addRow(QLabel("<b>FOV Number(s):</b>"), self.fov_input)

        # Crop Area (4 정수)
        crop_layout = QHBoxLayout()

        self.left_top_x_input = QLineEdit()
        self.left_top_x_input.setPlaceholderText("LEFT_TOP_X")
        crop_layout.addWidget(QLabel("LeftX:"))
        crop_layout.addWidget(self.left_top_x_input)

        self.left_top_y_input = QLineEdit()
        self.left_top_y_input.setPlaceholderText("LEFT_TOP_Y")
        crop_layout.addWidget(QLabel("TopY:"))
        crop_layout.addWidget(self.left_top_y_input)

        self.right_bottom_x_input = QLineEdit()
        self.right_bottom_x_input.setPlaceholderText("RIGHT_BOTTOM_X")
        crop_layout.addWidget(QLabel("RightX:"))
        crop_layout.addWidget(self.right_bottom_x_input)

        self.right_bottom_y_input = QLineEdit()
        self.right_bottom_y_input.setPlaceholderText("RIGHT_BOTTOM_Y")
        crop_layout.addWidget(QLabel("BotY:"))
        crop_layout.addWidget(self.right_bottom_y_input)

        self.specific_layout.addRow(QLabel("<b>Crop Area (Pixels):</b>"), crop_layout)

        # Image Formats
        self.format_bmp = QCheckBox("BMP")
        self.format_org_jpg = QCheckBox("org_jpg")
        self.format_fov_jpg = QCheckBox("fov_jpg")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_org_jpg)
        formats_layout.addWidget(self.format_fov_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        self.specific_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)
        self.format_bmp.setChecked(True)

    def select_source(self):
        path = QFileDialog.getExistingDirectory(self, "Select Source Folder", "",
                                                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if path:
            self.source_path.setText(path)

    def select_target(self):
        path = QFileDialog.getExistingDirectory(self, "Select Target Folder", "",
                                                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if path:
            self.target_path.setText(path)

    def get_parameters(self):
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_org_jpg.isChecked():
            formats.append("org_jpg")
        if self.format_fov_jpg.isChecked():
            formats.append("fov_jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        if self.format_png.isChecked():
            formats.append(".png")

        return {
            'operation': 'crop',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'formats': formats,
            # 추가된 fov_number
            'fov_number': self.fov_input.text().strip(),
            # crop 4개 좌표
            'left_top_x': self.left_top_x_input.text().strip(),
            'left_top_y': self.left_top_y_input.text().strip(),
            'right_bottom_x': self.right_bottom_x_input.text().strip(),
            'right_bottom_y': self.right_bottom_y_input.text().strip()
        }

    def validate_parameters(self, params):
        missing_fields = []
        if not params['source']:
            missing_fields.append("Source Path")
        if not params['target']:
            missing_fields.append("Target Path")
        if not params['formats']:
            missing_fields.append("Image Formats")

        # crop area 4개 좌표 모두 필수 정수
        crop_fields = [
            ('left_top_x', "Left Top X"),
            ('left_top_y', "Left Top Y"),
            ('right_bottom_x', "Right Bottom X"),
            ('right_bottom_y', "Right Bottom Y")
        ]
        for key, desc in crop_fields:
            val = params.get(key, '')
            if not val:
                missing_fields.append(desc)
            else:
                try:
                    int(val)
                except:
                    missing_fields.append(f"{desc} (정수 필요)")

        path_fields = ['source', 'target']
        invalid_paths = []
        for field in path_fields:
            path = params.get(field, '')
            if path and not os.path.isdir(path):
                invalid_paths.append(f"{field.capitalize()} Path이(가) 유효하지 않습니다.")

        if missing_fields or invalid_paths:
            warning_messages = []
            if missing_fields:
                warning_messages.append("다음 필드를 입력해야 합니다:")
                warning_messages.extend(missing_fields)
            if invalid_paths:
                warning_messages.append("다음 경로가 유효하지 않습니다:")
                warning_messages.extend(invalid_paths)
            QMessageBox.warning(self, "입력 오류", "\n".join(warning_messages))
            return False
        return True