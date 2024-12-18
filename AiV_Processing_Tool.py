import sys
import os
import shutil
import json
import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QFileDialog,
    QProgressBar, QMessageBox, QLabel, QHBoxLayout, QTextEdit,
    QDialog, QFormLayout, QLineEdit, QSpinBox, QCheckBox
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PIL import Image

logging.basicConfig(filename='error.log', level=logging.ERROR,
                    format='%(asctime)s:%(levelname)s:%(message)s')

class WorkerThread(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal(str)
    
    def __init__(self, task):
        super().__init__()
        self.task = task
        self._is_stopped = False

    def run(self):
        try:
            operation = self.task['operation']
            if operation == 'ng_sorting':
                self.ng_folder_sorting(self.task)
            elif operation == 'date_copy':
                self.date_based_copy(self.task)
            elif operation == 'image_copy':
                self.image_format_copy(self.task)
            elif operation == 'simulation_foldering':
                self.simulation_foldering(self.task)
            else:
                self.log.emit(f"알 수 없는 작업 유형: {operation}")
                self.finished.emit("알 수 없는 작업 유형.")
        except Exception as e:
            logging.error("작업 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중 오류 발생.")

    def stop(self):
        self._is_stopped = True

    def ng_folder_sorting(self, task):
        inputs = task['inputs']
        outputs = task['outputs']
        self.log.emit("NG Folder Sorting 작업 시작")
        total_tasks = len(inputs)
        for i, (inp, outp) in enumerate(zip(inputs, outputs), start=1):
            if self._is_stopped:
                self.log.emit("작업이 중지되었습니다.")
                self.finished.emit("작업 중지됨.")
                return
            self.log.emit(f"Processing {inp} -> {outp}")
            if not os.path.exists(inp):
                self.log.emit(f"Input 경로 존재하지 않음: {inp}")
                continue
            if not os.path.exists(outp):
                os.makedirs(outp, exist_ok=True)
            # 복사 작업
            try:
                for item in os.listdir(inp):
                    src_path = os.path.join(inp, item)
                    dst_path = os.path.join(outp, item)
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src_path, dst_path)
                self.log.emit(f"Copied {inp} to {outp}")
            except Exception as e:
                logging.error("NG Folder Sorting 중 오류", exc_info=True)
                self.log.emit(f"오류 발생: {str(e)}")
            progress_percent = int((i / total_tasks) * 100)
            self.progress.emit(progress_percent)
        self.finished.emit("NG Folder Sorting 완료.")

    def date_based_copy(self, task):
        source = task['source']
        target = task['target']
        year = task['year']
        month = task['month']
        day = task['day']
        hour = task['hour']
        minute = task['minute']
        second = task['second']
        count = task['count']
        self.log.emit("Date-Based Copy 작업 시작")
        if not os.path.exists(source):
            self.log.emit(f"Source 경로 존재하지 않음: {source}")
            self.finished.emit("작업 중지됨.")
            return
        # 특정 날짜 기준으로 폴더 찾기
        try:
            datetime_str = f"{year}{month:02d}{day:02d}{hour:02d}{minute:02d}{second:02d}"
            matching_folders = [f for f in os.listdir(source) if f.startswith(datetime_str)]
            self.log.emit(f"Found {len(matching_folders)} folders matching {datetime_str}")
            total_folders = min(len(matching_folders), count)
            for i, folder in enumerate(matching_folders[:total_folders], start=1):
                if self._is_stopped:
                    self.log.emit("작업이 중지되었습니다.")
                    self.finished.emit("작업 중지됨.")
                    return
                src_path = os.path.join(source, folder)
                dst_path = os.path.join(target, folder)
                if not os.path.exists(dst_path):
                    os.makedirs(dst_path, exist_ok=True)
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                self.log.emit(f"Copied {src_path} to {dst_path}")
                progress_percent = int((i / total_folders) * 100)
                self.progress.emit(progress_percent)
            self.finished.emit("Date-Based Copy 완료.")
        except Exception as e:
            logging.error("Date-Based Copy 중 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중지됨.")

    def image_format_copy(self, task):
        sources = task['sources']
        targets = task['targets']
        formats = task['formats']
        self.log.emit("Image Format Copy-Paste 작업 시작")
        total_tasks = len(sources)
        for i, (src, tgt) in enumerate(zip(sources, targets), start=1):
            if self._is_stopped:
                self.log.emit("작업이 중지되었습니다.")
                self.finished.emit("작업 중지됨.")
                return
            self.log.emit(f"Processing {src} -> {tgt}")
            if not os.path.exists(src):
                self.log.emit(f"Source 경로 존재하지 않음: {src}")
                continue
            if not os.path.exists(tgt):
                os.makedirs(tgt, exist_ok=True)
            try:
                image_files = [f for f in os.listdir(src) if any(f.lower().endswith(fmt.lower()) for fmt in formats)]
                total_files = len(image_files)
                if total_files == 0:
                    self.log.emit(f"No image files found in {src} with specified formats.")
                    continue
                for idx, file in enumerate(image_files, start=1):
                    if self._is_stopped:
                        self.log.emit("작업이 중지되었습니다.")
                        self.finished.emit("작업 중지됨.")
                        return
                    src_file = os.path.join(src, file)
                    dst_file = os.path.join(tgt, file)  # 원본 이름 그대로 복사
                    shutil.copy2(src_file, dst_file)
                    self.log.emit(f"Copied {src_file} to {dst_file}")
                    progress_percent = int((idx / total_files) * 100)
                    self.progress.emit(progress_percent)
            except Exception as e:
                logging.error("Image Format Copy-Paste 중 오류", exc_info=True)
                self.log.emit(f"오류 발생: {str(e)}")
            progress_percent = int((i / total_tasks) * 100)
            self.progress.emit(progress_percent)
        self.finished.emit("Image Format Copy-Paste 완료.")

    def simulation_foldering(self, task):
        source = task['source']
        target = task['target']
        formats = task['formats']
        self.log.emit("Simulation Foldering 작업 시작")
        if not os.path.exists(source):
            self.log.emit(f"Source 경로 존재하지 않음: {source}")
            self.finished.emit("작업 중지됨.")
            return
        if not os.path.exists(target):
            os.makedirs(target, exist_ok=True)
        try:
            files = [f for f in os.listdir(source) if any(f.lower().endswith(fmt.lower()) for fmt in formats)]
            total_files = len(files)
            for i, file in enumerate(files, start=1):
                if self._is_stopped:
                    self.log.emit("작업이 중지되었습니다.")
                    self.finished.emit("작업 중지됨.")
                    return
                parts = file.split('_')
                if len(parts) < 3:
                    self.log.emit(f"파일 이름 형식 오류: {file}")
                    continue
                folder_name = parts[0]
                new_file_name = '_'.join(parts[2:])  # 2_Socket_Top_Tilt.bmp
                folder_path = os.path.join(target, folder_name)
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path, exist_ok=True)
                src_file = os.path.join(source, file)
                dst_file = os.path.join(folder_path, new_file_name)
                shutil.copy2(src_file, dst_file)
                self.log.emit(f"Copied {src_file} to {dst_file}")
                progress_percent = int((i / total_files) * 100)
                self.progress.emit(progress_percent)
            self.finished.emit("Simulation Foldering 완료.")
        except Exception as e:
            logging.error("Simulation Foldering 중 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중지됨.")


class NGSortingDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NG Folder Sorting 설정")
        self.setFixedSize(600, 500)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        form_layout = QFormLayout()

        # Source Path 1
        self.source1_button = QPushButton("Select NG Folders")
        self.source1_button.clicked.connect(self.select_source1)
        self.source1_list = QListWidget()
        form_layout.addRow("Source Path #1 (NG Folders):", self.source1_button)
        form_layout.addRow("", self.source1_list)

        # Source Path 2
        self.source2_button = QPushButton("Select Matching Folders")
        self.source2_button.clicked.connect(self.select_source2)
        self.source2_list = QListWidget()
        form_layout.addRow("Source Path #2 (Matching Folders):", self.source2_button)
        form_layout.addRow("", self.source2_list)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        form_layout.addRow("Target Path:", self.target_button)
        form_layout.addRow("", self.target_path)

        layout.addLayout(form_layout)

        # Submit Button
        self.submit_button = QPushButton("Start NG Folder Sorting")
        self.submit_button.clicked.connect(self.accept)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

    def select_source1(self):
        # Allow multiple folder selection by selecting one, then repeatedly selecting more
        folder_paths = QFileDialog.getExistingDirectory(self, "Select NG Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if folder_paths:
            # Append to list
            item = QListWidgetItem(folder_paths)
            if not self.source1_list.findItems(folder_paths, Qt.MatchExactly):
                self.source1_list.addItem(item)

    def select_source2(self):
        folder_paths = QFileDialog.getExistingDirectory(self, "Select Matching Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if folder_paths:
            item = QListWidgetItem(folder_paths)
            if not self.source2_list.findItems(folder_paths, Qt.MatchExactly):
                self.source2_list.addItem(item)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def get_parameters(self):
        sources1 = [self.source1_list.item(i).text() for i in range(self.source1_list.count())]
        sources2 = [self.source2_list.item(i).text() for i in range(self.source2_list.count())]
        target = self.target_path.text()
        return {
            'operation': 'ng_sorting',
            'inputs': sources1,
            'outputs': sources2,
            'target': target
        }


class DateBasedCopyDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Date-Based Copy 설정")
        self.setFixedSize(500, 400)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Date and Time
        self.year_input = QSpinBox()
        self.year_input.setRange(1900, 2100)
        self.year_input.setValue(2024)
        self.month_input = QSpinBox()
        self.month_input.setRange(1, 12)
        self.month_input.setValue(1)
        self.day_input = QSpinBox()
        self.day_input.setRange(1, 31)
        self.day_input.setValue(1)
        self.hour_input = QSpinBox()
        self.hour_input.setRange(0, 23)
        self.hour_input.setValue(0)
        self.minute_input = QSpinBox()
        self.minute_input.setRange(0, 59)
        self.minute_input.setValue(0)
        self.second_input = QSpinBox()
        self.second_input.setRange(0, 59)
        self.second_input.setValue(0)

        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Year:"))
        date_layout.addWidget(self.year_input)
        date_layout.addWidget(QLabel("Month:"))
        date_layout.addWidget(self.month_input)
        date_layout.addWidget(QLabel("Day:"))
        date_layout.addWidget(self.day_input)
        date_layout.addWidget(QLabel("Hour:"))
        date_layout.addWidget(self.hour_input)
        date_layout.addWidget(QLabel("Minute:"))
        date_layout.addWidget(self.minute_input)
        date_layout.addWidget(QLabel("Second:"))
        date_layout.addWidget(self.second_input)
        form_layout.addRow("Date and Time:", date_layout)

        # Count
        self.count_input = QSpinBox()
        self.count_input.setRange(1, 1000)
        self.count_input.setValue(1)
        form_layout.addRow("Number of Folders to Copy:", self.count_input)

        # Source Path
        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        form_layout.addRow("Source Path:", self.source_button)
        form_layout.addRow("", self.source_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        form_layout.addRow("Target Path:", self.target_button)
        form_layout.addRow("", self.target_path)

        layout.addLayout(form_layout)

        # Submit Button
        self.submit_button = QPushButton("Start Date-Based Copy")
        self.submit_button.clicked.connect(self.accept)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def select_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if source:
            self.source_path.setText(source)

    def get_parameters(self):
        return {
            'operation': 'date_copy',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'year': self.year_input.value(),
            'month': self.month_input.value(),
            'day': self.day_input.value(),
            'hour': self.hour_input.value(),
            'minute': self.minute_input.value(),
            'second': self.second_input.value(),
            'count': self.count_input.value()
        }


class ImageFormatCopyDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Format Copy-Paste 설정")
        self.setFixedSize(600, 400)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Source Path
        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        form_layout.addRow("Source Path:", self.source_button)
        form_layout.addRow("", self.source_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        form_layout.addRow("Target Path:", self.target_button)
        form_layout.addRow("", self.target_path)

        # Image Formats
        self.format_bmp = QCheckBox("BMP")
        self.format_jpg = QCheckBox("JPG")
        self.format_mim = QCheckBox("MIM")
        self.format_png = QCheckBox("PNG")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_jpg)
        formats_layout.addWidget(self.format_mim)
        formats_layout.addWidget(self.format_png)
        form_layout.addRow("Image Formats:", formats_layout)

        layout.addLayout(form_layout)

        # Submit Button
        self.submit_button = QPushButton("Start Image Format Copy-Paste")
        self.submit_button.clicked.connect(self.accept)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

    def select_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if source:
            self.source_path.setText(source)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def get_parameters(self):
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_jpg.isChecked():
            formats.append(".jpg")
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


class SimulationFolderingDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulation Foldering 설정")
        self.setFixedSize(600, 400)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Source Path
        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        form_layout.addRow("Source Path:", self.source_button)
        form_layout.addRow("", self.source_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        form_layout.addRow("Target Path:", self.target_button)
        form_layout.addRow("", self.target_path)

        # Image Formats
        self.format_bmp = QCheckBox("BMP")
        self.format_jpg = QCheckBox("JPG")
        self.format_mim = QCheckBox("MIM")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_jpg)
        formats_layout.addWidget(self.format_mim)
        form_layout.addRow("Image Formats:", formats_layout)

        layout.addLayout(form_layout)

        # Submit Button
        self.submit_button = QPushButton("Start Simulation Foldering")
        self.submit_button.clicked.connect(self.accept)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

    def select_source(self):
        source = QFileDialog.getExistingDirectory(self, "Select Source Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if source:
            self.source_path.setText(source)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def get_parameters(self):
        formats = []
        if self.format_bmp.isChecked():
            formats.append(".bmp")
        if self.format_jpg.isChecked():
            formats.append(".jpg")
        if self.format_mim.isChecked():
            formats.append(".mim")
        return {
            'operation': 'simulation_foldering',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'formats': formats
        }


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AiV PROCESS TOOL")
        self.setWindowIcon(QIcon('./AiV.png'))
        self.setFixedSize(700, 600)
        self.initUI()
        self.worker = None

    def initUI(self):
        main_layout = QVBoxLayout()

        # Buttons for each functionality
        button_layout = QHBoxLayout()

        self.ng_sorting_button = QPushButton("NG Folder Sorting")
        self.ng_sorting_button.clicked.connect(self.open_ng_sorting)
        self.ng_sorting_button.setStyleSheet("background-color: #8B0000; color: white; padding: 10px;")
        button_layout.addWidget(self.ng_sorting_button)

        self.date_copy_button = QPushButton("Date-Based Copy")
        self.date_copy_button.clicked.connect(self.open_date_copy)
        self.date_copy_button.setStyleSheet("background-color: #8B0000; color: white; padding: 10px;")
        button_layout.addWidget(self.date_copy_button)

        self.image_copy_button = QPushButton("Image Format Copy-Paste")
        self.image_copy_button.clicked.connect(self.open_image_copy)
        self.image_copy_button.setStyleSheet("background-color: #8B0000; color: white; padding: 10px;")
        button_layout.addWidget(self.image_copy_button)

        self.simulation_button = QPushButton("Simulation Foldering")
        self.simulation_button.clicked.connect(self.open_simulation_foldering)
        self.simulation_button.setStyleSheet("background-color: #8B0000; color: white; padding: 10px;")
        button_layout.addWidget(self.simulation_button)

        main_layout.addLayout(button_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #8B0000;
                width: 20px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # Log Area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background-color: #F5F5F5;")
        main_layout.addWidget(QLabel("Logs:"))
        main_layout.addWidget(self.log_area)

        # Stop Button
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_task)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("background-color: #A9A9A9; color: white; padding: 10px;")
        main_layout.addWidget(self.stop_button)

        self.setLayout(main_layout)

    def open_ng_sorting(self):
        dialog = NGSortingDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            self.start_task(params)

    def open_date_copy(self):
        dialog = DateBasedCopyDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            self.start_task(params)

    def open_image_copy(self):
        dialog = ImageFormatCopyDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            self.start_task(params)

    def open_simulation_foldering(self):
        dialog = SimulationFolderingDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            self.start_task(params)

    def start_task(self, params):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "작업 중", "이미 작업이 진행 중입니다.")
            return
        self.log_area.clear()
        self.progress_bar.setValue(0)
        self.worker = WorkerThread(params)
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.task_finished)
        self.worker.start()
        self.stop_button.setEnabled(True)
        self.append_log("작업이 시작되었습니다.")

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def append_log(self, message):
        self.log_area.append(message)

    def task_finished(self, message):
        self.append_log(message)
        self.stop_button.setEnabled(False)
        QMessageBox.information(self, "완료", message)
        if "완료" in message or "오류" in message or "중지" in message:
            self.close_program()

    def stop_task(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.append_log("Stop 신호를 보냈습니다.")
            self.stop_button.setEnabled(False)

    def close_program(self):
        # 사용자 확인 후 프로그램 종료
        reply = QMessageBox.question(self, '프로그램 종료', '프로그램을 종료하시겠습니까?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            QApplication.instance().quit()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Palette 설정을 통해 다크 레드, 회색, 흰색 사용
    palette = app.palette()
    palette.setColor(palette.Window, Qt.white)
    palette.setColor(palette.Button, Qt.darkGray)
    palette.setColor(palette.ButtonText, Qt.white)
    palette.setColor(palette.Base, Qt.white)
    palette.setColor(palette.Text, Qt.black)
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
