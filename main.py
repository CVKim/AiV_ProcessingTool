# main.py
import sys
import os
import signal
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from ui_dialogs import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    palette = app.palette()
    palette.setColor(palette.Window, Qt.white)
    palette.setColor(palette.Button, Qt.darkGray)
    palette.setColor(palette.ButtonText, Qt.white)
    palette.setColor(palette.Base, Qt.white)
    palette.setColor(palette.Text, Qt.black)
    app.setPalette(palette)

    window = MainWindow()
    window.show()

    def cleanup():
        print("프로그램 종료 중... 실행 중인 작업 정리")
        os._exit(0)  # 강제 종료

    app.aboutToQuit.connect(cleanup)  # 앱 종료 시 cleanup 함수 실행

    sys.exit(app.exec_())

if __name__ == '__main__': 
    main()

# pyinstaller --windowed --icon=AiV_LOGO.ico --add-data "AiV_LOGO.ico;." main.py
# pyinstaller --name APT --windowed --icon=AiV_LOGO.ico --add-data "AiV_LOGO.ico;." main.py