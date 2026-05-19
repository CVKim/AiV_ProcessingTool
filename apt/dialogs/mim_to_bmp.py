from __future__ import annotations

import configparser
import os

from PyQt5.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
)

from apt.constants import OP_MIM_TO_BMP
from apt.dialogs.base import BaseTaskPanel
from apt.widgets import PathPicker


class MIMtoBMPPanel(BaseTaskPanel):
    TITLE = "MIM to BMP"
    SUBTITLE = (
        "INI 파일을 선택하면 모든 [PATH*] 섹션의 Source/Target 값을 초기화한 뒤 편집합니다. "
        "Start 클릭 시 mim2color.exe를 새 콘솔로 실행합니다."
    )

    def __init__(self, parent=None) -> None:
        self._ini_path = ""
        self._orig_text = ""
        super().__init__(parent)

    def build_form(self, form: QFormLayout) -> None:
        self.ini_picker = PathPicker(
            "Select INI file",
            "Select mim_converter_config.ini",
            pick_file=True,
            file_filter="INI files (*.ini)",
            read_only=True,
        )
        self.ini_picker.pathChanged.connect(self._on_ini_picked)
        form.addRow(QLabel("<b>INI Path</b>"), self.ini_picker)

        self.editor = QTextEdit()
        self.editor.setEnabled(False)
        self.editor.setFontFamily("Consolas")
        self.editor.setLineWrapMode(QTextEdit.NoWrap)
        self.editor.setMinimumHeight(200)
        form.addRow(QLabel("<b>INI Contents</b>"), self.editor)

        btn_row = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save_ini)
        self.reload_button = QPushButton("Reload")
        self.reload_button.setEnabled(False)
        self.reload_button.clicked.connect(self._reload_ini)
        btn_row.addWidget(self.save_button)
        btn_row.addWidget(self.reload_button)
        btn_row.addStretch(1)
        form.addRow("", btn_row)

    # -- INI helpers ---------------------------------------------------
    def _clear_path_fields(self, ini_path: str) -> bool:
        cfg = configparser.ConfigParser()
        cfg.optionxform = str
        cfg.read(ini_path, encoding="utf-8")
        changed = False
        for sec in cfg.sections():
            if sec.upper().startswith("PATH"):
                if cfg[sec].get("Source mim path", ""):
                    cfg[sec]["Source mim path"] = ""
                    changed = True
                if cfg[sec].get("Target img path", ""):
                    cfg[sec]["Target img path"] = ""
                    changed = True
        if changed:
            with open(ini_path, "w", encoding="utf-8") as fw:
                cfg.write(fw)
        return changed

    def _on_ini_picked(self, path: str) -> None:
        if not path or path == self._ini_path:
            return
        try:
            cleared = self._clear_path_fields(path)
            if cleared:
                self.append_log(f"[INI] PATH 섹션의 Source/Target 값을 초기화하여 저장했습니다 → {path}")
            else:
                self.append_log(f"[INI] 이미 경로가 비어있거나 PATH 섹션이 없습니다 → {path}")
        except Exception as exc:
            QMessageBox.critical(self, "INI 처리 오류", str(exc))
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as exc:
            QMessageBox.critical(self, "INI 열기 오류", str(exc))
            return
        self._ini_path = path
        self._orig_text = text
        self.editor.setPlainText(text)
        self.editor.setEnabled(True)
        self.save_button.setEnabled(True)
        self.reload_button.setEnabled(True)
        self.append_log(f"INI 로드 완료: {path}")

    def _save_ini(self) -> None:
        if not self._ini_path:
            return
        try:
            with open(self._ini_path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self._orig_text = self.editor.toPlainText()
            self.append_log(f"INI 저장 완료: {self._ini_path}")
        except Exception as exc:
            QMessageBox.critical(self, "저장 오류", str(exc))

    def _reload_ini(self) -> None:
        if not self._ini_path:
            return
        try:
            with open(self._ini_path, "r", encoding="utf-8") as f:
                text = f.read()
            self.editor.setPlainText(text)
            self._orig_text = text
            self.append_log(f"INI 되돌리기: {self._ini_path}")
        except Exception as exc:
            QMessageBox.critical(self, "로드 오류", str(exc))

    # -- task wiring ----------------------------------------------------
    def get_parameters(self) -> dict:
        return {"operation": OP_MIM_TO_BMP, "ini_path": self._ini_path.strip()}

    def validate_parameters(self, params: dict) -> bool:
        ini_path = params.get("ini_path", "")
        if not ini_path or not os.path.isfile(ini_path):
            QMessageBox.warning(self, "입력 오류", "INI 파일을 선택해야 합니다.")
            return False
        return True
