import sys
import os
import shutil
from datetime import datetime
import configparser

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLineEdit, QTextEdit, QLabel,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QGroupBox, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

class DLModelCleaner(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DLMODEL 파일 정리기")
        self.setGeometry(100, 100, 1000, 700)

        # 아이콘 설정
        self.set_app_icon()

        # 초기 변수 설정
        self.file_names = []
        self.valid_extensions = [".trt", ".onnx"]
        self.target_folder = ""
        self.ini_path = ""

        # 카운터 초기화
        self.retained_count = 0
        self.moved_count = 0

        # 백업 폴더 패턴
        self.backup_folder_prefix = "back_dlmode_"
        self.backup_folder = ""

        # 모델 이름과 'name' 키를 매핑할 딕셔너리
        self.name_mapping = {}

        # UI 설정
        self.setup_ui()

    def set_app_icon(self):
        if getattr(sys, 'frozen', False):
            # 실행 파일로 패키징된 경우 (PyInstaller)
            application_path = sys._MEIPASS
        else:
            # 개발 중인 경우
            application_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(application_path, 'AiV_LOGO.ico')  # 'AiV_LOGO.ico'로 변경
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(QIcon())  # 기본 아이콘 설정

    def setup_ui(self):
        # 전체 레이아웃
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # 스타일 설정
        self.setStyleSheet("""
            QWidget {
                background-color: #2E2E2E;
                color: white;
                font-family: Arial, sans-serif;
                font-size: 14px;
            }
            QPushButton {
                background-color: #8B0000; /* 다크 레드 */
                border: none;
                color: white;
                padding: 10px 20px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 14px;
                margin: 4px 2px;
                cursor: pointer;
                border-radius: 5px;
            }
            QPushButton:disabled {
                background-color: #A5A5A5;
                cursor: not-allowed;
            }
            QLineEdit {
                background-color: #3C3C3C;
                border: 1px solid #555555;
                padding: 8px;
                color: white;
            }
            QTextEdit {
                background-color: #3C3C3C;
                border: 1px solid #555555;
                padding: 8px;
                color: white;
            }
            QLabel {
                font-weight: bold;
                font-size: 16px;
            }
            QCheckBox {
                font-weight: bold;
                font-size: 14px;
            }
        """)

        # INI 파일 선택 레이아웃
        ini_group = QGroupBox("INI 파일 선택")
        ini_layout = QHBoxLayout()
        self.ini_button = QPushButton("DLMODEL.ini 선택")
        self.ini_button.clicked.connect(self.select_ini_file)
        self.ini_line_edit = QLineEdit()
        self.ini_line_edit.setPlaceholderText("여기에 INI 파일 경로가 표시됩니다...")
        ini_layout.addWidget(self.ini_button)
        ini_layout.addWidget(self.ini_line_edit)
        ini_group.setLayout(ini_layout)

        # 정리 시작 버튼
        self.start_button = QPushButton("정리 시작")
        self.start_button.clicked.connect(self.start_cleanup)
        self.start_button.setEnabled(False)  # 유효한 INI 파일 선택 전까지 비활성화

        # 폴더 정리 옵션
        folder_option_group = QGroupBox("폴더 정리 옵션")
        folder_option_layout = QHBoxLayout()
        self.delete_all_folders_checkbox = QCheckBox("모든 폴더 삭제")
        self.keep_matching_folders_checkbox = QCheckBox("일치하는 폴더만 유지")
        folder_option_layout.addWidget(self.delete_all_folders_checkbox)
        folder_option_layout.addWidget(self.keep_matching_folders_checkbox)
        folder_option_group.setLayout(folder_option_layout)

        # 로그 보기
        log_group = QGroupBox("로그")
        log_layout = QVBoxLayout()
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        log_layout.addWidget(self.log_text_edit)
        log_group.setLayout(log_layout)

        # 로그 초기화 버튼
        self.clear_log_button = QPushButton("로그 초기화")
        self.clear_log_button.clicked.connect(self.clear_logs)

        # 레이아웃에 위젯 추가
        main_layout.addWidget(ini_group)
        main_layout.addWidget(self.start_button)
        main_layout.addWidget(folder_option_group)
        main_layout.addWidget(log_group)
        main_layout.addWidget(self.clear_log_button, alignment=Qt.AlignRight)

        self.setLayout(main_layout)

    def select_ini_file(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        # 기본 경로 설정: D:\AIV\MODEL
        ini_file, _ = QFileDialog.getOpenFileName(
            self,
            "DLMODEL.ini 파일 선택",
            r"D:\AIV\MODEL",
            "INI Files (*.ini);;모든 파일 (*)",
            options=options
        )
        if ini_file:
            file_name = os.path.basename(ini_file)
            if file_name.lower() != "dlmodel.ini":
                QMessageBox.critical(
                    self,
                    "잘못된 파일",
                    "선택한 파일이 DLMODEL.ini가 아닙니다. 올바른 파일을 선택해 주세요."
                )
                return
            self.ini_path = ini_file
            self.ini_line_edit.setText(self.ini_path)
            self.parse_ini_file()
            self.start_button.setEnabled(True)

    def parse_ini_file(self):
        config = configparser.ConfigParser()
        try:
            config.read(self.ini_path)
        except Exception as e:
            QMessageBox.critical(
                self,
                "오류",
                f"INI 파일을 읽는 중 오류가 발생했습니다: {e}"
            )
            return

        # [DLMODEL Information] 섹션에서 MODEL Count와 DLMODEL path 추출
        try:
            model_count = int(config.get("DLMODEL Information", "MODEL Count"))
            self.target_folder = config.get("DLMODEL Information", "DLMODEL path")
            if not os.path.isdir(self.target_folder):
                QMessageBox.critical(
                    self,
                    "오류",
                    f"DLMODEL path가 유효하지 않습니다: {self.target_folder}"
                )
                self.start_button.setEnabled(False)
                return
        except Exception as e:
            QMessageBox.critical(
                self,
                "오류",
                f"[DLMODEL Information] 섹션을 읽는 중 오류가 발생했습니다: {e}"
            )
            self.start_button.setEnabled(False)
            return

        # 모델 이름 추출 및 'name' 키 매핑
        self.file_names = []
        self.name_mapping = {}
        for i in range(1, model_count + 1):
            section = f"DLMODEL{str(i).zfill(4)}"
            if section in config:
                try:
                    model_name = config.get(section, "model name")
                    model_display_name = config.get(section, "name")
                    # 확장자를 제외한 파일명 추가
                    file_base, file_ext = os.path.splitext(model_name)
                    self.file_names.append(file_base)
                    self.name_mapping[file_base] = model_display_name
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "경고",
                        f"{section} 섹션에서 'model name' 또는 'name'을 읽는 중 오류가 발생했습니다: {e}"
                    )
            else:
                QMessageBox.warning(
                    self,
                    "경고",
                    f"{section} 섹션이 INI 파일에 존재하지 않습니다."
                )

        if self.file_names:
            self.log(f"[업데이트] 유지할 파일 목록이 업데이트되었습니다: {', '.join(self.file_names)}")
        else:
            QMessageBox.warning(
                self,
                "경고",
                "유지할 파일 목록이 비어 있습니다. INI 파일을 확인해 주세요."
            )
            self.start_button.setEnabled(False)

    def start_cleanup(self):
        # INI 파일 경로가 수정되었을 수 있으므로 다시 파싱
        self.ini_path = self.ini_line_edit.text().strip()
        if not os.path.isfile(self.ini_path):
            QMessageBox.critical(
                self,
                "오류",
                "INI 파일 경로가 유효하지 않습니다. 다시 선택해 주세요."
            )
            return
        file_name = os.path.basename(self.ini_path)
        if file_name.lower() != "dlmodel.ini":
            QMessageBox.critical(
                self,
                "잘못된 파일",
                "선택한 파일이 DLMODEL.ini가 아닙니다. 올바른 파일을 선택해 주세요."
            )
            return
        # INI 파일 파싱
        self.parse_ini_file()
        if not self.file_names:
            QMessageBox.critical(
                self,
                "오류",
                "유지할 파일 목록이 비어 있습니다. INI 파일을 확인해 주세요."
            )
            return
        if not self.target_folder:
            QMessageBox.critical(
                self,
                "오류",
                "DLMODEL path가 설정되지 않았습니다."
            )
            return

        # 백업 폴더 생성
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_folder = os.path.join(self.target_folder, f"{self.backup_folder_prefix}{current_time}")
        try:
            os.makedirs(self.backup_folder, exist_ok=True)
            self.log(f"[백업] 백업 폴더 생성: {self.backup_folder}")
        except Exception as e:
            QMessageBox.critical(
                self,
                "오류",
                f"백업 폴더를 생성하는 중 오류가 발생했습니다: {e}"
            )
            return

        # 폴더 정리 옵션 처리
        delete_all_folders = self.delete_all_folders_checkbox.isChecked()
        keep_matching_folders = self.keep_matching_folders_checkbox.isChecked()

        # 카운터 초기화
        self.retained_count = 0
        self.moved_count = 0

        # 대상 폴더 내 모든 파일 및 폴더 탐색
        try:
            for item in os.listdir(self.target_folder):
                item_path = os.path.join(self.target_folder, item)

                # 백업 폴더와 .svn 폴더는 무시
                if item == os.path.basename(self.backup_folder) or item.lower() == ".svn":
                    self.log(f"[무시] 특별 폴더: {item}")
                    continue

                if os.path.isfile(item_path):
                    file_base, file_ext = os.path.splitext(item)

                    # 유지할 파일인지 확인
                    if (file_base in self.file_names) and (file_ext.lower() in self.valid_extensions):
                        model_display_name = self.name_mapping.get(file_base, "Unknown")
                        self.log(f"[유지] {item} [{model_display_name}]")
                        self.retained_count += 1
                    else:
                        # 파일 이동
                        shutil.move(item_path, self.backup_folder)
                        self.log(f"[복사] {item} -> {self.backup_folder}")
                        self.moved_count += 1
                elif os.path.isdir(item_path):
                    # .svn 폴더는 이미 무시되었으므로 여기서는 다른 폴더만 처리
                    if delete_all_folders:
                        # 모든 폴더 삭제
                        shutil.rmtree(item_path)
                        self.log(f"[삭제] 폴더 삭제: {item}")
                    elif keep_matching_folders:
                        # 파일명과 일치하는 폴더만 유지
                        if item in self.file_names:
                            model_display_name = self.name_mapping.get(item, "Unknown")
                            self.log(f"[유지] 폴더: {item} [{model_display_name}]")
                        else:
                            shutil.rmtree(item_path)
                            self.log(f"[삭제] 폴더 삭제: {item}")
                    else:
                        # 아무 작업도 하지 않음
                        self.log(f"[무시] 폴더: {item}")

            # 완료 로그 및 메시지
            self.log(f"[완료] 파일 정리가 완료되었습니다. 유지된 파일: {self.retained_count}, 이동된 파일: {self.moved_count}")
            QMessageBox.information(
                self,
                "완료",
                f"파일 정리가 완료되었습니다.\n유지된 파일: {self.retained_count}\n이동된 파일: {self.moved_count}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "오류",
                f"파일 또는 폴더를 처리하는 중 오류가 발생했습니다: {e}"
            )

    def log(self, message):
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
        self.log_text_edit.append(f"{timestamp}{message}")

    def clear_logs(self):
        self.log_text_edit.clear()
        self.log("[정보] 로그가 초기화되었습니다.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DLModelCleaner()
    window.show()
    sys.exit(app.exec_())

# pyinstaller --onefile --windowed  --upx-dir "E:\Dev\DL_Tool\upx-4.2.4-win64" dlmodel_killer.py
# pyinstaller --windowed --icon=AiV_LOGO.ico --add-data "AiV_LOGO.ico;." dlmodel_killer.py