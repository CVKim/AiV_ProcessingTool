"""Resolve bundled sample images.

The Preprocessing panel ships with a couple of demo images so first-time
users can try the node graph immediately, without having to provide their
own data. This module returns the on-disk paths to those images, working
in both:

  * **dev mode** — running from source, samples live at ``<repo>/sample/``
  * **frozen mode** — PyInstaller build, samples land in the bundle's
    ``_internal/sample/`` (referenced via ``sys._MEIPASS``)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SAMPLE_DIR_NAME = "sample"
SAMPLE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")


def find_sample_dir() -> Path | None:
    """Return the directory holding the bundled sample images, or None."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / SAMPLE_DIR_NAME)
    here = Path(__file__).resolve().parent
    candidates.extend([
        here.parent / SAMPLE_DIR_NAME,                 # repo root / sample
        here / SAMPLE_DIR_NAME,                        # apt/sample (fallback)
        Path.cwd() / SAMPLE_DIR_NAME,                  # current dir
    ])
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def sample_image_paths() -> list[str]:
    """Sorted list of absolute paths to every supported sample image."""
    folder = find_sample_dir()
    if folder is None:
        return []
    paths: list[str] = []
    for entry in sorted(folder.iterdir()):
        if entry.is_file() and entry.suffix.lower() in SAMPLE_EXTENSIONS:
            paths.append(str(entry))
    return paths
