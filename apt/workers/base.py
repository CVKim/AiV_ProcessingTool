"""QThread worker + operation dispatch table.

The dispatch is data-driven so that adding a new task does not require
touching the if/elif chain that the legacy ``WorkerThread.run`` carried.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
from typing import Callable

from PyQt5.QtCore import QThread, pyqtSignal

from apt.constants import (
    OP_ATTACH_FOV,
    OP_BASIC_SORTING,
    OP_BTJ,
    OP_CROP,
    OP_DATE_COPY,
    OP_IMAGE_COPY,
    OP_MIM_TO_BMP,
    OP_NG_COUNT,
    OP_NG_SORTING,
    OP_SIMULATION,
)
from apt.utils.fs import ensure_target_folder as _ensure_target_folder

TaskHandler = Callable[["WorkerThread", dict], None]


def set_worker_priority() -> None:
    """Lower the OS scheduling priority of the calling worker thread.

    The legacy code shelled out to ``win32process`` on Windows and ``os.nice``
    elsewhere; we keep the same behavior so heavy I/O loops do not starve the
    UI thread.
    """
    try:
        import win32api  # type: ignore[import-untyped]
        import win32process  # type: ignore[import-untyped]

        thread_handle = win32api.GetCurrentThread()
        win32process.SetThreadPriority(thread_handle, win32process.THREAD_PRIORITY_BELOW_NORMAL)
    except ImportError:
        try:
            os.nice(10)
        except (AttributeError, OSError):
            pass


class WorkerThread(QThread):
    """The single QThread that owns one task at a time.

    Signals
    -------
    progress(int)
        0–100 percent progress.
    log(str)
        Free-form log line — UI appends to its log console.
    ng_count_result(object)
        NG-count result tuple ``(rows, total_top_folders, total_cams,
        total_defects)``.
    finished(str)
        Terminal status message — always emitted exactly once when the task
        completes (success, cancel, or exception).
    """

    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    ng_count_result = pyqtSignal(object)
    finished = pyqtSignal(str)

    def __init__(self, task: dict) -> None:
        super().__init__()
        self.task: dict = task
        self._is_stopped = False
        self.max_workers = min(12, (multiprocessing.cpu_count() or 1) * 2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def stop(self) -> None:
        self._is_stopped = True

    def is_stopped(self) -> bool:
        return self._is_stopped

    def run(self) -> None:  # noqa: D401
        operation = self.task.get("operation", "")
        handler = _HANDLERS.get(operation)
        if handler is None:
            self.log.emit(f"알 수 없는 작업 유형입니다: {operation!r}")
            self.finished.emit("알 수 없는 작업 유형입니다.")
            return
        try:
            handler(self, self.task)
        except Exception as exc:  # noqa: BLE001
            logging.error("작업 중 오류 발생", exc_info=True)
            self.log.emit(f"오류 발생: {exc}")
            self.finished.emit("작업 중 오류 발생했습니다.")

    # ------------------------------------------------------------------
    # Shared helpers — workers call these instead of redefining their own.
    # ------------------------------------------------------------------
    def ensure_target_folder(self, target_path: str) -> bool:
        return _ensure_target_folder(target_path, log=self.log.emit)


# ---------------------------------------------------------------------------
# Operation registry — populated below by importing the task modules.
# Each handler signature: handler(worker: WorkerThread, task: dict) -> None
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, TaskHandler] = {}


def register(operation: str, handler: TaskHandler) -> TaskHandler:
    """Register a worker task. Returns the handler so it can decorate."""
    _HANDLERS[operation] = handler
    return handler


# Import task modules so they self-register. The imports are at module bottom
# to avoid circular imports with workers.base.
from apt.workers import (  # noqa: E402,F401  (registration side-effects)
    btj,
    copying,
    counting,
    cropping,
    fov,
    mim,
    sorting,
)

# Sanity check — every operation key declared in constants must have a handler.
_EXPECTED = {
    OP_NG_SORTING,
    OP_DATE_COPY,
    OP_IMAGE_COPY,
    OP_SIMULATION,
    OP_BASIC_SORTING,
    OP_NG_COUNT,
    OP_CROP,
    OP_ATTACH_FOV,
    OP_MIM_TO_BMP,
    OP_BTJ,
}
_missing = _EXPECTED - _HANDLERS.keys()
if _missing:  # pragma: no cover — would break import
    raise RuntimeError(f"Worker handlers missing for: {sorted(_missing)}")
