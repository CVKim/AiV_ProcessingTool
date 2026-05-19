"""Dummy directory tree factories for AIVEX worker tests.

These build the minimum filesystem shape each worker expects so that tests
can exercise the real handlers without needing a network share or production
dataset.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def _write_bmp(path: Path, size: tuple[int, int] = (32, 32), color=(255, 0, 0)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "BMP")


def make_bmp_tree(root: Path) -> Path:
    """Create three BMP files in a small nested tree.

    Layout::

        <root>/source/
            top.bmp
            sub/
                1_a.bmp
                2_b.bmp
    """
    src = root / "source"
    _write_bmp(src / "top.bmp")
    _write_bmp(src / "sub" / "1_a.bmp")
    _write_bmp(src / "sub" / "2_b.bmp", color=(0, 255, 0))
    return src


def make_ng_count_tree(root: Path) -> Path:
    """Build a minimal NG folder layout::

        <root>/lot01/
            ng/
                Cam_01/Defect_A/<3 defect folders>
                Cam_01/Defect_B/<1 defect folder>
                Cam_02/Defect_A/<2 defect folders>
    """
    base = root / "lot01" / "ng"
    layout = {
        ("Cam_01", "Defect_A"): 3,
        ("Cam_01", "Defect_B"): 1,
        ("Cam_02", "Defect_A"): 2,
    }
    for (cam, defect), n in layout.items():
        for i in range(n):
            (base / cam / defect / f"item_{i:02d}").mkdir(parents=True, exist_ok=True)
    # Sibling folders excluded from the "top folders" count.
    (root / "lot01" / "ok").mkdir(parents=True, exist_ok=True)
    (root / "lot01" / "ng_info").mkdir(parents=True, exist_ok=True)
    (root / "lot01" / "extra_top").mkdir(parents=True, exist_ok=True)
    return base


def make_basic_sorting_tree(root: Path) -> dict:
    """Inner-ID list + source folder mirror used by basic_sorting.

    Returns the paths a Basic Sorting task expects::

        {'inner_id_list': ..., 'source': ..., 'target': ..., 'ids': [...]}
    """
    inner = root / "inner"
    src = root / "src"
    target = root / "target"
    ids = ["ID001", "ID002"]
    for ident in ids:
        # Empty placeholder in inner-id list (only the directory is needed).
        (inner / ident).mkdir(parents=True, exist_ok=True)
        _write_bmp(src / ident / f"1_{ident}.bmp")
        _write_bmp(src / ident / f"2_{ident}.bmp")
    target.mkdir(parents=True, exist_ok=True)
    return {
        "inner_id_list": str(inner),
        "source": str(src),
        "target": str(target),
        "ids": ids,
    }
