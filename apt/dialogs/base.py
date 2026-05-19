"""Shared base for task panels.

Layout (top to bottom):
    [page header: title + subtitle]
    [configuration area  — subclass-provided ``build_form(form_layout)``]
    [Logs (LogConsole)]
    [Progress bar]
    [Start / Stop buttons]

Subclasses provide ``TITLE`` / ``SUBTITLE`` class attributes, implement
``build_form()`` to populate the form, and override ``get_parameters()`` /
``validate_parameters()`` to produce the worker task dict.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from apt.widgets import LogConsole
from apt.workers import WorkerThread


class BaseTaskPanel(QWidget):
    TITLE: str = "Task"
    SUBTITLE: str = ""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.worker: WorkerThread | None = None
        self._build_layout()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        title = QLabel(self.TITLE)
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        if self.SUBTITLE:
            subtitle = QLabel(self.SUBTITLE)
            subtitle.setObjectName("PageSubtitle")
            subtitle.setWordWrap(True)
            layout.addWidget(subtitle)

        config_group = QGroupBox("Configuration")
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(14, 18, 14, 14)
        config_layout.setSpacing(10)
        self._form = QFormLayout()
        self._form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._form.setSpacing(8)
        config_layout.addLayout(self._form)
        layout.addWidget(config_group)

        self.build_form(self._form)

        self.log_console = LogConsole()
        layout.addWidget(self.log_console, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self.start_task)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("DangerButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_task)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        layout.addLayout(button_row)

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------
    def build_form(self, form: QFormLayout) -> None:
        """Subclasses populate ``form`` with their inputs."""

    def get_parameters(self) -> dict:
        return {}

    def validate_parameters(self, params: dict) -> bool:
        return True

    # ------------------------------------------------------------------
    # Task lifecycle
    # ------------------------------------------------------------------
    def append_log(self, message: str) -> None:
        self.log_console.append(message)

    def start_task(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.warning(self, "작업 중", "이미 작업이 진행 중입니다.")
            return
        self.append_log("------ 작업 시작 ------")
        self.progress_bar.setValue(0)
        params = self.get_parameters()
        if not self.validate_parameters(params):
            self.append_log("------ 작업 중지 ------")
            return
        try:
            self.worker = WorkerThread(params)
        except Exception as exc:  # pragma: no cover
            logging.error("WorkerThread 생성 실패", exc_info=True)
            self.append_log(f"WorkerThread 생성 실패: {exc}")
            return
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.append_log)
        if params.get("operation") == "ng_count":
            self.worker.ng_count_result.connect(self.update_ng_count_table)
        self.worker.finished.connect(self.task_finished)
        self.worker.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_task(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.append_log("Stop 신호를 보냈습니다.")
            self.stop_button.setEnabled(False)

    def update_progress(self, value: int) -> None:
        self.progress_bar.setValue(value)

    def task_finished(self, message: str) -> None:
        self.append_log(message)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        if any(token in message for token in ("완료", "오류", "중지")):
            self.append_log("------ 작업 종료 ------")

    def update_ng_count_table(self, data) -> None:  # noqa: D401
        """Default no-op — overridden by NGCountPanel."""

    # ------------------------------------------------------------------
    # Common validators (call these from validate_parameters as needed)
    # ------------------------------------------------------------------
    def warn_missing(self, missing: Iterable[str], invalid: Iterable[str] = ()) -> bool:
        messages: list[str] = []
        missing = list(missing)
        invalid = list(invalid)
        if missing:
            messages.append("다음 필드를 입력해야 합니다:")
            messages.extend(missing)
        if invalid:
            messages.append("다음 경로가 유효하지 않습니다:")
            messages.extend(invalid)
        if not messages:
            return True
        QMessageBox.warning(self, "입력 오류", "\n".join(messages))
        return False

    @staticmethod
    def validate_paths(params: dict, fields: Iterable[str]) -> list[str]:
        invalid: list[str] = []
        for field in fields:
            path = params.get(field, "")
            if path and not os.path.isdir(path):
                invalid.append(f"{field.capitalize()} Path이(가) 유효하지 않습니다.")
        return invalid
