"""Shared constants for AIVEX Processing Tool.

Centralises format codes, ignored folder names, and the operation registry.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Format codes used by every file-picker dialog. The string values are what
# the workers compare against ``filename.lower()`` (or special-cased for
# org_jpg / fov_jpg).
# ---------------------------------------------------------------------------

FORMAT_CHOICES: list[tuple[str, str]] = [
    ("MIM", ".mim"),
    ("fov_jpg", "fov_jpg"),
    ("org_jpg", "org_jpg"),
    ("BMP", ".bmp"),
    ("PNG", ".png"),
]

# Folder names that should never be treated as dataset content.
IGNORED_DIRS: frozenset[str] = frozenset(
    {"ok", "ng", "ng_info", "crop", "thumbnail"}
)

# ---------------------------------------------------------------------------
# Operation identifiers (the ``operation`` field in worker task dicts).
# Keep these in lock-step with apt/workers/base.OPERATION_REGISTRY.
# ---------------------------------------------------------------------------

OP_NG_SORTING = "ng_sorting"
OP_DATE_COPY = "date_copy"
OP_IMAGE_COPY = "image_copy"
OP_SIMULATION = "simulation_foldering"
OP_BASIC_SORTING = "basic_sorting"
OP_NG_COUNT = "ng_count"
OP_CROP = "crop"
OP_ATTACH_FOV = "attach_fov"
OP_MIM_TO_BMP = "mim_to_bmp"
OP_BTJ = "btj"
