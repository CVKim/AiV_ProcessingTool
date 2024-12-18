import sys
import os
import shutil
import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QFileDialog,
    QProgressBar, QMessageBox, QLabel, QHBoxLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

logging.basicConfig(filename='error.log', level=logging.ERROR,
                    format='%(asctime)s:%(levelname)s:%(message)s')

class FileCopierThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(int)
    stopped = False

    def __init__(self, source, target):
        super().__init__()
        self.source = source
        self.target = target

    def run(self):
        try:
            bmp_files = [f for f in os.listdir(self.source) if f.lower().endswith('.bmp')]
            total = len(bmp_files)
            if total == 0:
                self.finished.emit(0)
                return

            for index, file in enumerate(bmp_files, start=1):
                if self.stopped:
                    self.finished.emit(index - 1)
                    return
                src_path = os.path.join(self.source, file)
                dst_path = os.path.join(self.target, file)
                shutil.copy2(src_path, dst_path)  # 파일 복사
                progress_percent = int((index / total) * 100)
                self.progress.emit(progress_percent)
                self.msleep(50)  # Optional: Slow down for demonstration
            self.finished.emit(total)
        except Exception as e:
            logging.error("파일 복사 중 오류 발생", exc_info=True)
            self.finished.emit(-1)

    def stop(self):
        self.stopped = True


class FileCopierGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.thread = None

    def initUI(self):
        self.setWindowTitle('BMP 파일 복사기')

        layout = QVBoxLayout()

        self.copy_button = QPushButton('Image File Copy', self)
        self.copy_button.clicked.connect(self.start_copy)
        layout.addWidget(self.copy_button)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel('상태: 대기 중', self)
        layout.addWidget(self.status_label)

        self.stop_button = QPushButton('Stop', self)
        self.stop_button.clicked.connect(self.stop_copy)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        self.setLayout(layout)
        self.setGeometry(100, 100, 400, 200)

    def start_copy(self):
        source = QFileDialog.getExistingDirectory(self, "소스 폴더 선택")
        if not source:
            return
        target = QFileDialog.getExistingDirectory(self, "타겟 폴더 선택")
        if not target:
            return

        self.copy_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText('상태: 복사 중...')

        self.thread = FileCopierThread(source, target)
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.copy_finished)
        self.thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def copy_finished(self, count):
        self.copy_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        if count == -1:
            QMessageBox.critical(self, "오류", "파일 복사 중 오류가 발생했습니다.")
            self.status_label.setText('상태: 오류 발생')
        elif count == 0:
            QMessageBox.information(self, "완료", "복사할 BMP 파일이 없습니다.")
            self.status_label.setText('상태: 완료 (파일 없음)')
            self.close_program()
        else:
            QMessageBox.information(self, "완료", f"{count}개의 BMP 파일을 복사했습니다.")
            self.status_label.setText(f'상태: 완료 ({count}개 복사)')
            self.close_program()

    def stop_copy(self):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait()
            QMessageBox.information(self, "중지", "파일 복사가 중지되었습니다.")
            self.status_label.setText('상태: 중지됨')
            self.copy_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.close_program()

    def close_program(self):
        reply = QMessageBox.question(self, '프로그램 종료', '프로그램을 종료하시겠습니까?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            QApplication.instance().quit()

def main():
    app = QApplication(sys.argv)
    gui = FileCopierGUI()
    gui.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()