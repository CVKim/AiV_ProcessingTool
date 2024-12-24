import sys
import os
import shutil
import json
import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QFileDialog,
    QProgressBar, QMessageBox, QLabel, QHBoxLayout, QTextEdit,
    QDialog, QFormLayout, QLineEdit, QSpinBox, QCheckBox, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QGridLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from datetime import datetime

# 로깅 설정
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
            elif operation == 'ng_count':
                self.ng_count(self.task)
            elif operation == 'basic_sorting':
                self.basic_sorting(self.task)
            elif operation == 'crop':
                self.crop_images(self.task)
            elif operation == 'resize':
                self.resize_images(self.task)
            elif operation == 'flip':
                self.flip_images(self.task)
            elif operation == 'rotate':
                self.rotate_images(self.task)
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
        # 기존 NG Folder Sorting 기능 유지
        inputs = task['inputs']  # List of selected subfolders (full paths)
        source2 = task['source2']  # Single source path #2 folder
        target = task['target']
        self.log.emit("NG Folder Sorting 작업 시작")
        total_tasks = len(inputs)
        total_processed = 0  # 총 복사한 폴더 수
        for i, src_folder in enumerate(inputs, start=1):
            if self._is_stopped:
                self.log.emit("작업이 중지되었습니다.")
                self.finished.emit(f"작업 중지됨. 총 복사한 폴더: {total_processed}")
                return
            folder_name = os.path.basename(src_folder)
            self.log.emit(f"Processing folder name: {folder_name}")
            # 소스 경로 #2에서 동일한 폴더 이름을 가진 폴더 찾기 (NG, OK 제외)
            try:
                if not os.path.exists(source2):
                    self.log.emit(f"Source Path #2 경로 존재하지 않음: {source2}")
                    continue
                matching_folders = [f for f in os.listdir(source2) 
                                    if f == folder_name and 
                                    f not in ['NG', 'OK'] and 
                                    os.path.isdir(os.path.join(source2, f))]
                if not matching_folders:
                    self.log.emit(f"No matching folder named '{folder_name}' found in Source Path #2.")
                    continue
                for match_folder in matching_folders:
                    src_path = os.path.join(source2, match_folder)
                    dst_path = os.path.join(target, match_folder)
                    if not os.path.exists(dst_path):
                        os.makedirs(dst_path, exist_ok=True)
                    shutil.copytree(src_path, dst_path, dirs_exist_ok=True)  # 덮어쓰기
                    self.log.emit(f"Copied {src_path} to {dst_path}")
                    total_processed += 1
            except Exception as e:
                logging.error("NG Folder Sorting 중 오류", exc_info=True)
                self.log.emit(f"오류 발생: {str(e)}")
            progress_percent = int((i / total_tasks) * 100)
            self.progress.emit(progress_percent)
        self.finished.emit(f"NG Folder Sorting 완료. 총 복사한 폴더: {total_processed}")

    def date_based_copy(self, task):
        # 기존 Date-Based Copy 기능 유지
        source = task['source']
        target = task['target']
        year = task['year']
        month = task['month']
        day = task['day']
        hour = task['hour']
        minute = task['minute']
        second = task['second']
        count = task['count']
        formats = task['formats']  # 이미지 포맷 필터링
        self.log.emit("Date-Based Copy 작업 시작")
        if not os.path.exists(source):
            self.log.emit(f"Source 경로 존재하지 않음: {source}")
            self.finished.emit("작업 중지됨.")
            return
        # 설정한 날짜 이후에 수정된 파일 찾기
        try:
            # 사용자 설정 날짜와 시간
            specified_datetime = datetime(year, month, day, hour, minute, second)
            specified_timestamp = specified_datetime.timestamp()

            # 소스 디렉토리 내의 파일 리스트
            all_files = [f for f in os.listdir(source) if os.path.isfile(os.path.join(source, f))]

            # 파일의 수정 시간을 기준으로 필터링
            matching_files = []
            for file in all_files:
                file_path = os.path.join(source, file)
                file_mtime = os.path.getmtime(file_path)
                if file_mtime > specified_timestamp:
                    if any(file.lower().endswith(fmt.lower()) for fmt in formats):
                        matching_files.append((file, file_mtime))

            # 수정 시간 기준으로 정렬 (오래된 순)
            matching_files.sort(key=lambda x: x[1])

            self.log.emit(f"Found {len(matching_files)} files modified after {specified_datetime} with specified formats")

            # 지정한 개수만큼 선택
            selected_files = [file for file, mtime in matching_files[:count]]
            total_files = len(selected_files)

            for i, file in enumerate(selected_files, start=1):
                if self._is_stopped:
                    self.log.emit(f"작업이 중지되었습니다. 총 처리한 파일: {i-1}")
                    self.finished.emit(f"작업 중지됨. 총 처리한 파일: {i-1}")
                    return
                src_path = os.path.join(source, file)
                dst_path = os.path.join(target, file)
                if not os.path.exists(target):
                    os.makedirs(target, exist_ok=True)
                try:
                    shutil.copy2(src_path, dst_path)  # 덮어쓰기 기본 동작
                    self.log.emit(f"Copied {src_path} to {dst_path}")
                except Exception as e:
                    logging.error("Date-Based Copy 중 오류", exc_info=True)
                    self.log.emit(f"오류 발생: {str(e)}")
                progress_percent = int((i / total_files) * 100)
                self.progress.emit(progress_percent)
            self.finished.emit("Date-Based Copy 완료.")
        except Exception as e:
            logging.error("Date-Based Copy 중 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중지됨.")

    def image_format_copy(self, task):
        # 기존 Image Format Copy 기능 유지
        sources = task['sources']
        targets = task['targets']
        formats = task['formats']
        self.log.emit("Image Format Copy 작업 시작")
        total_tasks = len(sources)
        total_processed = 0  # 총 처리한 파일 수
        for i, (src, tgt) in enumerate(zip(sources, targets), start=1):
            if self._is_stopped:
                self.log.emit(f"작업이 중지되었습니다. 총 처리한 파일: {total_processed}")
                self.finished.emit(f"작업 중지됨. 총 처리한 파일: {total_processed}")
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
                        self.log.emit(f"작업이 중지되었습니다. 총 처리한 파일: {total_processed}")
                        self.finished.emit(f"작업 중지됨. 총 처리한 파일: {total_processed}")
                        return
                    src_file = os.path.join(src, file)
                    dst_file = os.path.join(tgt, file)  # 원본 이름 그대로 복사
                    try:
                        shutil.copy2(src_file, dst_file)  # 덮어쓰기 기본 동작
                        self.log.emit(f"Copied {src_file} to {dst_file}")
                        total_processed += 1
                    except Exception as e:
                        logging.error("Image Format Copy 중 오류", exc_info=True)
                        self.log.emit(f"오류 발생: {str(e)}")
                    progress_percent = int((idx / total_files) * 100)
                    self.progress.emit(progress_percent)
            except Exception as e:
                logging.error("Image Format Copy 중 오류", exc_info=True)
                self.log.emit(f"오류 발생: {str(e)}")
            progress_percent = int((i / total_tasks) * 100)
            self.progress.emit(progress_percent)
        self.log.emit(f"Image Format Copy 완료. 총 처리한 파일: {total_processed}")
        self.finished.emit(f"Image Format Copy 완료. 총 처리한 파일: {total_processed}")

    def simulation_foldering(self, task):
        # 기존 Simulation Foldering 기능 유지
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
            total_processed = 0  # 총 처리한 파일 수
            for i, file in enumerate(files, start=1):
                if self._is_stopped:
                    self.log.emit(f"작업이 중지되었습니다. 총 처리한 파일: {total_processed}")
                    self.finished.emit(f"작업 중지됨. 총 처리한 파일: {total_processed}")
                    return
                parts = file.split('_')
                if len(parts) < 3:
                    self.log.emit(f"파일 이름 형식 오류: {file}")
                    continue
                folder_name = parts[0]
                new_file_name = '_'.join(parts[2:])  # 예: 2_Socket_Top_Tilt.bmp
                folder_path = os.path.join(target, folder_name)
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path, exist_ok=True)
                src_file = os.path.join(source, file)
                dst_file = os.path.join(folder_path, new_file_name)
                try:
                    shutil.copy2(src_file, dst_file)
                    self.log.emit(f"Copied {src_file} to {dst_file}")
                    total_processed += 1
                except Exception as e:
                    logging.error("Simulation Foldering 중 오류", exc_info=True)
                    self.log.emit(f"오류 발생: {str(e)}")
                progress_percent = int((i / total_files) * 100)
                self.progress.emit(progress_percent)
            self.log.emit(f"Simulation Foldering 완료. 총 처리한 파일: {total_processed}")
            self.finished.emit(f"Simulation Foldering 완료. 총 처리한 파일: {total_processed}")
        except Exception as e:
            logging.error("Simulation Foldering 중 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중지됨.")

    def ng_count(self, task):
        # 기존 NG Count 기능 유지
        ng_folder = task['ng_folder']
        self.log.emit("NG Count 작업 시작")
        if not os.path.exists(ng_folder):
            self.log.emit(f"Selected NG folder does not exist: {ng_folder}")
            self.finished.emit("작업 중지됨.")
            return
        try:
            # 선택한 NG 폴더 내의 모든 폴더 리스트
            all_subfolders = [f for f in os.listdir(ng_folder) if os.path.isdir(os.path.join(ng_folder, f))]

            # 'Cam_'으로 시작하는 폴더만 필터링
            cam_folders = [f for f in all_subfolders if f.startswith('Cam_')]

            if not cam_folders:
                self.log.emit("No 'Cam_' prefixed folders found in the selected NG folder.")
                self.finished.emit("NG Count 완료.")
                return

            self.log.emit(f"Counting - Select ng folder : {ng_folder}")

            for cam in cam_folders:
                cam_path = os.path.join(ng_folder, cam)
                # cam_path 내의 이너 폴더 리스트
                inner_folders = [f for f in os.listdir(cam_path) if os.path.isdir(os.path.join(cam_path, f))]
                for inner in inner_folders:
                    inner_path = os.path.join(cam_path, inner)
                    # inner_path 내의 폴더 수 카운팅
                    count = len([f for f in os.listdir(inner_path) if os.path.isdir(os.path.join(inner_path, f))])
                    # CamX - InnerFolder : count개 형식으로 로그 출력
                    self.log.emit(f"{cam} - {inner} : {count}개")
            self.finished.emit("NG Count 완료.")
        except Exception as e:
            logging.error("NG Count 중 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중지됨.")

    # 새로운 기능을 위한 메서드들 (기능 구현 필요)
    def basic_sorting(self, task):
        self.log.emit("Basic Sorting 작업 시작")
        # 기능 구현 필요
        try:
            # 예시: Basic Sorting 로직을 여기에 구현
            self.log.emit("Basic Sorting 기능이 아직 구현되지 않았습니다.")
            self.finished.emit("Basic Sorting 완료.")
        except Exception as e:
            logging.error("Basic Sorting 중 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중지됨.")

    def crop_images(self, task):
        self.log.emit("Crop 작업 시작")
        # 기능 구현 필요
        try:
            # 예시: Crop 로직을 여기에 구현
            self.log.emit("Crop 기능이 아직 구현되지 않았습니다.")
            self.finished.emit("Crop 완료.")
        except Exception as e:
            logging.error("Crop 중 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중지됨.")

    def resize_images(self, task):
        self.log.emit("Resize 작업 시작")
        # 기능 구현 필요
        try:
            # 예시: Resize 로직을 여기에 구현
            self.log.emit("Resize 기능이 아직 구현되지 않았습니다.")
            self.finished.emit("Resize 완료.")
        except Exception as e:
            logging.error("Resize 중 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중지됨.")

    def flip_images(self, task):
        self.log.emit("FLIP 작업 시작")
        # 기능 구현 필요
        try:
            # 예시: FLIP 로직을 여기에 구현
            self.log.emit("FLIP 기능이 아직 구현되지 않았습니다.")
            self.finished.emit("FLIP 완료.")
        except Exception as e:
            logging.error("FLIP 중 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중지됨.")

    def rotate_images(self, task):
        self.log.emit("Rotate 작업 시작")
        # 기능 구현 필요
        try:
            # 예시: Rotate 로직을 여기에 구현
            self.log.emit("Rotate 기능이 아직 구현되지 않았습니다.")
            self.finished.emit("Rotate 완료.")
        except Exception as e:
            logging.error("Rotate 중 오류", exc_info=True)
            self.log.emit(f"오류 발생: {str(e)}")
            self.finished.emit("작업 중지됨.")


class NGSortingDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NG Folder Sorting 설정")
        self.setFixedSize(800, 700)  # 크기 확장
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        form_layout = QFormLayout()

        # Source Path 1
        self.add_source_button = QPushButton("Add NG Folder")
        self.add_source_button.clicked.connect(self.add_source_folder)
        self.source1_list = QListWidget()
        self.source1_list.setSelectionMode(QListWidget.ExtendedSelection)
        form_layout.addRow(QLabel("<b>Source Path #1 (NG Folders):</b>"), self.add_source_button)
        form_layout.addRow("", self.source1_list)

        # Remove Selected Folder Button
        self.remove_source_button = QPushButton("Remove Selected Folder")
        self.remove_source_button.clicked.connect(self.remove_selected_source_folder)
        form_layout.addRow("", self.remove_source_button)

        # Source Path 2
        self.source2_button = QPushButton("Select Matching Folder")
        self.source2_button.clicked.connect(self.select_source2)
        self.source2_path = QLineEdit()
        self.source2_path.setReadOnly(True)
        form_layout.addRow(QLabel("<b>Source Path #2 (Matching Folder):</b>"), self.source2_button)
        form_layout.addRow("", self.source2_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        form_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        form_layout.addRow("", self.target_path)

        layout.addLayout(form_layout)

        # Submit Button
        self.submit_button = QPushButton("Start NG Folder Sorting")
        self.submit_button.clicked.connect(self.accept)
        self.submit_button.setStyleSheet("background-color: #8B0000; color: white; padding: 15px; font-size: 14px; border-radius: 5px;")
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

    def add_source_folder(self):
        parent_folder = QFileDialog.getExistingDirectory(self, "Select Parent Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if parent_folder:
            # 소스 폴더 내의 모든 서브 폴더(OK, NG 제외) 가져오기
            try:
                subfolders = [f for f in os.listdir(parent_folder) 
                              if os.path.isdir(os.path.join(parent_folder, f)) 
                              and f not in ['OK', 'NG']]
                if not subfolders:
                    QMessageBox.information(self, "정보", "선택한 폴더 내에 서브 폴더가 없습니다.")
                    return
            except Exception as e:
                logging.error("서브 폴더 목록 가져오기 중 오류", exc_info=True)
                QMessageBox.warning(self, "오류", f"서브 폴더 목록 가져오기 중 오류가 발생했습니다:\n{str(e)}")
                return

            # 서브 폴더 선택 다이얼로그 열기
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
                    # 중복된 폴더는 추가하지 않음
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
        folder = QFileDialog.getExistingDirectory(self, "Select Matching Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if folder:
            self.source2_path.setText(folder)

    def select_target(self):
        target = QFileDialog.getExistingDirectory(self, "Select Target Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if target:
            self.target_path.setText(target)

    def get_parameters(self):
        sources1 = [self.source1_list.item(i).text() for i in range(self.source1_list.count())]
        source2 = self.source2_path.text()
        target = self.target_path.text()
        return {
            'operation': 'ng_sorting',
            'inputs': sources1,
            'source2': source2,
            'target': target
        }


class DateBasedCopyDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Date-Based Copy 설정")
        self.setFixedSize(800, 700)  # 크기 확장
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        current_time = datetime.now()
        year, month, day = current_time.year, current_time.month, current_time.day
        hour, minute, second = current_time.hour, current_time.minute, current_time.second

        # Date and Time (확장된 레이아웃)
        self.year_input = QSpinBox()
        self.year_input.setRange(2020, 2030)
        self.year_input.setValue(year)
        self.month_input = QSpinBox()
        self.month_input.setRange(1, 12)
        self.month_input.setValue(month)
        self.day_input = QSpinBox()
        self.day_input.setRange(1, 31)
        self.day_input.setValue(day)
        self.hour_input = QSpinBox()
        self.hour_input.setRange(0, 23)
        self.hour_input.setValue(hour)
        self.minute_input = QSpinBox()
        self.minute_input.setRange(0, 59)
        self.minute_input.setValue(minute)
        self.second_input = QSpinBox()
        self.second_input.setRange(0, 59)
        self.second_input.setValue(second)

        # 날짜 입력 레이아웃
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Year:"))
        date_layout.addWidget(self.year_input)
        date_layout.addWidget(QLabel("Month:"))
        date_layout.addWidget(self.month_input)
        date_layout.addWidget(QLabel("Day:"))
        date_layout.addWidget(self.day_input)
        form_layout.addRow(QLabel("<b>Date:</b>"), date_layout)

        # 시간 입력 레이아웃
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Hour:"))
        time_layout.addWidget(self.hour_input)
        time_layout.addWidget(QLabel("Minute:"))
        time_layout.addWidget(self.minute_input)
        time_layout.addWidget(QLabel("Second:"))
        time_layout.addWidget(self.second_input)
        form_layout.addRow(QLabel("<b>Time:</b>"), time_layout)

        # Count
        self.count_input = QSpinBox()
        self.count_input.setRange(1, 1000)
        self.count_input.setValue(1)
        form_layout.addRow(QLabel("<b>Number of Files to Copy:</b>"), self.count_input)

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
        form_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)

        # Source Path
        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        form_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        form_layout.addRow("", self.source_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        form_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        form_layout.addRow("", self.target_path)

        layout.addLayout(form_layout)

        # Submit Button
        self.submit_button = QPushButton("Start Date-Based Copy")
        self.submit_button.clicked.connect(self.accept)
        self.submit_button.setStyleSheet("background-color: #8B0000; color: white; padding: 15px; font-size: 14px; border-radius: 5px;")
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
        # 이미지 포맷 필터링
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
            'operation': 'date_copy',
            'source': self.source_path.text(),
            'target': self.target_path.text(),
            'year': self.year_input.value(),
            'month': self.month_input.value(),
            'day': self.day_input.value(),
            'hour': self.hour_input.value(),
            'minute': self.minute_input.value(),
            'second': self.second_input.value(),
            'count': self.count_input.value(),
            'formats': formats  # 이미지 포맷 필터링
        }


class ImageFormatCopyDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Format Copy 설정")
        self.setFixedSize(800, 700)  # 크기 확장
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Source Path
        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        form_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        form_layout.addRow("", self.source_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        form_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
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
        form_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)

        layout.addLayout(form_layout)

        # Submit Button
        self.submit_button = QPushButton("Start Image Format Copy")
        self.submit_button.clicked.connect(self.accept)
        self.submit_button.setStyleSheet("background-color: #8B0000; color: white; padding: 15px; font-size: 14px; border-radius: 5px;")
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
        self.setFixedSize(800, 700)  # 크기 확장
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Source Path
        self.source_button = QPushButton("Select Source Path")
        self.source_button.clicked.connect(self.select_source)
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        form_layout.addRow(QLabel("<b>Source Path:</b>"), self.source_button)
        form_layout.addRow("", self.source_path)

        # Target Path
        self.target_button = QPushButton("Select Target Path")
        self.target_button.clicked.connect(self.select_target)
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        form_layout.addRow(QLabel("<b>Target Path:</b>"), self.target_button)
        form_layout.addRow("", self.target_path)

        # Image Formats
        self.format_bmp = QCheckBox("BMP")
        self.format_jpg = QCheckBox("JPG")
        self.format_mim = QCheckBox("MIM")
        formats_layout = QHBoxLayout()
        formats_layout.addWidget(self.format_bmp)
        formats_layout.addWidget(self.format_jpg)
        formats_layout.addWidget(self.format_mim)
        form_layout.addRow(QLabel("<b>Image Formats:</b>"), formats_layout)

        layout.addLayout(form_layout)

        # Submit Button
        self.submit_button = QPushButton("Start Simulation Foldering")
        self.submit_button.clicked.connect(self.accept)
        self.submit_button.setStyleSheet("background-color: #8B0000; color: white; padding: 15px; font-size: 14px; border-radius: 5px;")
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


class NGCountDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NG Count 설정")
        self.setFixedSize(800, 700)  # 크기 확장
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # NG Folder Path
        self.ng_folder_button = QPushButton("Select NG Folder")
        self.ng_folder_button.clicked.connect(self.select_ng_folder)
        self.ng_folder_path = QLineEdit()
        self.ng_folder_path.setReadOnly(True)
        form_layout.addRow(QLabel("<b>Counting - Select NG folder:</b>"), self.ng_folder_button)
        form_layout.addRow("", self.ng_folder_path)

        # Submit Button
        self.submit_button = QPushButton("Start NG Count")
        self.submit_button.clicked.connect(self.accept)
        self.submit_button.setStyleSheet("background-color: #8B0000; color: white; padding: 15px; font-size: 14px; border-radius: 5px;")
        form_layout.addRow("", self.submit_button)

        layout.addLayout(form_layout)

        self.setLayout(layout)

    def select_ng_folder(self):
        ng_folder = QFileDialog.getExistingDirectory(self, "Select NG Folder", "", QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        if ng_folder:
            self.ng_folder_path.setText(ng_folder)

    def get_parameters(self):
        return {
            'operation': 'ng_count',
            'ng_folder': self.ng_folder_path.text()
        }


# 새로운 기능을 위한 Dialog 클래스 추가
class BasicSortingDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Basic Sorting 설정")
        self.setFixedSize(800, 700)  # 크기 확장
        self.initUI()

    def initUI(self):
        # 기능 구현 필요
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Basic Sorting 기능을 설정하세요."))
        # 추가 설정 요소들을 여기에 구현
        self.submit_button = QPushButton("Start Basic Sorting")
        self.submit_button.clicked.connect(self.accept)
        self.submit_button.setStyleSheet("background-color: #8B0000; color: white; padding: 15px; font-size: 14px; border-radius: 5px;")
        layout.addWidget(self.submit_button)
        self.setLayout(layout)

    def get_parameters(self):
        # 설정된 파라미터 반환
        return {
            'operation': 'basic_sorting',
            # 추가 파라미터들
        }


class CropDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Crop 설정")
        self.setFixedSize(800, 700)  # 크기 확장
        self.initUI()

    def initUI(self):
        # 기능 구현 필요
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Crop 기능을 설정하세요."))
        # 추가 설정 요소들을 여기에 구현
        self.submit_button = QPushButton("Start Crop")
        self.submit_button.clicked.connect(self.accept)
        self.submit_button.setStyleSheet("background-color: #8B0000; color: white; padding: 15px; font-size: 14px; border-radius: 5px;")
        layout.addWidget(self.submit_button)
        self.setLayout(layout)

    def get_parameters(self):
        # 설정된 파라미터 반환
        return {
            'operation': 'crop',
            # 추가 파라미터들
        }


class ResizeDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Resize 설정")
        self.setFixedSize(800, 700)  # 크기 확장
        self.initUI()

    def initUI(self):
        # 기능 구현 필요
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Resize 기능을 설정하세요."))
        # 추가 설정 요소들을 여기에 구현
        self.submit_button = QPushButton("Start Resize")
        self.submit_button.clicked.connect(self.accept)
        self.submit_button.setStyleSheet("background-color: #8B0000; color: white; padding: 15px; font-size: 14px; border-radius: 5px;")
        layout.addWidget(self.submit_button)
        self.setLayout(layout)

    def get_parameters(self):
        # 설정된 파라미터 반환
        return {
            'operation': 'resize',
            # 추가 파라미터들
        }


class FlipDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FLIP 설정")
        self.setFixedSize(800, 700)  # 크기 확장
        self.initUI()

    def initUI(self):
        # 기능 구현 필요
        layout = QVBoxLayout()
        layout.addWidget(QLabel("FLIP 기능을 설정하세요."))
        # 추가 설정 요소들을 여기에 구현
        self.submit_button = QPushButton("Start FLIP")
        self.submit_button.clicked.connect(self.accept)
        self.submit_button.setStyleSheet("background-color: #8B0000; color: white; padding: 15px; font-size: 14px; border-radius: 5px;")
        layout.addWidget(self.submit_button)
        self.setLayout(layout)

    def get_parameters(self):
        # 설정된 파라미터 반환
        return {
            'operation': 'flip',
            # 추가 파라미터들
        }


class RotateDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rotate 설정")
        self.setFixedSize(800, 700)  # 크기 확장
        self.initUI()

    def initUI(self):
        # 기능 구현 필요
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Rotate 기능을 설정하세요."))
        # 추가 설정 요소들을 여기에 구현
        self.submit_button = QPushButton("Start Rotate")
        self.submit_button.clicked.connect(self.accept)
        self.submit_button.setStyleSheet("background-color: #8B0000; color: white; padding: 15px; font-size: 14px; border-radius: 5px;")
        layout.addWidget(self.submit_button)
        self.setLayout(layout)

    def get_parameters(self):
        # 설정된 파라미터 반환
        return {
            'operation': 'rotate',
            # 추가 파라미터들
        }


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Processor")
        self.setWindowIcon(QIcon('./AiV.png'))  # 아이콘 유지
        self.setFixedSize(1000, 800)  # 약간 넓혀서 버튼들이 작아질 여유를 줌
        self.initUI()
        self.worker = None

    def initUI(self):
        main_layout = QVBoxLayout()

        # Buttons for each functionality in 2 rows of 5
        button_layout = QGridLayout()
        button_layout.setSpacing(20)  # 버튼 간 간격 설정

        # First Row Buttons
        self.ng_sorting_button = QPushButton("NG Folder Sorting")
        self.ng_sorting_button.clicked.connect(self.open_ng_sorting)
        self.ng_sorting_button.setFixedSize(150, 80)
        self.ng_sorting_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-size: 14px;
                border: 2px solid black;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #A52A2A;
            }
        """)
        button_layout.addWidget(self.ng_sorting_button, 0, 0)

        self.date_copy_button = QPushButton("Date-Based Copy")
        self.date_copy_button.clicked.connect(self.open_date_copy)
        self.date_copy_button.setFixedSize(150, 80)
        self.date_copy_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-size: 14px;
                border: 2px solid black;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #A52A2A;
            }
        """)
        button_layout.addWidget(self.date_copy_button, 0, 1)

        self.image_copy_button = QPushButton("Image Format Copy")
        self.image_copy_button.clicked.connect(self.open_image_copy)
        self.image_copy_button.setFixedSize(150, 80)
        self.image_copy_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-size: 14px;
                border: 2px solid black;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #A52A2A;
            }
        """)
        button_layout.addWidget(self.image_copy_button, 0, 2)

        self.basic_sorting_button = QPushButton("Basic Sorting")
        self.basic_sorting_button.clicked.connect(self.open_basic_sorting)
        self.basic_sorting_button.setFixedSize(150, 80)
        self.basic_sorting_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-size: 14px;
                border: 2px solid black;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #A52A2A;
            }
        """)
        button_layout.addWidget(self.basic_sorting_button, 0, 3)

        self.ng_count_button = QPushButton("NG Count")
        self.ng_count_button.clicked.connect(self.open_ng_count)
        self.ng_count_button.setFixedSize(150, 80)
        self.ng_count_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-size: 14px;
                border: 2px solid black;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #A52A2A;
            }
        """)
        button_layout.addWidget(self.ng_count_button, 0, 4)

        # Second Row Buttons
        self.simulation_button = QPushButton("Simulation Foldering")
        self.simulation_button.clicked.connect(self.open_simulation_foldering)
        self.simulation_button.setFixedSize(150, 80)
        self.simulation_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-size: 14px;
                border: 2px solid black;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #A52A2A;
            }
        """)
        button_layout.addWidget(self.simulation_button, 1, 0)

        self.crop_button = QPushButton("Crop")
        self.crop_button.clicked.connect(self.open_crop)
        self.crop_button.setFixedSize(150, 80)
        self.crop_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-size: 14px;
                border: 2px solid black;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #A52A2A;
            }
        """)
        button_layout.addWidget(self.crop_button, 1, 1)

        self.resize_button = QPushButton("Resize")
        self.resize_button.clicked.connect(self.open_resize)
        self.resize_button.setFixedSize(150, 80)
        self.resize_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-size: 14px;
                border: 2px solid black;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #A52A2A;
            }
        """)
        button_layout.addWidget(self.resize_button, 1, 2)

        self.flip_button = QPushButton("FLIP")
        self.flip_button.clicked.connect(self.open_flip)
        self.flip_button.setFixedSize(150, 80)
        self.flip_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-size: 14px;
                border: 2px solid black;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #A52A2A;
            }
        """)
        button_layout.addWidget(self.flip_button, 1, 3)

        self.rotate_button = QPushButton("Rotate")
        self.rotate_button.clicked.connect(self.open_rotate)
        self.rotate_button.setFixedSize(150, 80)
        self.rotate_button.setStyleSheet("""
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-size: 14px;
                border: 2px solid black;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #A52A2A;
            }
        """)
        button_layout.addWidget(self.rotate_button, 1, 4)

        main_layout.addLayout(button_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
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
        main_layout.addWidget(self.progress_bar)

        # Log Area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #F5F5F5;
                font-family: Consolas;
                font-size: 14px;
                padding: 10px;
                border: 1px solid #CCC;
                border-radius: 5px;
            }
        """)
        main_layout.addWidget(QLabel("<b>Logs:</b>"))
        main_layout.addWidget(self.log_area)

        # Stop Button
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_task)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #A9A9A9;
                color: white;
                padding: 15px;
                font-size: 16px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #696969;
            }
        """)
        main_layout.addWidget(self.stop_button)

        self.setLayout(main_layout)

    # 기존 기능에 대한 열기 메서드 유지
    def open_ng_sorting(self):
        dialog = NGSortingDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            # 유효성 검사
            if not params['inputs']:
                QMessageBox.warning(self, "입력 오류", "Source Path #1에 최소 하나의 폴더를 추가해야 합니다.")
                return
            if not params['source2']:
                QMessageBox.warning(self, "입력 오류", "Source Path #2를 선택해야 합니다.")
                return
            if not params['target']:
                QMessageBox.warning(self, "입력 오류", "Target Path를 선택해야 합니다.")
                return
            self.start_task(params)

    def open_ng_count(self):
        dialog = NGCountDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            # 유효성 검사
            if not params['ng_folder']:
                QMessageBox.warning(self, "입력 오류", "NG 폴더를 선택해야 합니다.")
                return
            self.start_task(params)

    def open_date_copy(self):
        dialog = DateBasedCopyDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            # 유효성 검사
            if not params['source']:
                QMessageBox.warning(self, "입력 오류", "Source Path를 선택해야 합니다.")
                return
            if not params['target']:
                QMessageBox.warning(self, "입력 오류", "Target Path를 선택해야 합니다.")
                return
            if not params['formats']:
                QMessageBox.warning(self, "입력 오류", "적어도 하나의 이미지 포맷을 선택해야 합니다.")
                return
            self.start_task(params)

    def open_image_copy(self):
        dialog = ImageFormatCopyDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            # 유효성 검사
            if not params['sources'][0]:
                QMessageBox.warning(self, "입력 오류", "Source Path를 선택해야 합니다.")
                return
            if not params['targets'][0]:
                QMessageBox.warning(self, "입력 오류", "Target Path를 선택해야 합니다.")
                return
            if not params['formats']:
                QMessageBox.warning(self, "입력 오류", "적어도 하나의 이미지 포맷을 선택해야 합니다.")
                return
            self.start_task(params)

    def open_simulation_foldering(self):
        dialog = SimulationFolderingDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            # 유효성 검사
            if not params['source']:
                QMessageBox.warning(self, "입력 오류", "Source Path를 선택해야 합니다.")
                return
            if not params['target']:
                QMessageBox.warning(self, "입력 오류", "Target Path를 선택해야 합니다.")
                return
            if not params['formats']:
                QMessageBox.warning(self, "입력 오류", "적어도 하나의 이미지 포맷을 선택해야 합니다.")
                return
            self.start_task(params)

    # 새로운 기능에 대한 열기 메서드 추가
    def open_basic_sorting(self):
        dialog = BasicSortingDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            self.start_task(params)

    def open_crop(self):
        dialog = CropDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            self.start_task(params)

    def open_resize(self):
        dialog = ResizeDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            self.start_task(params)

    def open_flip(self):
        dialog = FlipDialog()
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.get_parameters()
            self.start_task(params)

    def open_rotate(self):
        dialog = RotateDialog()
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
