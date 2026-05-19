"""Category palette and short descriptions for preprocessing operations.

Centralised here so the operations sidebar, node items, and edge colors stay
in lock-step. Each entry maps a category name to:

    color    — hex string used for node title bar, accent stripe, and edges
    icon     — single-character glyph (no font file required)
    hint     — one-sentence description shown next to the category header
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryStyle:
    color: str
    icon: str
    hint: str


CATEGORY_STYLES: dict[str, CategoryStyle] = {
    "Geometry":   CategoryStyle("#5BA9F5", "⬚", "Resize / rotate / flip"),
    "Color":      CategoryStyle("#C77DFF", "◐", "Tone, channel and brightness"),
    "Filter":     CategoryStyle("#4FD1C5", "≈", "Smoothing and sharpening"),
    "Threshold":  CategoryStyle("#F6BE2B", "◑", "Binarisation"),
    "Edge":       CategoryStyle("#E5484D", "✦", "Edge / gradient detectors"),
    "Morphology": CategoryStyle("#33B66B", "▣", "Erode / dilate / open / close"),
    "Histogram":  CategoryStyle("#FF7029", "▥", "Equalise / CLAHE"),
    "Combine":    CategoryStyle("#EC4899", "⊕", "Take two inputs, produce one"),
}

# Origin gets its own style — distinct from any op category.
ORIGIN_STYLE = CategoryStyle("#33B66B", "▶", "Source image")


def style_for(category: str) -> CategoryStyle:
    return CATEGORY_STYLES.get(category, CategoryStyle("#FF7029", "•", ""))


def short_hint(op_key: str, params: dict) -> str:
    """Render a one-line parameter summary for a node (e.g. ``ksize=5  σ=0``)."""
    if not params:
        return ""
    pieces: list[str] = []
    for k, v in params.items():
        if isinstance(v, float):
            pieces.append(f"{k}={v:g}")
        elif isinstance(v, bool):
            if v:
                pieces.append(k)
        else:
            pieces.append(f"{k}={v}")
    text = "  ".join(pieces)
    return text if len(text) <= 38 else text[:35] + "…"
