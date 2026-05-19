"""Attach FOV handler — pairs FOV images across two trees side-by-side."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from apt.constants import IGNORED_DIRS, OP_ATTACH_FOV
from apt.utils.fov import parse_fov_numbers

if TYPE_CHECKING:
    from apt.workers.base import WorkerThread


def _recursive_find_fov_images(root_folder: str) -> dict[tuple[str, str], list[str]]:
    result: dict[tuple[str, str], list[str]] = {}
    for dirpath, dirnames, filenames in os.walk(root_folder):
        dirnames[:] = [d for d in dirnames if d.lower() not in IGNORED_DIRS]
        folder_name = os.path.basename(dirpath)
        if folder_name.lower() in IGNORED_DIRS:
            continue
        last15 = folder_name[-15:] if len(folder_name) >= 15 else folder_name
        for filename in filenames:
            lname = filename.lower()
            if lname.startswith("fov") and lname.endswith(".jpg"):
                digits = "".join(filter(str.isdigit, lname.replace("fov", "")))
                if not digits:
                    continue
                key = (last15, digits)
                result.setdefault(key, []).append(os.path.join(dirpath, filename))
    return result


def _attach_two_images(
    src1: str, src2: str, key: tuple[str, str], target: str, is_stopped
) -> str:
    if is_stopped():
        return "오류 발생: 사용자 중지 요청"
    try:
        last15, fovnum = key
        im1 = Image.open(src1)
        im2 = Image.open(src2)
        width = im1.width + im2.width
        height = max(im1.height, im2.height)
        new_img = Image.new("RGB", (width, height), (255, 255, 255))
        new_img.paste(im1, (0, 0))
        new_img.paste(im2, (im1.width, 0))
        draw = ImageDraw.Draw(new_img)
        font = ImageFont.load_default()
        draw.text((10, 10), f"{os.path.basename(src1)}\nfov:{fovnum}", fill=(0, 0, 0), font=font)
        draw.text(
            (im1.width + 10, 10), f"{os.path.basename(src2)}\nfov:{fovnum}", fill=(0, 0, 0), font=font
        )
        out_path = os.path.join(target, f"attached_{last15}_{fovnum}.jpg")
        new_img.save(out_path)
        return f"Attached: {src1} + {src2} => {out_path}"
    except Exception as exc:
        logging.error("attach_two_images 오류", exc_info=True)
        return f"오류 발생: {exc}"


def attach_fov(worker: "WorkerThread", task: dict) -> None:
    from apt.workers.base import set_worker_priority

    worker.log.emit("------ Attach FOV 작업 시작 ------")
    try:
        search1 = task.get("search1", "")
        search2 = task.get("search2", "")
        target = task.get("target", "")
        fov_text = task.get("fov_number", "").strip()

        if not os.path.isdir(search1) or not os.path.isdir(search2):
            worker.log.emit("Search Folder Path 오류")
            worker.finished.emit("Attach FOV 중지됨.")
            return
        if not worker.ensure_target_folder(target):
            worker.finished.emit("Attach FOV 중지됨.")
            return

        fov_numbers = parse_fov_numbers(fov_text) if fov_text else None

        dict1 = _recursive_find_fov_images(search1)
        dict2 = _recursive_find_fov_images(search2)
        intersection_keys = set(dict1.keys()) & set(dict2.keys())
        if fov_numbers is not None:
            intersection_keys = {k for k in intersection_keys if k[1] in fov_numbers}
        if not intersection_keys:
            worker.log.emit("교집합 fov 이미지 없음")
            worker.finished.emit("Attach FOV 완료.")
            return

        total = sum(min(len(dict1[k]), len(dict2[k])) for k in intersection_keys)
        worker.log.emit(f"총 attach 건수: {total}")
        is_stopped = worker.is_stopped
        processed = 0

        with ThreadPoolExecutor(max_workers=worker.max_workers, initializer=set_worker_priority) as executor:
            futures = []
            for key in intersection_keys:
                a, b = dict1[key], dict2[key]
                for i in range(min(len(a), len(b))):
                    futures.append(executor.submit(_attach_two_images, a[i], b[i], key, target, is_stopped))
            for future in as_completed(futures):
                if is_stopped():
                    worker.log.emit(f"작업 중지: 처리 이미지 쌍 {processed}")
                    worker.finished.emit(f"Attach FOV 중지됨. 처리 이미지 쌍: {processed}")
                    return
                result = future.result()
                if result.startswith("오류 발생"):
                    worker.log.emit(result)
                else:
                    processed += 1
                    worker.log.emit(result)
                    worker.progress.emit(min(int(processed / total * 100), 100))

        worker.finished.emit(f"Attach FOV 완료. 처리 이미지 쌍: {processed}")
        worker.log.emit("------ Attach FOV 작업 완료 ------")
    except Exception as exc:
        logging.error("Attach FOV 오류", exc_info=True)
        worker.log.emit(f"오류 발생: {exc}")
        worker.finished.emit("Attach FOV 중 오류 발생.")


from apt.workers.base import register  # noqa: E402

register(OP_ATTACH_FOV, attach_fov)
