"""FOV-number parsing utilities.

The legacy expressions ``1,2,3`` and ``1,2,3/5`` (range) are both accepted.
``parse_fov_numbers`` returns ``None`` for an empty / invalid input to mirror
the original worker behavior (callers branch on ``if fov_numbers is None``).
"""

from __future__ import annotations

import re


def parse_fov_numbers(text: str | None) -> set[str] | None:
    """Parse a comma-separated FOV expression to a set of digit strings.

    >>> parse_fov_numbers("1,2,3")
    {'1', '2', '3'}
    >>> parse_fov_numbers("1,2,3/5")
    {'1', '2', '3', '4', '5'}
    >>> parse_fov_numbers("")
    """
    if not text:
        return None

    results: set[str] = set()
    for raw in (p.strip() for p in text.split(",") if p.strip()):
        if "/" in raw:
            try:
                start_s, end_s = raw.split("/", 1)
                start_i = int(start_s.strip())
                end_i = int(end_s.strip())
            except ValueError:
                continue
            if start_i <= end_i:
                results.update(str(n) for n in range(start_i, end_i + 1))
        elif raw.isdigit():
            results.add(raw)

    return results or None


def extract_fov_from_filename(filename: str) -> str | None:
    """Return the leading numeric prefix of ``filename`` (before the first ``_``).

    >>> extract_fov_from_filename("12_image.bmp")
    '12'
    >>> extract_fov_from_filename("FOV_007.jpg") is None
    True
    """
    if not filename:
        return None
    prefix = filename.split("_", 1)[0]
    digits = re.sub(r"[^0-9]", "", prefix)
    return digits or None
