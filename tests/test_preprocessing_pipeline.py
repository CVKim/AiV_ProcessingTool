"""Pipeline graph behaviour tests."""

from __future__ import annotations

import numpy as np
import pytest

from apt.preprocessing import Pipeline, PipelineError


@pytest.fixture
def origin():
    img = np.full((40, 40, 3), 128, dtype=np.uint8)
    img[10:30, 10:30] = 200
    return img


def _make(pipeline, op_key, *, inputs=None, **params):
    node = pipeline.add_node(op_key)
    for port, src in enumerate(inputs or []):
        pipeline.connect(src, node.id, port)
    for k, v in params.items():
        pipeline.set_param(node.id, k, v)
    return node.id


def test_origin_always_exists():
    p = Pipeline()
    assert p.get(Pipeline.ORIGIN_ID).op_key == "origin"


def test_compute_origin_requires_loaded_image():
    p = Pipeline()
    with pytest.raises(PipelineError):
        p.compute(Pipeline.ORIGIN_ID)


def test_add_op_node_and_run(origin):
    p = Pipeline()
    p.set_origin(origin)
    blur = _make(p, "gaussian_blur", inputs=[Pipeline.ORIGIN_ID], ksize=3)
    out = p.compute(blur)
    assert out.shape == origin.shape


def test_disconnect_invalidates_cache(origin):
    p = Pipeline()
    p.set_origin(origin)
    blur = _make(p, "gaussian_blur", inputs=[Pipeline.ORIGIN_ID])
    p.compute(blur)
    p.disconnect(blur, 0)
    with pytest.raises(PipelineError):
        p.compute(blur)


def test_remove_node_propagates_to_downstream(origin):
    p = Pipeline()
    p.set_origin(origin)
    a = _make(p, "gaussian_blur", inputs=[Pipeline.ORIGIN_ID])
    b = _make(p, "canny", inputs=[a])
    p.compute(b)
    p.remove_node(a)
    # b's only input is gone now.
    with pytest.raises(PipelineError):
        p.compute(b)


def test_cycle_is_refused(origin):
    p = Pipeline()
    p.set_origin(origin)
    a = _make(p, "gaussian_blur", inputs=[Pipeline.ORIGIN_ID])
    b = _make(p, "median_blur", inputs=[a])
    # b consumes a; trying to feed b back into a would create a cycle.
    with pytest.raises(PipelineError):
        p.connect(b, a, 0)


def test_two_input_combine(origin):
    p = Pipeline()
    p.set_origin(origin)
    a = _make(p, "gaussian_blur", inputs=[Pipeline.ORIGIN_ID])
    b = _make(p, "canny", inputs=[Pipeline.ORIGIN_ID])
    c = _make(p, "blend", inputs=[a, b], alpha=0.4)
    out = p.compute(c)
    assert out.shape[:2] == origin.shape[:2]


def test_set_param_recomputes(origin):
    p = Pipeline()
    p.set_origin(origin)
    bright = _make(p, "brightness_contrast", inputs=[Pipeline.ORIGIN_ID])
    out1 = p.compute(bright).copy()
    p.set_param(bright, "brightness", 80)
    out2 = p.compute(bright)
    assert not np.array_equal(out1, out2)


def test_output_ids_excludes_origin_when_graph_has_ops(origin):
    p = Pipeline()
    p.set_origin(origin)
    a = _make(p, "gaussian_blur", inputs=[Pipeline.ORIGIN_ID])
    b = _make(p, "canny", inputs=[Pipeline.ORIGIN_ID])
    # Both leaves; origin should NOT show up.
    leaves = set(p.output_ids())
    assert Pipeline.ORIGIN_ID not in leaves
    assert leaves == {a, b}


def test_output_ids_when_only_origin():
    p = Pipeline()
    # No op nodes — origin counts as the leaf.
    assert p.output_ids() == [Pipeline.ORIGIN_ID]


def test_clear_keeps_origin_only():
    p = Pipeline()
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    p.set_origin(img)
    _make(p, "gaussian_blur", inputs=[Pipeline.ORIGIN_ID])
    p.clear()
    assert list(n.id for n in p.nodes()) == [Pipeline.ORIGIN_ID]


def test_unknown_op_rejected():
    p = Pipeline()
    with pytest.raises(KeyError):
        p.add_node("does_not_exist")


def test_origin_cannot_be_removed():
    p = Pipeline()
    with pytest.raises(PipelineError):
        p.remove_node(Pipeline.ORIGIN_ID)


def test_connect_into_origin_refused():
    p = Pipeline()
    a = p.add_node("gaussian_blur")
    with pytest.raises(PipelineError):
        p.connect(a.id, Pipeline.ORIGIN_ID, 0)


def test_id_assignment_does_not_reuse_gaps(origin):
    """Regression: after a delete+add, the new node id must not collide with
    a stale id that lives elsewhere — and the panel's export-clone path
    relies on stable per-pipeline numbering to build a correct id map."""
    p = Pipeline()
    p.set_origin(origin)
    a = p.add_node("rotate")
    b = p.add_node("to_gray")
    assert a.id == "rotate_1"
    assert b.id == "to_gray_2"
    p.remove_node(a.id)
    c = p.add_node("to_gray")
    # New node should get a fresh id, not collide with the remaining b.
    assert c.id != b.id
    assert c.id == "to_gray_3"
