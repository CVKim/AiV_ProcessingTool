"""Image preprocessing operation registry.

Every operation declares:
    * ``key`` — stable identifier used in pipeline / persistence
    * ``label`` — human-readable name shown in the UI
    * ``category`` — grouped in the operations sidebar
    * ``inputs`` — how many input images it consumes (1 or 2)
    * ``params`` — list of :class:`ParamSpec` describing tweakable inputs
    * ``fn`` — pure function ``(images: list[ndarray], **params) -> ndarray``

All images use ``numpy.uint8`` arrays. Single-channel results are kept 2-D so
callers can decide when to broadcast back to BGR for compositing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Parameter & operation descriptors
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParamSpec:
    """Describes one tweakable parameter of an :class:`Operation`."""

    name: str
    label: str
    kind: str                # "int" | "float" | "bool" | "choice"
    default: Any
    min: float | None = None
    max: float | None = None
    step: float = 1
    choices: tuple[str, ...] | None = None  # for kind == "choice"
    hint: str = ""

    def coerce(self, value: Any) -> Any:
        if self.kind == "int":
            return int(value)
        if self.kind == "float":
            return float(value)
        if self.kind == "bool":
            return bool(value)
        if self.kind == "choice":
            return str(value)
        return value


@dataclass(frozen=True)
class Operation:
    key: str
    label: str
    category: str
    inputs: int
    fn: Callable[..., np.ndarray]
    params: tuple[ParamSpec, ...] = field(default_factory=tuple)
    hint: str = ""

    def defaults(self) -> dict[str, Any]:
        return {p.name: p.default for p in self.params}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_uint8(img: np.ndarray) -> np.ndarray:
    if img.dtype == np.uint8:
        return img
    if img.dtype in (np.float32, np.float64):
        return np.clip(img * 255 if img.max() <= 1.0 else img, 0, 255).astype(np.uint8)
    return np.clip(img, 0, 255).astype(np.uint8)


def _ensure_bgr(img: np.ndarray) -> np.ndarray:
    """Promote single-channel images to 3-channel BGR for compositing."""
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.ndim == 3 and img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img


def _match_shape(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Resize ``b`` to ``a``'s height/width if they differ, and align channels."""
    a = _ensure_bgr(a)
    b = _ensure_bgr(b)
    if a.shape[:2] != b.shape[:2]:
        b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)
    return a, b


def _to_odd(n: int, minimum: int = 1) -> int:
    n = max(int(n), minimum)
    return n if n % 2 == 1 else n + 1


# ---------------------------------------------------------------------------
# 1-input operations
# ---------------------------------------------------------------------------

def op_identity(images, **_):
    return images[0]


def op_resize(images, width: int = 0, height: int = 0, scale: float = 1.0):
    img = images[0]
    h, w = img.shape[:2]
    tw = int(width) if width > 0 else int(round(w * scale))
    th = int(height) if height > 0 else int(round(h * scale))
    tw = max(1, tw)
    th = max(1, th)
    interp = cv2.INTER_AREA if (tw * th) < (w * h) else cv2.INTER_CUBIC
    return cv2.resize(img, (tw, th), interpolation=interp)


def op_rotate(images, angle: float = 0.0, keep_size: bool = True):
    img = images[0]
    h, w = img.shape[:2]
    center = (w / 2.0, h / 2.0)
    matrix = cv2.getRotationMatrix2D(center, float(angle), 1.0)
    if keep_size:
        return cv2.warpAffine(img, matrix, (w, h), borderValue=(0, 0, 0))
    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])
    nw = int(h * sin + w * cos)
    nh = int(h * cos + w * sin)
    matrix[0, 2] += (nw / 2.0) - center[0]
    matrix[1, 2] += (nh / 2.0) - center[1]
    return cv2.warpAffine(img, matrix, (nw, nh), borderValue=(0, 0, 0))


def op_flip(images, direction: str = "horizontal"):
    img = images[0]
    code = {"horizontal": 1, "vertical": 0, "both": -1}.get(direction, 1)
    return cv2.flip(img, code)


def op_to_gray(images):
    img = images[0]
    if img.ndim == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def op_invert(images):
    return cv2.bitwise_not(images[0])


def op_brightness_contrast(images, brightness: int = 0, contrast: float = 1.0):
    img = images[0].astype(np.float32)
    img = img * float(contrast) + float(brightness)
    return _ensure_uint8(img)


def op_gamma(images, gamma: float = 1.0):
    img = images[0]
    g = max(float(gamma), 1e-3)
    table = np.array([((i / 255.0) ** (1.0 / g)) * 255 for i in range(256)]).astype(np.uint8)
    return cv2.LUT(img, table)


def op_gaussian_blur(images, ksize: int = 5, sigma: float = 0.0):
    k = _to_odd(ksize, 1)
    return cv2.GaussianBlur(images[0], (k, k), float(sigma))


def op_median_blur(images, ksize: int = 5):
    k = _to_odd(ksize, 3)
    return cv2.medianBlur(images[0], k)


def op_bilateral(images, d: int = 9, sigma_color: float = 75.0, sigma_space: float = 75.0):
    return cv2.bilateralFilter(images[0], int(d), float(sigma_color), float(sigma_space))


def op_box_blur(images, ksize: int = 5):
    k = max(int(ksize), 1)
    return cv2.blur(images[0], (k, k))


def op_sharpen(images, amount: float = 1.0):
    img = images[0]
    blurred = cv2.GaussianBlur(img, (0, 0), 3)
    return cv2.addWeighted(img, 1 + float(amount), blurred, -float(amount), 0)


def op_threshold_binary(images, thresh: int = 127, max_value: int = 255, invert: bool = False):
    img = _ensure_bgr(images[0])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mode = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    _, out = cv2.threshold(gray, int(thresh), int(max_value), mode)
    return out


def op_threshold_otsu(images, invert: bool = False):
    img = _ensure_bgr(images[0])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mode = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    _, out = cv2.threshold(gray, 0, 255, mode | cv2.THRESH_OTSU)
    return out


def op_threshold_adaptive(
    images,
    method: str = "gaussian",
    block_size: int = 11,
    C: int = 2,
    invert: bool = False,
):
    img = _ensure_bgr(images[0])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    adaptive = (
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C if method == "gaussian" else cv2.ADAPTIVE_THRESH_MEAN_C
    )
    mode = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    block = _to_odd(block_size, 3)
    return cv2.adaptiveThreshold(gray, 255, adaptive, mode, block, int(C))


def op_canny(images, threshold1: int = 100, threshold2: int = 200):
    img = _ensure_bgr(images[0])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Canny(gray, int(threshold1), int(threshold2))


def op_sobel(images, ksize: int = 3, direction: str = "both"):
    img = _ensure_bgr(images[0])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    k = _to_odd(ksize, 1)
    if direction == "x":
        out = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=k)
    elif direction == "y":
        out = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=k)
    else:
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=k)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=k)
        out = cv2.magnitude(gx, gy)
    out = np.absolute(out)
    out = np.clip(out, 0, 255).astype(np.uint8)
    return out


def op_laplacian(images, ksize: int = 3):
    img = _ensure_bgr(images[0])
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    k = _to_odd(ksize, 1)
    out = cv2.Laplacian(gray, cv2.CV_64F, ksize=k)
    return np.clip(np.absolute(out), 0, 255).astype(np.uint8)


def _morph(images, op_flag: int, ksize: int, iterations: int):
    k = max(int(ksize), 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    return cv2.morphologyEx(images[0], op_flag, kernel, iterations=max(int(iterations), 1))


def op_erode(images, ksize: int = 3, iterations: int = 1):
    return _morph(images, cv2.MORPH_ERODE, ksize, iterations)


def op_dilate(images, ksize: int = 3, iterations: int = 1):
    return _morph(images, cv2.MORPH_DILATE, ksize, iterations)


def op_open(images, ksize: int = 3, iterations: int = 1):
    return _morph(images, cv2.MORPH_OPEN, ksize, iterations)


def op_close(images, ksize: int = 3, iterations: int = 1):
    return _morph(images, cv2.MORPH_CLOSE, ksize, iterations)


def op_equalize_hist(images):
    img = _ensure_bgr(images[0])
    if img.ndim == 2:
        return cv2.equalizeHist(img)
    ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
    return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)


def op_clahe(images, clip_limit: float = 2.0, tile_grid: int = 8):
    img = _ensure_bgr(images[0])
    clahe = cv2.createCLAHE(clipLimit=float(clip_limit), tileGridSize=(int(tile_grid), int(tile_grid)))
    if img.ndim == 2:
        return clahe.apply(img)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


# ---------------------------------------------------------------------------
# 2-input operations (combine)
# ---------------------------------------------------------------------------

def op_blend(images, alpha: float = 0.5):
    a, b = _match_shape(images[0], images[1])
    return cv2.addWeighted(a, float(alpha), b, 1.0 - float(alpha), 0)


def op_add(images):
    a, b = _match_shape(images[0], images[1])
    return cv2.add(a, b)


def op_subtract(images):
    a, b = _match_shape(images[0], images[1])
    return cv2.subtract(a, b)


def op_max(images):
    a, b = _match_shape(images[0], images[1])
    return np.maximum(a, b)


def op_min(images):
    a, b = _match_shape(images[0], images[1])
    return np.minimum(a, b)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

OPERATIONS: tuple[Operation, ...] = (
    # ---- Geometry ----
    Operation(
        key="resize", label="Resize", category="Geometry", inputs=1, fn=op_resize,
        params=(
            ParamSpec("width", "Width (0=auto)", "int", 0, min=0, max=8192, step=1),
            ParamSpec("height", "Height (0=auto)", "int", 0, min=0, max=8192, step=1),
            ParamSpec("scale", "Scale (used when W/H=0)", "float", 1.0, min=0.05, max=8.0, step=0.05),
        ),
    ),
    Operation(
        key="rotate", label="Rotate", category="Geometry", inputs=1, fn=op_rotate,
        params=(
            ParamSpec("angle", "Angle (deg)", "float", 0.0, min=-360.0, max=360.0, step=1.0),
            ParamSpec("keep_size", "Keep original size", "bool", True),
        ),
    ),
    Operation(
        key="flip", label="Flip", category="Geometry", inputs=1, fn=op_flip,
        params=(
            ParamSpec("direction", "Direction", "choice", "horizontal",
                      choices=("horizontal", "vertical", "both")),
        ),
    ),
    # ---- Color ----
    Operation(
        key="to_gray", label="Grayscale", category="Color", inputs=1, fn=op_to_gray,
    ),
    Operation(
        key="invert", label="Invert", category="Color", inputs=1, fn=op_invert,
    ),
    Operation(
        key="brightness_contrast", label="Brightness / Contrast", category="Color",
        inputs=1, fn=op_brightness_contrast,
        params=(
            ParamSpec("brightness", "Brightness", "int", 0, min=-128, max=128, step=1),
            ParamSpec("contrast", "Contrast", "float", 1.0, min=0.0, max=4.0, step=0.05),
        ),
    ),
    Operation(
        key="gamma", label="Gamma", category="Color", inputs=1, fn=op_gamma,
        params=(
            ParamSpec("gamma", "Gamma", "float", 1.0, min=0.1, max=4.0, step=0.05),
        ),
    ),
    # ---- Filter ----
    Operation(
        key="gaussian_blur", label="Gaussian Blur", category="Filter", inputs=1, fn=op_gaussian_blur,
        params=(
            ParamSpec("ksize", "Kernel (odd)", "int", 5, min=1, max=99, step=2),
            ParamSpec("sigma", "Sigma (0=auto)", "float", 0.0, min=0.0, max=50.0, step=0.1),
        ),
    ),
    Operation(
        key="median_blur", label="Median Blur", category="Filter", inputs=1, fn=op_median_blur,
        params=(
            ParamSpec("ksize", "Kernel (odd ≥3)", "int", 5, min=3, max=99, step=2),
        ),
    ),
    Operation(
        key="bilateral", label="Bilateral Filter", category="Filter", inputs=1, fn=op_bilateral,
        params=(
            ParamSpec("d", "Diameter", "int", 9, min=1, max=51, step=1),
            ParamSpec("sigma_color", "Sigma color", "float", 75.0, min=1.0, max=300.0, step=1.0),
            ParamSpec("sigma_space", "Sigma space", "float", 75.0, min=1.0, max=300.0, step=1.0),
        ),
    ),
    Operation(
        key="box_blur", label="Box Blur", category="Filter", inputs=1, fn=op_box_blur,
        params=(ParamSpec("ksize", "Kernel", "int", 5, min=1, max=99, step=1),),
    ),
    Operation(
        key="sharpen", label="Unsharp Mask", category="Filter", inputs=1, fn=op_sharpen,
        params=(ParamSpec("amount", "Amount", "float", 1.0, min=0.0, max=5.0, step=0.1),),
    ),
    # ---- Threshold ----
    Operation(
        key="threshold_binary", label="Threshold (Binary)", category="Threshold",
        inputs=1, fn=op_threshold_binary,
        params=(
            ParamSpec("thresh", "Threshold", "int", 127, min=0, max=255, step=1),
            ParamSpec("max_value", "Max value", "int", 255, min=0, max=255, step=1),
            ParamSpec("invert", "Invert", "bool", False),
        ),
    ),
    Operation(
        key="threshold_otsu", label="Threshold (Otsu)", category="Threshold",
        inputs=1, fn=op_threshold_otsu,
        params=(ParamSpec("invert", "Invert", "bool", False),),
    ),
    Operation(
        key="threshold_adaptive", label="Threshold (Adaptive)", category="Threshold",
        inputs=1, fn=op_threshold_adaptive,
        params=(
            ParamSpec("method", "Method", "choice", "gaussian", choices=("gaussian", "mean")),
            ParamSpec("block_size", "Block size (odd ≥3)", "int", 11, min=3, max=99, step=2),
            ParamSpec("C", "C constant", "int", 2, min=-20, max=20, step=1),
            ParamSpec("invert", "Invert", "bool", False),
        ),
    ),
    # ---- Edge ----
    Operation(
        key="canny", label="Canny Edge", category="Edge", inputs=1, fn=op_canny,
        params=(
            ParamSpec("threshold1", "Threshold 1", "int", 100, min=0, max=500, step=1),
            ParamSpec("threshold2", "Threshold 2", "int", 200, min=0, max=500, step=1),
        ),
    ),
    Operation(
        key="sobel", label="Sobel", category="Edge", inputs=1, fn=op_sobel,
        params=(
            ParamSpec("ksize", "Kernel (odd)", "int", 3, min=1, max=31, step=2),
            ParamSpec("direction", "Direction", "choice", "both", choices=("both", "x", "y")),
        ),
    ),
    Operation(
        key="laplacian", label="Laplacian", category="Edge", inputs=1, fn=op_laplacian,
        params=(ParamSpec("ksize", "Kernel (odd)", "int", 3, min=1, max=31, step=2),),
    ),
    # ---- Morphology ----
    Operation(
        key="erode", label="Erode", category="Morphology", inputs=1, fn=op_erode,
        params=(
            ParamSpec("ksize", "Kernel", "int", 3, min=1, max=31, step=1),
            ParamSpec("iterations", "Iterations", "int", 1, min=1, max=10, step=1),
        ),
    ),
    Operation(
        key="dilate", label="Dilate", category="Morphology", inputs=1, fn=op_dilate,
        params=(
            ParamSpec("ksize", "Kernel", "int", 3, min=1, max=31, step=1),
            ParamSpec("iterations", "Iterations", "int", 1, min=1, max=10, step=1),
        ),
    ),
    Operation(
        key="open", label="Open", category="Morphology", inputs=1, fn=op_open,
        params=(
            ParamSpec("ksize", "Kernel", "int", 3, min=1, max=31, step=1),
            ParamSpec("iterations", "Iterations", "int", 1, min=1, max=10, step=1),
        ),
    ),
    Operation(
        key="close", label="Close", category="Morphology", inputs=1, fn=op_close,
        params=(
            ParamSpec("ksize", "Kernel", "int", 3, min=1, max=31, step=1),
            ParamSpec("iterations", "Iterations", "int", 1, min=1, max=10, step=1),
        ),
    ),
    # ---- Histogram ----
    Operation(
        key="equalize_hist", label="Equalize Histogram", category="Histogram",
        inputs=1, fn=op_equalize_hist,
    ),
    Operation(
        key="clahe", label="CLAHE", category="Histogram", inputs=1, fn=op_clahe,
        params=(
            ParamSpec("clip_limit", "Clip limit", "float", 2.0, min=0.1, max=20.0, step=0.1),
            ParamSpec("tile_grid", "Tile grid", "int", 8, min=2, max=32, step=1),
        ),
    ),
    # ---- Combine ----
    Operation(
        key="blend", label="Blend (A·α + B·(1-α))", category="Combine",
        inputs=2, fn=op_blend,
        params=(ParamSpec("alpha", "Alpha", "float", 0.5, min=0.0, max=1.0, step=0.01),),
    ),
    Operation(
        key="add", label="Add (A + B)", category="Combine", inputs=2, fn=op_add,
    ),
    Operation(
        key="subtract", label="Subtract (A - B)", category="Combine", inputs=2, fn=op_subtract,
    ),
    Operation(
        key="max", label="Max(A, B)", category="Combine", inputs=2, fn=op_max,
    ),
    Operation(
        key="min", label="Min(A, B)", category="Combine", inputs=2, fn=op_min,
    ),
)


_BY_KEY: dict[str, Operation] = {op.key: op for op in OPERATIONS}


def get_operation(key: str) -> Operation:
    if key not in _BY_KEY:
        raise KeyError(f"Unknown operation: {key!r}")
    return _BY_KEY[key]


def apply_operation(key: str, images: list[np.ndarray], **params) -> np.ndarray:
    op = get_operation(key)
    merged = op.defaults()
    merged.update({k: v for k, v in params.items() if k in merged})
    if op.inputs == 1:
        result = op.fn([images[0]], **merged)
    else:
        if len(images) < op.inputs:
            raise ValueError(
                f"Operation {key!r} requires {op.inputs} inputs, got {len(images)}"
            )
        result = op.fn(images[: op.inputs], **merged)
    return _ensure_uint8(result)
