"""MIM-to-BMP handler — shells out to ``mim2color.exe`` in a new console."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import TYPE_CHECKING

from apt.constants import OP_MIM_TO_BMP

if TYPE_CHECKING:
    from apt.workers.base import WorkerThread


def _find_mim2color() -> str | None:
    cwd_dir = os.getcwd()
    exe_path = os.path.join(cwd_dir, "mim2color.exe")
    if os.path.isfile(exe_path):
        return exe_path
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    exe_path = os.path.join(script_dir, "mim2color.exe")
    if os.path.isfile(exe_path):
        return exe_path
    # Fallback: project root next to the apt/ package
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(package_root)
    exe_path = os.path.join(project_root, "mim2color.exe")
    if os.path.isfile(exe_path):
        return exe_path
    return None


def mim_to_bmp(worker: "WorkerThread", task: dict) -> None:
    worker.log.emit("------ MIM to BMP 작업 시작 ------")
    try:
        exe_path = _find_mim2color()
        if not exe_path:
            worker.log.emit("mim2color.exe 를 찾을 수 없습니다.")
            worker.finished.emit("MIM to BMP 중지됨.")
            return

        ini_path = task.get("ini_path", "").strip()
        if not ini_path or not os.path.isfile(ini_path):
            worker.log.emit("INI 경로가 유효하지 않습니다.")
            worker.finished.emit("MIM to BMP 중지됨.")
            return

        worker.log.emit(f"INI 사용: {ini_path}")
        worker.log.emit(f"실행 파일: {exe_path}")

        creation_flags = 0
        if os.name == "nt":
            creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)

        subprocess.Popen(
            [exe_path, ini_path],
            cwd=os.path.dirname(exe_path),
            creationflags=creation_flags,
        )
        worker.progress.emit(100)
        worker.finished.emit("mim2color.exe 실행 지시 완료 (새 콘솔 창).")
        worker.log.emit("------ 작업 지시 후 종료 ------")
    except Exception as exc:
        logging.error("MIM to BMP 오류", exc_info=True)
        worker.log.emit(f"오류 발생: {exc}")
        worker.finished.emit("MIM to BMP 중 오류 발생.")


from apt.workers.base import register  # noqa: E402

register(OP_MIM_TO_BMP, mim_to_bmp)
