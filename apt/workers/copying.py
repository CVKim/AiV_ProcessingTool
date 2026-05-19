"""Date-Based Copy / Image Format Copy / Simulation Foldering handlers."""

from __future__ import annotations

import logging
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import TYPE_CHECKING

from apt.constants import OP_DATE_COPY, OP_IMAGE_COPY, OP_SIMULATION
from apt.utils.formats import is_valid_file
from apt.utils.fs import copy_file_chunked, copy_folder_filtered

if TYPE_CHECKING:
    from apt.workers.base import WorkerThread


# ---------------------------------------------------------------------------
# 1) Date-Based Copy
# ---------------------------------------------------------------------------

def date_based_copy(worker: "WorkerThread", task: dict) -> None:
    from apt.workers.base import set_worker_priority

    worker.log.emit("------ Date-Based Copy 작업 시작 ------")
    try:
        mode = task.get("mode", "folder")
        source = task["source"]
        target = task["target"]
        count = task["count"]
        formats = task.get("formats", [])
        specified_dt = datetime(
            task["year"], task["month"], task["day"],
            task["hour"], task["minute"], task["second"],
        )
        strong_random = task.get("strong_random", False)
        conditional_random = task.get("conditional_random", False)
        random_count = task.get("random_count", 0)
        fov_numbers = task.get("fov_numbers", [])

        if not os.path.exists(source):
            worker.log.emit(f"Source 경로 없음: {source}")
            worker.finished.emit("Date-Based Copy 중지됨.")
            return
        if not worker.ensure_target_folder(target):
            worker.finished.emit("Date-Based Copy 중지됨.")
            return

        all_folders = [
            os.path.join(source, f)
            for f in os.listdir(source)
            if os.path.isdir(os.path.join(source, f))
        ]
        eligible: list[str] = []
        for folder in all_folders:
            try:
                if datetime.fromtimestamp(os.path.getmtime(folder)) >= specified_dt:
                    eligible.append(folder)
            except Exception as exc:
                worker.log.emit(f"폴더 {folder} 수정시간 오류: {exc}")
        if not eligible:
            worker.log.emit("지정 날짜 이후 폴더 없음")
            worker.finished.emit("Date-Based Copy 완료.")
            return

        sorted_folders = sorted(eligible, key=lambda x: os.path.getmtime(x))
        is_stopped = worker.is_stopped

        if mode == "folder":
            if strong_random:
                worker.log.emit("Strong Random (Folder Mode)")
                selected = sorted_folders if len(sorted_folders) < count else random.sample(sorted_folders, count)
            elif conditional_random:
                worker.log.emit(f"Conditional Random (Folder Mode, Random Count: {random_count})")
                selected = []
                index = 0
                while index < len(sorted_folders) and len(selected) < count:
                    selected.append(sorted_folders[index])
                    index += (random_count + 1)
            else:
                selected = sorted_folders[:count]
            total = len(selected)
            worker.log.emit(
                f"날짜: {specified_dt.strftime('%Y-%m-%d %H:%M:%S')}, 폴더 수: {total}"
            )
            processed = 0
            with ThreadPoolExecutor(max_workers=worker.max_workers, initializer=set_worker_priority) as executor:
                futures = []
                for folder_path in selected:
                    if is_stopped():
                        worker.log.emit(f"작업 중지: 폴더 처리 {processed}")
                        worker.finished.emit(f"작업 중지됨. 폴더 처리: {processed}")
                        return
                    folder_name = os.path.basename(folder_path)
                    dst_folder = os.path.join(target, folder_name)
                    if not worker.ensure_target_folder(dst_folder):
                        continue
                    worker.log.emit(f"Source: {folder_path}, Destination: {dst_folder}")
                    futures.append(
                        executor.submit(copy_folder_filtered, folder_path, dst_folder, formats, is_stopped)
                    )
                for future in as_completed(futures):
                    if is_stopped():
                        worker.log.emit(f"작업 중지: 폴더 처리 {processed}")
                        worker.finished.emit(f"작업 중지됨. 폴더 처리: {processed}")
                        return
                    worker.log.emit(future.result())
                    processed += 1
                    worker.progress.emit(min(int(processed / total * 100), 100))
            worker.finished.emit(f"Date-Based Copy (Folder Mode) 완료. 폴더 처리: {processed}")
            worker.log.emit("------ Date-Based Copy (Folder Mode) 완료 ------")
            return

        if mode == "image":
            if not fov_numbers:
                worker.log.emit("Image 모드 FOV Numbers 필수")
                worker.finished.emit("Date-Based Copy 중지됨.")
                return
            if strong_random:
                worker.log.emit("Strong Random (Image Mode)")
                selected = sorted_folders if len(sorted_folders) < count else random.sample(sorted_folders, count)
            elif conditional_random:
                worker.log.emit(f"Conditional Random (Image Mode, Random Count: {random_count})")
                selected = []
                index = 0
                while index < len(sorted_folders) and len(selected) < count:
                    selected.append(sorted_folders[index])
                    index += random_count
            else:
                selected = sorted_folders[:count]
            total = len(selected)
            worker.log.emit(f"Image Mode: 선택된 폴더 수 {total}")
            processed_folders = 0
            processed_images = 0
            for folder_path in selected:
                if is_stopped():
                    worker.log.emit(f"작업 중지: 폴더 처리 {processed_folders}")
                    worker.finished.emit(f"작업 중지됨. 폴더 처리: {processed_folders}")
                    return
                inner_id = os.path.basename(folder_path)
                try:
                    with os.scandir(folder_path) as it:
                        image_files = [
                            entry.name for entry in it
                            if entry.is_file() and is_valid_file(entry.name, formats)
                        ]
                except Exception as exc:
                    worker.log.emit(f"폴더 {folder_path} 파일 목록 오류: {exc}")
                    continue
                matching = []
                for image in image_files:
                    parts = image.split("_", 1)
                    if len(parts) < 2:
                        worker.log.emit(f"파일 이름 오류: {image}")
                        continue
                    prefix = parts[0].lower()
                    digits = re.sub(r"[^0-9]", "", prefix)
                    if digits in fov_numbers:
                        matching.append(image)
                if not matching:
                    worker.log.emit(f"폴더 {folder_path} FOV 미일치")
                else:
                    worker.log.emit(f"폴더 {folder_path}에서 {len(matching)} 이미지 복사 시작")
                    with ThreadPoolExecutor(max_workers=worker.max_workers, initializer=set_worker_priority) as executor:
                        futures = []
                        for image in matching:
                            if is_stopped():
                                break
                            src_file = os.path.join(folder_path, image)
                            file_base, file_ext = os.path.splitext(image)
                            new_name = f"{inner_id}_{file_base}{file_ext}"
                            dst_file = os.path.join(target, new_name)
                            if os.path.exists(dst_file):
                                worker.log.emit(f"파일 건너뜀: {dst_file}")
                                continue
                            futures.append(executor.submit(copy_file_chunked, src_file, dst_file, is_stopped))
                        for future in as_completed(futures):
                            if is_stopped():
                                break
                            result = future.result()
                            if result.startswith("오류 발생"):
                                worker.log.emit(result)
                            else:
                                processed_images += 1
                                worker.log.emit(result)
                processed_folders += 1
                worker.progress.emit(min(int(processed_folders / total * 100), 100))
            worker.finished.emit(
                f"Date-Based Copy (Image Mode) 완료. 폴더: {processed_folders}, 이미지: {processed_images}"
            )
            worker.log.emit("------ Date-Based Copy (Image Mode) 완료 ------")
            return

        worker.log.emit(f"알 수 없는 mode: {mode}")
        worker.finished.emit("Date-Based Copy 중지됨.")
    except Exception as exc:
        logging.error("Date-Based Copy 중 오류 발생", exc_info=True)
        worker.log.emit(f"오류 발생: {exc}")
        worker.finished.emit("Date-Based Copy 중 오류 발생.")


# ---------------------------------------------------------------------------
# 2) Image Format Copy
# ---------------------------------------------------------------------------

def image_format_copy(worker: "WorkerThread", task: dict) -> None:
    from apt.workers.base import set_worker_priority

    worker.log.emit("------ Image Format Copy 작업 시작 ------")
    try:
        sources = task["sources"]
        targets = task["targets"]
        formats = task["formats"]

        if targets and not os.path.exists(targets[0]):
            os.makedirs(targets[0], exist_ok=True)

        total = 0
        pairs = list(zip(sources, targets))
        for source, _target in pairs:
            if os.path.exists(source):
                try:
                    with os.scandir(source) as it:
                        total += sum(
                            1 for entry in it
                            if entry.is_file() and is_valid_file(entry.name, formats)
                        )
                except Exception as exc:
                    worker.log.emit(f"Source {source} 파일 목록 오류: {exc}")
        if total == 0:
            worker.log.emit("선택한 이미지 포맷 없음")
            worker.finished.emit("Image Format Copy 완료.")
            return
        worker.log.emit(f"총 복사할 이미지 수: {total}")

        is_stopped = worker.is_stopped
        processed = 0
        with ThreadPoolExecutor(max_workers=worker.max_workers, initializer=set_worker_priority) as executor:
            futures = []
            for source, target in pairs:
                if is_stopped():
                    worker.log.emit(f"작업 중지: 처리 이미지 {processed}")
                    worker.finished.emit(f"작업 중지됨. 처리 이미지: {processed}")
                    return
                if not os.path.exists(source):
                    worker.log.emit(f"Source 경로 없음: {source}")
                    continue
                if not worker.ensure_target_folder(target):
                    continue
                try:
                    with os.scandir(source) as it:
                        image_files = [
                            entry.name for entry in it
                            if entry.is_file() and is_valid_file(entry.name, formats)
                        ]
                except Exception as exc:
                    worker.log.emit(f"Source {source} 파일 목록 오류: {exc}")
                    continue
                for name in image_files:
                    if is_stopped():
                        worker.log.emit(f"작업 중지: 처리 이미지 {processed}")
                        worker.finished.emit(f"작업 중지됨. 처리 이미지: {processed}")
                        return
                    src_file = os.path.join(source, name)
                    dst_file = os.path.join(target, name)
                    futures.append(executor.submit(copy_file_chunked, src_file, dst_file, is_stopped))

            for future in as_completed(futures):
                if is_stopped():
                    worker.log.emit(f"작업 중지: 처리 이미지 {processed}")
                    worker.finished.emit(f"작업 중지됨. 처리 이미지: {processed}")
                    return
                result = future.result()
                if result.startswith("오류 발생"):
                    worker.log.emit(result)
                else:
                    processed += 1
                    worker.log.emit(result)
                    worker.progress.emit(min(int(processed / total * 100), 100))
        worker.finished.emit(f"Image Format Copy 완료. 처리 이미지: {processed}")
        worker.log.emit("------ Image Format Copy 작업 완료 ------")
    except Exception as exc:
        logging.error("Image Format Copy 오류", exc_info=True)
        worker.log.emit(f"오류 발생: {exc}")
        worker.finished.emit("Image Format Copy 중 오류 발생.")


# ---------------------------------------------------------------------------
# 3) Simulation Foldering (legacy stub — kept as-is)
# ---------------------------------------------------------------------------

def simulation_foldering(worker: "WorkerThread", _task: dict) -> None:
    worker.log.emit("------ Simulation Foldering 작업 시작 ------")
    worker.finished.emit("Simulation Foldering 작업 완료.")


from apt.workers.base import register  # noqa: E402

register(OP_DATE_COPY, date_based_copy)
register(OP_IMAGE_COPY, image_format_copy)
register(OP_SIMULATION, simulation_foldering)
