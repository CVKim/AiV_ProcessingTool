"""Crop handler — supports BMP + JSON pair cropping and debug overlays."""

from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFile, ImageOps

from apt.constants import IGNORED_DIRS, OP_CROP
from apt.utils.formats import is_valid_file
from apt.utils.fov import parse_fov_numbers

ImageFile.LOAD_TRUNCATED_IMAGES = True

if TYPE_CHECKING:
    from apt.workers.base import WorkerThread


# ---------------------------------------------------------------------------
# Crop primitives
# ---------------------------------------------------------------------------

def _crop_image(src: str, dst: str, crop_coords: tuple[int, int, int, int], is_stopped) -> str:
    if is_stopped():
        return "오류 발생: 사용자 중지 요청"
    try:
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)
            img.load()
            w, h = img.size
            x1, y1, x2, y2 = crop_coords
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            x1 = max(0, min(x1, w))
            y1 = max(0, min(y1, h))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))
            if x2 <= x1 or y2 <= y1:
                return f"SKIP: 크롭 영역이 유효하지 않음 (img={w}x{h}, box={crop_coords})"
            cropped = img.crop((x1, y1, x2, y2))
            try:
                cropped.save(dst)
            except OSError:
                cropped = cropped.convert("RGB")
                cropped.save(dst)
            return f"Cropped {src} -> {dst} (img={w}x{h}, box=({x1},{y1},{x2},{y2}))"
    except Exception as exc:
        logging.error(f"이미지 크롭 오류: {src}", exc_info=True)
        return f"오류 발생: {exc}"


def _adjust_and_save_json(
    src_json_path: str,
    dst_json_path: str,
    crop_box: tuple[int, int, int, int],
    new_size: tuple[int, int],
    new_image_filename: str,
    debug_draw_path: str | None = None,
    debug_base_image_path: str | None = None,
) -> None:
    with open(src_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    x1, y1, _x2, _y2 = crop_box
    new_w, new_h = new_size

    for shp in data.get("shapes", []):
        pts = shp.get("points", [])
        shape_type = (shp.get("shape_type") or "").lower()
        adj_pts = []
        for p in pts:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                continue
            nx = max(0.0, min(float(p[0]) - float(x1), float(new_w)))
            ny = max(0.0, min(float(p[1]) - float(y1), float(new_h)))
            adj_pts.append([nx, ny])
        if adj_pts:
            shp["points"] = adj_pts

        bbox = shp.get("bbox") if isinstance(shp.get("bbox"), dict) else None

        if shape_type == "point":
            if bbox is not None:
                old_x = float(bbox.get("x", adj_pts[0][0] if adj_pts else 0))
                old_y = float(bbox.get("y", adj_pts[0][1] if adj_pts else 0))
                old_w = float(bbox.get("width", 0) or 0.0)
                old_h = float(bbox.get("height", 0) or 0.0)
                nx = max(0.0, min(old_x - float(x1), float(new_w)))
                ny = max(0.0, min(old_y - float(y1), float(new_h)))
                if old_w > 0 and old_h > 0:
                    nx2 = min(nx + old_w, float(new_w))
                    ny2 = min(ny + old_h, float(new_h))
                    old_w = max(0.0, nx2 - nx)
                    old_h = max(0.0, ny2 - ny)
                bbox["x"] = nx
                bbox["y"] = ny
                bbox["width"] = old_w
                bbox["height"] = old_h
                shp["bbox"] = bbox
        elif bbox and float(bbox.get("width", 0)) == 0.0 and float(bbox.get("height", 0)) == 0.0 and len(adj_pts) == 1:
            bbox["x"] = float(adj_pts[0][0])
            bbox["y"] = float(adj_pts[0][1])
            bbox["width"] = 0.0
            bbox["height"] = 0.0
        else:
            xs = [p[0] for p in adj_pts]
            ys = [p[1] for p in adj_pts]
            if xs and ys:
                minx, maxx = max(0.0, min(xs)), min(float(new_w), max(xs))
                miny, maxy = max(0.0, min(ys)), min(float(new_h), max(ys))
                if bbox is not None:
                    bbox["x"] = float(minx)
                    bbox["y"] = float(miny)
                    bbox["width"] = float(max(0.0, maxx - minx))
                    bbox["height"] = float(max(0.0, maxy - miny))

    rois = data.get("rois", None)
    if isinstance(rois, list):
        new_rois = []
        for item in rois:
            if isinstance(item, (list, tuple)) and len(item) >= 4:
                rx1 = max(0, min(int(item[0]) - int(x1), new_w))
                ry1 = max(0, min(int(item[1]) - int(y1), new_h))
                rx2 = max(0, min(int(item[2]) - int(x1), new_w))
                ry2 = max(0, min(int(item[3]) - int(y1), new_h))
                if rx2 < rx1:
                    rx1, rx2 = rx2, rx1
                if ry2 < ry1:
                    ry1, ry2 = ry2, ry1
                new_rois.append([rx1, ry1, rx2, ry2])
            else:
                new_rois.append(item)
        data["rois"] = new_rois

    data["imagePath"] = new_image_filename
    data["imageWidth"] = int(new_w)
    data["imageHeight"] = int(new_h)

    with open(dst_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    if debug_draw_path and debug_base_image_path:
        try:
            _draw_debug_labels(debug_base_image_path, data, debug_draw_path)
        except Exception:
            logging.error("디버그 드로잉 오류", exc_info=True)


def _draw_debug_labels(image_path: str, data: dict, save_path: str) -> None:
    with Image.open(image_path) as im:
        draw = ImageDraw.Draw(im)
        for shp in data.get("shapes", []):
            pts = shp.get("points", [])
            shape_type = (shp.get("shape_type") or "").lower()
            if shape_type == "point" and isinstance(pts, list) and len(pts) == 1:
                cx, cy = float(pts[0][0]), float(pts[0][1])
                r = 4
                try:
                    draw.ellipse([cx - r, cy - r, cx + r, cy + r], width=2)
                except Exception:
                    pass
            elif isinstance(pts, list) and len(pts) >= 2:
                try:
                    draw.line([tuple(p) for p in pts] + [tuple(pts[0])], width=2)
                except Exception:
                    pass
            bbox = shp.get("bbox")
            if isinstance(bbox, dict):
                x = float(bbox.get("x", 0))
                y = float(bbox.get("y", 0))
                w = float(bbox.get("width", 0))
                h = float(bbox.get("height", 0))
                x2, y2 = x + w, y + h
                try:
                    if w == 0.0 and h == 0.0:
                        rr = 5
                        draw.ellipse([x - rr, y - rr, x + rr, y + rr], width=1)
                    else:
                        draw.rectangle([x, y, x2, y2], width=2)
                except Exception:
                    pass
        try:
            im.save(save_path)
        except OSError:
            im.convert("RGB").save(save_path)


def _crop_image_and_json_pair(
    src_img: str,
    dst_img: str,
    src_json: str,
    dst_json: str,
    crop_coords: tuple[int, int, int, int],
    debug_draw_path: str,
) -> str:
    try:
        with Image.open(src_img) as img:
            img = ImageOps.exif_transpose(img)
            img.load()
            x1, y1, x2, y2 = crop_coords
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            w, h = img.size
            x1 = max(0, min(x1, w))
            y1 = max(0, min(y1, h))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))
            if x2 <= x1 or y2 <= y1:
                return f"SKIP: 크롭 영역이 유효하지 않음 (img={w}x{h}, box=({x1},{y1},{x2},{y2}))"
            cropped = img.crop((x1, y1, x2, y2))
            try:
                cropped.save(dst_img)
            except OSError:
                cropped = cropped.convert("RGB")
                cropped.save(dst_img)
            new_w, new_h = cropped.size

        _adjust_and_save_json(
            src_json_path=src_json,
            dst_json_path=dst_json,
            crop_box=(x1, y1, x2, y2),
            new_size=(new_w, new_h),
            new_image_filename=os.path.basename(dst_img),
            debug_draw_path=debug_draw_path,
            debug_base_image_path=dst_img,
        )
        return f"Cropped+JSON {src_img} -> {dst_img}, JSON -> {dst_json}"
    except Exception as exc:
        logging.error("crop_image_and_json_pair 오류", exc_info=True)
        for p in (dst_img, dst_json, debug_draw_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        return f"오류 발생: {exc}"


def _collect_crop_candidates(
    root_folder: str,
    formats: list[str],
    fov_numbers: set[str] | None = None,
) -> list[tuple[str, str]]:
    collected: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root_folder):
        dirnames[:] = [d for d in dirnames if d.lower() not in IGNORED_DIRS]
        folder_name = os.path.basename(dirpath)
        if folder_name.lower() in IGNORED_DIRS:
            continue
        rel_path = os.path.relpath(dirpath, root_folder)
        parts = rel_path.split(os.sep)
        inner_id = parts[0] if parts else folder_name
        for fname in filenames:
            if not is_valid_file(fname, formats):
                continue
            if fov_numbers:
                prefix = fname.split("_", 1)[0].lower()
                digits = re.sub(r"[^0-9]", "", prefix)
                if digits not in fov_numbers:
                    continue
            collected.append((os.path.join(dirpath, fname), inner_id))
    return collected


# ---------------------------------------------------------------------------
# Public handler
# ---------------------------------------------------------------------------

def crop_images(worker: "WorkerThread", task: dict) -> None:
    from apt.workers.base import set_worker_priority

    worker.log.emit("------ Crop 작업 시작 ------")
    try:
        source = task["source"]
        target = task["target"]
        formats = task["formats"]
        fov_text = task.get("fov_number", "").strip()

        try:
            x1 = int(task["left_top_x"])
            y1 = int(task["left_top_y"])
            x2 = int(task["right_bottom_x"])
            y2 = int(task["right_bottom_y"])
            if task.get("coords_mode", "ltrb") == "xywh":
                start_x, start_y, width, height = x1, y1, x2, y2
                if width < 0 or height < 0:
                    worker.log.emit(
                        f"경고: width/height가 음수입니다. 절대값으로 보정합니다 (w={width}, h={height})"
                    )
                    width, height = abs(width), abs(height)
                if width == 0 or height == 0:
                    worker.log.emit("경고: width/height가 0입니다. 크롭을 중지합니다.")
                    worker.finished.emit("Crop 중지됨.")
                    return
                x1, y1 = start_x, start_y
                x2, y2 = start_x + width, start_y + height
        except Exception as exc:
            worker.log.emit(f"Crop 좌표 오류: {exc}")
            worker.finished.emit("Crop 중지됨.")
            return

        fov_numbers = parse_fov_numbers(fov_text) if fov_text else None

        if not os.path.exists(source):
            worker.log.emit(f"Source 경로 없음: {source}")
            worker.finished.emit("Crop 중지됨.")
            return
        if not worker.ensure_target_folder(target):
            worker.finished.emit("Crop 중지됨.")
            return

        all_files = _collect_crop_candidates(source, formats, fov_numbers)
        total = len(all_files)
        if total == 0:
            worker.log.emit("조건에 맞는 이미지 없음")
            worker.finished.emit("Crop 완료.")
            return

        worker.log.emit(f"총 Crop 대상 이미지 수: {total}")
        crop_coords = (x1, y1, x2, y2)
        worker.log.emit(f"Crop 영역(LTRB): {crop_coords}")

        is_stopped = worker.is_stopped
        processed = 0
        with ThreadPoolExecutor(max_workers=worker.max_workers, initializer=set_worker_priority) as executor:
            futures = []
            for file_path, inner_id in all_files:
                if is_stopped():
                    worker.log.emit(f"작업 중지: 처리 이미지 {processed}")
                    worker.finished.emit(f"작업 중지됨. 처리 이미지: {processed}")
                    return

                orig_filename = os.path.basename(file_path)
                file_base, file_ext = os.path.splitext(orig_filename)
                use_prefix = os.path.dirname(file_path) != source
                new_filename = f"{inner_id}_{orig_filename}" if use_prefix else orig_filename
                dst_file = os.path.join(target, new_filename)

                src_dir = os.path.dirname(file_path)
                json_path = os.path.join(src_dir, f"{file_base}.json")
                if file_ext.lower() == ".bmp" and os.path.isfile(json_path):
                    new_base = os.path.splitext(new_filename)[0]
                    dst_json = os.path.join(target, f"{new_base}.json")
                    debug_path = os.path.join(target, f"{new_base}_draw.bmp")
                    futures.append(
                        executor.submit(
                            _crop_image_and_json_pair,
                            file_path, dst_file, json_path, dst_json, crop_coords, debug_path,
                        )
                    )
                else:
                    futures.append(
                        executor.submit(_crop_image, file_path, dst_file, crop_coords, is_stopped)
                    )

            for future in as_completed(futures):
                if is_stopped():
                    worker.log.emit(f"작업 중지: 처리 이미지 {processed}")
                    worker.finished.emit(f"작업 중지됨. 처리 이미지: {processed}")
                    return
                result = future.result()
                if result:
                    processed += 1
                    worker.log.emit(result)
                    worker.progress.emit(min(int(processed / total * 100), 100))

        worker.finished.emit(f"Crop 완료. 처리 이미지: {processed}")
        worker.log.emit("------ Crop 작업 완료 ------")
    except Exception as exc:
        logging.error("Crop 중 오류 발생", exc_info=True)
        worker.log.emit(f"오류 발생: {exc}")
        worker.finished.emit("Crop 중 오류 발생.")


from apt.workers.base import register  # noqa: E402

register(OP_CROP, crop_images)
