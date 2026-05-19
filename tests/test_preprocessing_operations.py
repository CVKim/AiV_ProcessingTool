"""Smoke + invariant tests for every registered preprocessing operation.

We don't try to assert numerical correctness for OpenCV — those are well
tested upstream. We assert that:
    * Every op runs on a synthetic image without raising.
    * The output is a uint8 numpy array.
    * The output shape is consistent with the documented contract
      (filters preserve HxW; rotate w/ keep_size preserves; thresholds
      drop to 1 channel; combine ops broadcast both inputs to 3-channel
      and produce the larger input's HxW).
"""

from __future__ import annotations

import numpy as np
import pytest

from apt.preprocessing import OPERATIONS, apply_operation
from apt.preprocessing.operations import get_operation


# A reproducible non-uniform test image so threshold/edge ops behave non-trivially.
def _make_image() -> np.ndarray:
    rng = np.random.default_rng(42)
    img = rng.integers(0, 256, size=(64, 80, 3), dtype=np.uint8)
    # Draw a bright square so morphology / threshold ops have structure.
    img[20:40, 30:50] = 240
    return img


@pytest.fixture
def image():
    return _make_image()


@pytest.mark.parametrize("op", [op for op in OPERATIONS if op.inputs == 1], ids=lambda op: op.key)
def test_single_input_operations_run(op, image):
    result = apply_operation(op.key, [image], **op.defaults())
    assert isinstance(result, np.ndarray)
    assert result.dtype == np.uint8
    # All filters either keep HxW or, for non-keep-size geometry ops, produce
    # something sensible (non-empty).
    assert result.shape[0] > 0 and result.shape[1] > 0


@pytest.mark.parametrize("op", [op for op in OPERATIONS if op.inputs == 2], ids=lambda op: op.key)
def test_combine_operations_run(op, image):
    # Use a second image with a clearly different value pattern.
    other = (image // 2 + 30).astype(np.uint8)
    result = apply_operation(op.key, [image, other], **op.defaults())
    assert isinstance(result, np.ndarray)
    assert result.dtype == np.uint8
    assert result.shape[0] == image.shape[0]
    assert result.shape[1] == image.shape[1]


def test_combine_resizes_mismatched_second_input(image):
    smaller = np.full((20, 30, 3), 100, dtype=np.uint8)
    # Should not raise — the helper resizes B to match A.
    out = apply_operation("blend", [image, smaller], alpha=0.5)
    assert out.shape[:2] == image.shape[:2]


def test_threshold_binary_produces_2d(image):
    out = apply_operation("threshold_binary", [image], thresh=127)
    assert out.ndim == 2
    assert set(np.unique(out)).issubset({0, 255})


def test_canny_produces_2d(image):
    out = apply_operation("canny", [image])
    assert out.ndim == 2


def test_rotate_keep_size_preserves_shape(image):
    out = apply_operation("rotate", [image], angle=33, keep_size=True)
    assert out.shape == image.shape


def test_rotate_grow_changes_shape(image):
    out = apply_operation("rotate", [image], angle=33, keep_size=False)
    assert out.shape[0] >= image.shape[0] - 1
    assert out.shape[1] >= image.shape[1] - 1


def test_resize_to_explicit_dims(image):
    out = apply_operation("resize", [image], width=20, height=10)
    assert out.shape[:2] == (10, 20)


def test_resize_by_scale_when_dims_zero(image):
    out = apply_operation("resize", [image], width=0, height=0, scale=0.5)
    assert out.shape[0] == image.shape[0] // 2
    assert out.shape[1] == image.shape[1] // 2


def test_get_operation_raises_for_unknown_key():
    with pytest.raises(KeyError):
        get_operation("nope")


def test_apply_operation_rejects_missing_second_input():
    with pytest.raises(ValueError):
        apply_operation("blend", [_make_image()])


def test_param_defaults_are_consistent():
    # Every param's default must coerce-round-trip via its kind.
    for op in OPERATIONS:
        defaults = op.defaults()
        for spec in op.params:
            assert spec.name in defaults
            # Coerce should not raise on the default value.
            spec.coerce(defaults[spec.name])
