"""Image format matching — preserves the original legacy semantics:

``org_jpg``
    matches ``*.jpg`` whose basename does **not** contain ``fov``.
``fov_jpg``
    matches ``*.jpg`` whose basename **does** contain ``fov``.

All other tokens are treated as plain suffix checks (case-insensitive).
"""

from __future__ import annotations

import os


def is_valid_file(filename: str, formats: list[str] | None) -> bool:
    if not formats:
        return False

    fname_lower = filename.lower()
    base, ext = os.path.splitext(fname_lower)

    for fmt in formats:
        fmt_lower = fmt.lower()
        if fmt_lower == "org_jpg":
            if ext == ".jpg" and "fov" not in base:
                return True
        elif fmt_lower == "fov_jpg":
            if ext == ".jpg" and "fov" in base:
                return True
        else:
            if fname_lower.endswith(fmt_lower):
                return True
    return False
