"""BMP -> JPG conversion handler (BTJ)."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from PIL import Image

from apt.constants import OP_BTJ

if TYPE_CHECKING:
    from apt.workers.base import WorkerThread


def _convert_bmp_to_jpg(src: str, dst: str, is_stopped) -> str:
    if is_stopped():
        return "오류 발생: 사용자 중지 요청"
    try:
        with Image.open(src) as img:
            if img.mode == "RGBA":
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            img.save(dst, "JPEG")
        return f"Converted BMP -> JPG: {src} -> {dst}"
    except Exception as exc:
        logging.error(f"BMP->JPG 변환 오류 ({src})", exc_info=True)
        if os.path.exists(dst):
            try:
                os.remove(dst)
            except OSError:
                pass
        return f"오류 발생: {exc}"


def btj_operation(worker: "WorkerThread", task: dict) -> None:
    worker.log.emit("------ BMP TO JPG 작업: BMP -> JPG 변환 시작 ------")
    try:
        source = task.get("source", "").strip()
        target = task.get("target", "").strip()
        if not target:
            target = f"{source}_JPG"

        if not worker.ensure_target_folder(target):
            worker.finished.emit("BMP->JPG 변환 중지됨 (Target 생성 실패).")
            return
        if not os.path.isdir(source):
            worker.log.emit(f"Source 경로가 유효하지 않습니다: {source}")
            worker.finished.emit("BMP->JPG 변환 중지됨.")
            return

        is_stopped = worker.is_stopped
        bmp_files: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(source):
            if is_stopped():
                worker.log.emit("사용자에 의해 중지됨.")
                worker.finished.emit("BMP->JPG 변환 중지됨.")
                return
            for fname in filenames:
                if fname.lower().endswith(".bmp"):
                    bmp_files.append(os.path.join(dirpath, fname))

        total = len(bmp_files)
        if total == 0:
            worker.log.emit("변환할 .bmp 파일이 없습니다.")
            worker.finished.emit("BMP->JPG 변환 완료 (처리 대상 0).")
            return

        worker.log.emit(f"총 변환 대상 BMP 파일: {total}개")
        worker.log.emit(f"Target 폴더: {target}")

        processed = 0
        with ThreadPoolExecutor(max_workers=worker.max_workers) as executor:
            futures = []
            for bmp_path in bmp_files:
                if is_stopped():
                    break
                rel = os.path.relpath(bmp_path, source)
                out_path = os.path.join(target, os.path.splitext(rel)[0] + ".jpg")
                out_dir = os.path.dirname(out_path)
                if out_dir and not os.path.exists(out_dir):
                    os.makedirs(out_dir, exist_ok=True)
                futures.append(executor.submit(_convert_bmp_to_jpg, bmp_path, out_path, is_stopped))

            for future in as_completed(futures):
                if is_stopped():
                    worker.log.emit(
                        f"사용자 중지 요청으로 작업 중단. 현재까지 {processed}개 변환 완료."
                    )
                    worker.finished.emit("BMP->JPG 변환 중단됨.")
                    return
                result = future.result()
                if result.startswith("오류 발생"):
                    worker.log.emit(result)
                else:
                    processed += 1
                    worker.log.emit(result)
                    worker.progress.emit(min(int(processed / total * 100), 100))

        worker.log.emit("BMP->JPG 변환 작업 완료")
        worker.finished.emit(f"BMP->JPG 변환 완료 (총 {processed}개).")
    except Exception as exc:
        logging.error("BTJ(BMP->JPG 변환) 중 오류", exc_info=True)
        worker.log.emit(f"오류 발생: {exc}")
        worker.finished.emit("BMP->JPG 변환 중 오류 발생.")


from apt.workers.base import register  # noqa: E402

register(OP_BTJ, btj_operation)
