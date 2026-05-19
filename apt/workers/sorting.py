"""NG Folder Sorting and Basic Sorting task handlers.

These are split out of the legacy ``WorkerThread`` but the algorithms are
preserved line-for-line so existing pipelines stay byte-compatible.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from apt.constants import IGNORED_DIRS, OP_BASIC_SORTING, OP_NG_SORTING
from apt.utils.formats import is_valid_file
from apt.utils.fov import extract_fov_from_filename, parse_fov_numbers
from apt.utils.fs import copy_file_chunked

if TYPE_CHECKING:
    from apt.workers.base import WorkerThread


# ---------------------------------------------------------------------------
# Collection helpers (shared by both handlers).
# ---------------------------------------------------------------------------

def _collect_inner_ids(worker: "WorkerThread", sources) -> set[str]:
    inner_ids: set[str] = set()
    iterable = sources if isinstance(sources, list) else [sources]
    for source in iterable:
        if not os.path.exists(source):
            worker.log.emit(f"Source 경로 없음: {source}")
            continue
        folder_name = os.path.basename(source.rstrip(os.sep))
        if folder_name.lower() not in IGNORED_DIRS:
            inner_ids.add(folder_name)
    return inner_ids


def _collect_inner_ids_from_source2(worker: "WorkerThread", source2: str) -> set[str]:
    if not os.path.exists(source2):
        worker.log.emit(f"Source2 경로 없음: {source2}")
        return set()
    try:
        with os.scandir(source2) as it:
            return {
                entry.name
                for entry in it
                if entry.is_dir() and entry.name.lower() not in IGNORED_DIRS
            }
    except Exception as exc:
        worker.log.emit(f"Source2에서 Inner ID 수집 오류: {exc}")
        return set()


def _collect_images_to_copy(
    worker: "WorkerThread",
    inner_ids: set[str],
    source: str,
    formats: list[str],
) -> tuple[dict[str, list[str]], int]:
    images_to_copy: dict[str, list[str]] = {}
    total_images = 0
    for inner_id in inner_ids:
        source_folder = os.path.join(source, inner_id)
        if not os.path.exists(source_folder):
            worker.log.emit(f"Source 내 폴더 없음: {source_folder}")
            continue
        try:
            with os.scandir(source_folder) as it:
                images = [
                    entry.name
                    for entry in it
                    if entry.is_file() and is_valid_file(entry.name, formats)
                ]
            if images:
                images_to_copy[inner_id] = images
                total_images += len(images)
        except Exception as exc:
            worker.log.emit(f"이미지 수집 오류: {source_folder} | 에러: {exc}")
    return images_to_copy, total_images


def _get_fovs_from_folder(worker: "WorkerThread", folder_path: str) -> set[str]:
    if not os.path.isdir(folder_path):
        return set()
    fov_numbers: set[str] = set()
    try:
        with os.scandir(folder_path) as it:
            for entry in it:
                if entry.is_file():
                    digits = extract_fov_from_filename(entry.name)
                    if digits:
                        fov_numbers.add(digits)
    except Exception as exc:
        worker.log.emit(f"FOV 추출 오류: {folder_path} | 에러: {exc}")
    return fov_numbers


def _get_matching_files_for_folder(
    worker: "WorkerThread",
    folder_path: str,
    formats: list[str],
    fov_numbers: set[str],
) -> list[str]:
    if not os.path.isdir(folder_path):
        return []
    try:
        with os.scandir(folder_path) as it:
            image_files = [
                entry.name
                for entry in it
                if entry.is_file() and is_valid_file(entry.name, formats)
            ]
        matching = []
        for fname in image_files:
            digits = extract_fov_from_filename(fname)
            if digits and digits in fov_numbers:
                matching.append(fname)
        return matching
    except Exception as exc:
        worker.log.emit(f"이미지 목록 오류: {folder_path} | 에러: {exc}")
        return []


# ---------------------------------------------------------------------------
# 1) NG Folder Sorting
# ---------------------------------------------------------------------------

def ng_folder_sorting(worker: "WorkerThread", task: dict) -> None:
    from apt.workers.base import set_worker_priority

    worker.log.emit("------ NG Folder Sorting 작업 시작 ------")
    try:
        sources1 = task.get("inputs", [])
        source2 = task.get("source2", "")
        target = task.get("target", "")
        formats = task.get("formats", [])
        worker.log.emit(f"Sources1: {sources1}")
        worker.log.emit(f"Source2: {source2}")
        worker.log.emit(f"Target: {target}")
        worker.log.emit(f"Formats: {formats}")

        if not worker.ensure_target_folder(target):
            worker.finished.emit("NG Folder Sorting 중단.")
            return

        inner_ids_sources1 = _collect_inner_ids(worker, sources1)
        inner_ids_source2 = _collect_inner_ids_from_source2(worker, source2)
        matched = inner_ids_sources1 & inner_ids_source2

        if not matched:
            worker.log.emit("sources1과 source2 모두에 존재하는 Inner ID가 없습니다.")
            worker.finished.emit("NG Folder Sorting 완료.")
            return

        worker.log.emit(f"총 매칭된 Inner ID 수: {len(matched)}")

        images_to_copy, total_images = _collect_images_to_copy(
            worker, matched, source2, formats
        )
        if total_images == 0:
            worker.log.emit("선택한 이미지 포맷에 해당하는 이미지가 없습니다.")
            worker.finished.emit("NG Folder Sorting 완료.")
            return

        worker.log.emit(f"총 복사할 이미지 수: {total_images}")
        processed = 0
        is_stopped = worker.is_stopped

        with ThreadPoolExecutor(max_workers=worker.max_workers, initializer=set_worker_priority) as executor:
            futures: dict = {}
            for inner_id, images in images_to_copy.items():
                if is_stopped():
                    worker.log.emit(f"작업 중지: 처리한 이미지 {processed}")
                    worker.finished.emit(f"작업 중지됨. 처리한 이미지: {processed}")
                    return
                src_dir = os.path.join(source2, inner_id)
                dst_dir = os.path.join(target, inner_id)
                if not worker.ensure_target_folder(dst_dir):
                    continue
                for image in images:
                    if is_stopped():
                        worker.log.emit(f"작업 중지: 처리한 이미지 {processed}")
                        worker.finished.emit(f"작업 중지됨. 처리한 이미지: {processed}")
                        return
                    src_file = os.path.join(src_dir, image)
                    dst_file = os.path.join(dst_dir, image)
                    if os.path.exists(dst_file):
                        worker.log.emit(f"파일 건너뜀: {dst_file}")
                        continue
                    futures[executor.submit(copy_file_chunked, src_file, dst_file, is_stopped)] = (
                        src_file,
                        dst_file,
                    )

            for future in as_completed(futures):
                if is_stopped():
                    worker.log.emit(f"작업 중지: 처리한 이미지 {processed}")
                    worker.finished.emit(f"작업 중지됨. 처리한 이미지: {processed}")
                    return
                result = future.result()
                if result.startswith("오류 발생"):
                    worker.log.emit(result)
                else:
                    processed += 1
                    worker.log.emit(result)
                    worker.progress.emit(min(int(processed / total_images * 100), 100))

        worker.finished.emit(f"NG Folder Sorting 완료. 처리한 이미지: {processed}")
        worker.log.emit("------ NG Folder Sorting 작업 완료 ------")
    except Exception as exc:
        logging.error("NG Folder Sorting 중 오류 발생", exc_info=True)
        worker.log.emit(f"오류 발생: {exc}")
        worker.finished.emit("NG Folder Sorting 중 오류 발생.")


# ---------------------------------------------------------------------------
# 2) Basic Sorting
# ---------------------------------------------------------------------------

def basic_sorting(worker: "WorkerThread", task: dict) -> None:
    from apt.workers.base import set_worker_priority

    worker.log.emit("------ Basic Sorting 작업 시작 ------")
    try:
        source = task["source"]
        target = task["target"]
        inner_id_list_path = task.get("inner_id_list", "")
        use_inner_id = task.get("use_inner_id", False)
        fov_number_input = task.get("fov_number", "").strip()
        inner_id = task.get("inner_id", "").strip()
        formats = task["formats"]
        is_double_path = task.get("double_path_folder", False)
        only_defect_sorting = task.get("only_defect_sorting", False)

        # Inner ID info ----------------------------------------------------
        inner_id_info: list[dict] = []

        if use_inner_id and inner_id:
            inner_id_info.append({"path": inner_id, "name": inner_id, "code": None})
            if is_double_path:
                worker.log.emit(
                    "경고: 'Use Inner ID' 직접 입력 시 'Double Path Folder' 옵션은 무시됩니다."
                )
        elif inner_id_list_path and os.path.isdir(inner_id_list_path):
            try:
                with os.scandir(inner_id_list_path) as it:
                    for entry in it:
                        if not entry.is_dir() or entry.name.lower() in IGNORED_DIRS:
                            continue
                        if is_double_path:
                            code_folder = os.path.join(inner_id_list_path, entry.name)
                            with os.scandir(code_folder) as sub_it:
                                for sub_entry in sub_it:
                                    if sub_entry.is_dir() and sub_entry.name.lower() not in IGNORED_DIRS:
                                        rel_path = os.path.join(entry.name, sub_entry.name)
                                        inner_id_info.append(
                                            {"path": rel_path, "name": sub_entry.name, "code": entry.name}
                                        )
                        else:
                            inner_id_info.append({"path": entry.name, "name": entry.name, "code": None})
            except Exception as exc:
                worker.log.emit(f"Inner ID List Path 오류: {exc}")
                worker.finished.emit("Basic Sorting 중지됨.")
                return
        else:
            worker.log.emit("Inner ID List Path가 유효하지 않거나, 직접 입력된 Inner ID가 없습니다.")
            worker.finished.emit("Basic Sorting 중지됨.")
            return

        if not inner_id_info:
            worker.log.emit("유효한 Inner ID가 없습니다.")
            worker.finished.emit("Basic Sorting 완료.")
            return

        if not os.path.exists(source):
            worker.log.emit(f"Source 경로가 존재하지 않습니다: {source}")
            worker.finished.emit("Basic Sorting 중지됨.")
            return
        if not worker.ensure_target_folder(target):
            worker.finished.emit("Basic Sorting 중지됨.")
            return

        is_stopped = worker.is_stopped

        # --- Only Defect mode -------------------------------------------
        if only_defect_sorting:
            worker.log.emit("Only Defect Image Sorting 모드로 실행합니다.")
            copy_tasks: list[tuple[str, str]] = []
            for info in inner_id_info:
                if is_stopped():
                    break
                template_folder = os.path.join(inner_id_list_path, info["path"])
                fovs_to_find = _get_fovs_from_folder(worker, template_folder)
                if not fovs_to_find:
                    worker.log.emit(
                        f"[{info['name']}] 기준 폴더({template_folder})에 파일이 없어 건너뜁니다."
                    )
                    continue
                worker.log.emit(
                    f"[{info['name']}] 찾을 FOV: {', '.join(sorted(fovs_to_find))}"
                )
                source_folder = os.path.join(source, info["path"])
                matching = _get_matching_files_for_folder(
                    worker, source_folder, formats, fovs_to_find
                )
                for filename in matching:
                    src_file = os.path.join(source_folder, filename)
                    file_base, file_ext = os.path.splitext(filename)
                    prefix = f"{info['code']}_{info['name']}" if info.get("code") else info["name"]
                    new_name = f"{prefix}_{file_base}{file_ext}"
                    copy_tasks.append((src_file, os.path.join(target, new_name)))

            if is_stopped():
                worker.finished.emit("Basic Sorting 중지됨.")
                return

            total = len(copy_tasks)
            if total == 0:
                worker.log.emit("조건에 맞는 이미지를 찾지 못했습니다.")
                worker.finished.emit("Basic Sorting 완료.")
                return

            worker.log.emit(f"총 {total}개의 파일을 복사합니다.")
            processed = 0
            with ThreadPoolExecutor(max_workers=worker.max_workers, initializer=set_worker_priority) as executor:
                futures = [
                    executor.submit(copy_file_chunked, src, dst, is_stopped)
                    for src, dst in copy_tasks
                ]
                for future in as_completed(futures):
                    if is_stopped():
                        break
                    result = future.result()
                    if not result.startswith("오류 발생"):
                        processed += 1
                        worker.log.emit(result)
                        worker.progress.emit(min(int(processed / total * 100), 100))

            if is_stopped():
                worker.finished.emit(f"Basic Sorting 중지됨. ({processed}/{total})")
            else:
                worker.finished.emit(f"Basic Sorting 완료. 총 처리 파일: {processed}")
            worker.log.emit("------ Basic Sorting 작업 완료 ------")
            return

        # --- FOV explicit mode ------------------------------------------
        if fov_number_input:
            fov_numbers = parse_fov_numbers(fov_number_input)
            if not fov_numbers:
                worker.log.emit("유효한 FOV Number가 입력되지 않았습니다.")
                worker.finished.emit("Basic Sorting 중지됨.")
                return

            folder_to_files: dict[str, dict] = {}
            with ThreadPoolExecutor(max_workers=worker.max_workers, initializer=set_worker_priority) as scan_exec:
                future_to_info = {}
                for info in inner_id_info:
                    src_folder = os.path.join(source, info["path"])
                    if os.path.isdir(src_folder):
                        fut = scan_exec.submit(
                            _get_matching_files_for_folder,
                            worker,
                            src_folder,
                            formats,
                            fov_numbers,
                        )
                        future_to_info[fut] = info
                for fut in as_completed(future_to_info):
                    info = future_to_info[fut]
                    matching = fut.result()
                    if matching:
                        folder_to_files[info["path"]] = {"files": matching, "info": info}

            total = sum(len(d["files"]) for d in folder_to_files.values())
            if total == 0:
                worker.log.emit("선택한 FOV Number에 해당하는 이미지가 없습니다.")
                worker.finished.emit("Basic Sorting 완료.")
                return

            processed = 0
            with ThreadPoolExecutor(max_workers=worker.max_workers, initializer=set_worker_priority) as copy_exec:
                futures = []
                for rel_path, data in folder_to_files.items():
                    src_folder = os.path.join(source, rel_path)
                    info = data["info"]
                    for image_file in data["files"]:
                        if is_stopped():
                            break
                        src_file = os.path.join(src_folder, image_file)
                        file_base, file_ext = os.path.splitext(image_file)
                        prefix = f"{info['code']}_{info['name']}" if info.get("code") else info["name"]
                        new_name = f"{prefix}_{file_base}{file_ext}"
                        dst_file = os.path.join(target, new_name)
                        futures.append(copy_exec.submit(copy_file_chunked, src_file, dst_file, is_stopped))
                    if is_stopped():
                        break

                for future in as_completed(futures):
                    if is_stopped():
                        break
                    result = future.result()
                    if not result.startswith("오류 발생"):
                        processed += 1
                        worker.log.emit(result)
                        worker.progress.emit(min(int(processed / total * 100), 100))

            if is_stopped():
                worker.finished.emit(f"Basic Sorting 중지됨. ({processed}/{total})")
            else:
                worker.finished.emit(f"Basic Sorting 완료. 총 처리 파일: {processed}")
            worker.log.emit("------ Basic Sorting 작업 완료 ------")
            return

        # --- No FOV mode (copy all format-matching files) ---------------
        worker.log.emit("FOV 미입력: inner_id_list_path 폴더의 파일 복사 진행")
        folder_to_files = {}
        total = 0
        for info in inner_id_info:
            if is_stopped():
                break
            src_folder = os.path.join(inner_id_list_path, info["path"])
            if not os.path.isdir(src_folder):
                worker.log.emit(f"폴더 없음: {src_folder}")
                continue
            try:
                with os.scandir(src_folder) as it:
                    image_files = [
                        entry.name
                        for entry in it
                        if entry.is_file() and is_valid_file(entry.name, formats)
                    ]
                if image_files:
                    folder_to_files[info["path"]] = {"files": image_files, "info": info}
                    total += len(image_files)
            except Exception as exc:
                worker.log.emit(f"파일 목록 오류: {src_folder} | 에러: {exc}")

        if total == 0:
            worker.log.emit("formats 조건에 맞는 파일 없음.")
            worker.finished.emit("Basic Sorting 완료.")
            return

        processed = 0
        with ThreadPoolExecutor(max_workers=worker.max_workers, initializer=set_worker_priority) as executor:
            futures = []
            for rel_path, data in folder_to_files.items():
                if is_stopped():
                    break
                src_folder = os.path.join(inner_id_list_path, rel_path)
                info = data["info"]
                for image_file in data["files"]:
                    if is_stopped():
                        break
                    src_file = os.path.join(src_folder, image_file)
                    prefix = f"{info['code']}_{info['name']}" if info.get("code") else info["name"]
                    new_name = f"{prefix}_{image_file}"
                    dst_file = os.path.join(target, new_name)
                    futures.append(executor.submit(copy_file_chunked, src_file, dst_file, is_stopped))

            for future in as_completed(futures):
                if is_stopped():
                    break
                result = future.result()
                if not result.startswith("오류 발생"):
                    processed += 1
                    worker.log.emit(result)
                    worker.progress.emit(min(int(processed / total * 100), 100))

        if is_stopped():
            worker.finished.emit(f"Basic Sorting 중지됨. ({processed}/{total})")
        else:
            worker.finished.emit(f"Basic Sorting 완료. 총 처리 파일: {processed}")
        worker.log.emit("------ Basic Sorting 작업 완료 ------")

    except Exception as exc:
        logging.error("Basic Sorting 중 오류", exc_info=True)
        worker.log.emit(f"오류 발생: {exc}")
        worker.finished.emit("작업 중 오류 발생.")


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
from apt.workers.base import register  # noqa: E402

register(OP_NG_SORTING, ng_folder_sorting)
register(OP_BASIC_SORTING, basic_sorting)
