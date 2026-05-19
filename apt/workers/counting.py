"""NG Count handler.

Bug fix vs legacy: the original ``ng_count`` never emitted ``finished`` on
success (the call was commented out), which left the dialog's Start button
permanently disabled. We now always emit a terminal status.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from apt.constants import OP_NG_COUNT

if TYPE_CHECKING:
    from apt.workers.base import WorkerThread


def ng_count(worker: "WorkerThread", task: dict) -> None:
    worker.log.emit("------ NG Count 작업 시작 ------")
    try:
        ng_folder = task["ng_folder"]
        if not os.path.exists(ng_folder):
            worker.log.emit(f"NG 폴더 없음: {ng_folder}")
            worker.finished.emit("NG Count 중지됨.")
            return

        try:
            with os.scandir(ng_folder) as it:
                cam_folders = [
                    entry.name for entry in it
                    if entry.is_dir() and entry.name.startswith("Cam_")
                ]
        except Exception as exc:
            worker.log.emit(f"Cam_ 폴더 탐색 오류: {exc}")
            worker.finished.emit("NG Count 중지됨.")
            return

        total_cams = len(cam_folders)
        total_defects = 0
        rows: list[list] = []

        if total_cams == 0:
            worker.log.emit("NG 폴더 내 Cam_ 폴더 없음")
            worker.ng_count_result.emit(([], 0, 0, 0))
            worker.finished.emit("NG Count 완료.")
            return

        is_stopped = worker.is_stopped
        for i, cam in enumerate(cam_folders, start=1):
            if is_stopped():
                worker.log.emit(f"작업 중지: Cam {total_cams}, Defect {total_defects}")
                worker.finished.emit(f"작업 중지됨. Cam {total_cams}, Defect {total_defects}")
                return
            cam_path = os.path.join(ng_folder, cam)
            try:
                with os.scandir(cam_path) as it:
                    defect_folders = [entry.name for entry in it if entry.is_dir()]
            except Exception as exc:
                worker.log.emit(f"Cam {cam_path} Defect 폴더 오류: {exc}")
                continue
            for defect in defect_folders:
                defect_path = os.path.join(cam_path, defect)
                try:
                    with os.scandir(defect_path) as it_def:
                        count = sum(1 for entry in it_def if entry.is_dir())
                    rows.append([cam, defect, count])
                    total_defects += count
                except Exception as exc:
                    worker.log.emit(f"Defect {defect_path} 항목 계산 오류: {exc}")
            worker.progress.emit(min(int(i / total_cams * 100), 100))

        # Top folder count from the parent of ng_folder (excluding ok/ng/ng_info)
        parent = os.path.dirname(ng_folder)
        exclude = {"ng", "ok", "ng_info"}
        total_top_folders = 0
        if os.path.isdir(parent):
            try:
                with os.scandir(parent) as it:
                    total_top_folders = sum(
                        1 for entry in it
                        if entry.is_dir() and entry.name.lower() not in exclude
                    )
            except Exception as exc:
                worker.log.emit(f"상위 폴더 탐색 오류: {exc}")

        worker.ng_count_result.emit((rows, total_top_folders, total_cams, total_defects))
        worker.log.emit("------ NG Count 작업 완료 ------")
        worker.finished.emit(
            f"NG Count 완료. Cam {total_cams}, Defect {total_defects}, Top folders {total_top_folders}"
        )
    except Exception as exc:
        logging.error("NG Count 오류", exc_info=True)
        worker.log.emit(f"오류 발생: {exc}")
        worker.finished.emit("NG Count 중 오류 발생.")


from apt.workers.base import register  # noqa: E402

register(OP_NG_COUNT, ng_count)
