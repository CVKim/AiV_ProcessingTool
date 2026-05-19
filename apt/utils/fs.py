"""Filesystem helpers — chunked copy, target-folder creation, filtered copies.

These are extracted from the legacy ``WorkerThread`` so they can be unit
tested without instantiating Qt threads. They take a ``log`` callable and an
``is_stopped`` callable so that the worker can plug in its own cancellation
flag and progress logging.
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Callable, Iterable

from apt.utils.formats import is_valid_file

LogCallable = Callable[[str], None]
StoppedCallable = Callable[[], bool]

_CHUNK = 1024 * 1024  # 1 MiB


def _noop_log(_: str) -> None: ...


def _never_stopped() -> bool:
    return False


def ensure_target_folder(
    target_path: str,
    log: LogCallable = _noop_log,
) -> bool:
    """Create ``target_path`` if missing. Returns True on success."""
    if os.path.exists(target_path):
        return True
    try:
        os.makedirs(target_path, exist_ok=True)
        log(f"Target 경로 생성: {target_path}")
        return True
    except Exception as exc:  # pragma: no cover - filesystem dependent
        log(f"Target 경로 생성 실패: {target_path} | 에러: {exc}")
        return False


def copy_file_chunked(
    src: str,
    dst: str,
    is_stopped: StoppedCallable = _never_stopped,
) -> str:
    """Copy ``src`` to ``dst`` in 1 MiB chunks honouring ``is_stopped``."""
    if is_stopped():
        return "오류 발생: 사용자 중지 요청"
    try:
        with open(src, "rb") as sf, open(dst, "wb") as df:
            while True:
                if is_stopped():
                    df.close()
                    if os.path.exists(dst):
                        os.remove(dst)
                    return "오류 발생: 사용자 중지 요청"
                data = sf.read(_CHUNK)
                if not data:
                    break
                df.write(data)
        return f"Copied {src} to {dst}"
    except Exception as exc:
        logging.error("파일 복사 오류", exc_info=True)
        if os.path.exists(dst):
            try:
                os.remove(dst)
            except OSError:
                pass
        return f"오류 발생: {exc}"


def copy_folder(src: str, dst: str, is_stopped: StoppedCallable = _never_stopped) -> str:
    if is_stopped():
        return "오류 발생: 사용자 중지 요청"
    try:
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return f"Copied folder {src} to {dst}"
    except Exception as exc:
        logging.error("폴더 복사 오류", exc_info=True)
        return f"오류 발생: {exc}"


def copy_folder_filtered(
    src: str,
    dst: str,
    formats: Iterable[str],
    is_stopped: StoppedCallable = _never_stopped,
) -> str:
    """Copy the immediate files of ``src`` matching ``formats`` into ``dst``."""
    if is_stopped():
        return "오류 발생: 사용자 중지 요청"
    formats_list = list(formats)
    try:
        if not os.path.exists(dst):
            os.makedirs(dst, exist_ok=True)
        count = 0
        with os.scandir(src) as it:
            for entry in it:
                if is_stopped():
                    return "오류 발생: 사용자 중지 요청"
                if entry.is_file() and is_valid_file(entry.name, formats_list):
                    src_file = os.path.join(src, entry.name)
                    dst_file = os.path.join(dst, entry.name)
                    result = copy_file_chunked(src_file, dst_file, is_stopped)
                    if not result.startswith("오류 발생"):
                        count += 1
        return f"Copied {count} file(s) from {src} to {dst} (filtered)"
    except Exception as exc:
        logging.error("Filtered folder copy 오류", exc_info=True)
        return f"오류 발생: {exc}"
