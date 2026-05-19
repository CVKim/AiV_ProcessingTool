"""Save/load round-trip and validation for preprocessing job files."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from apt.preprocessing import (
    JobFormatError,
    Pipeline,
    deserialize_pipeline,
    load_job,
    save_job,
    serialize_pipeline,
)


def _build_sample_pipeline() -> Pipeline:
    p = Pipeline()
    blur = p.add_node("gaussian_blur")
    bright = p.add_node("brightness_contrast")
    blend = p.add_node("blend")
    p.connect(Pipeline.ORIGIN_ID, blur.id, 0)
    p.connect(Pipeline.ORIGIN_ID, bright.id, 0)
    p.connect(blur.id, blend.id, 0)
    p.connect(bright.id, blend.id, 1)
    p.set_param(blur.id, "ksize", 7)
    p.set_param(bright.id, "brightness", 25)
    p.set_param(blend.id, "alpha", 0.4)
    p.get(blur.id).position = (40.0, 50.0)
    p.get(blend.id).position = (300.0, 100.0)
    return p


def test_roundtrip_in_memory():
    original = _build_sample_pipeline()
    data = serialize_pipeline(original)
    restored = deserialize_pipeline(data)

    orig_ops = sorted(n.op_key for n in original.nodes())
    rest_ops = sorted(n.op_key for n in restored.nodes())
    assert orig_ops == rest_ops


def test_roundtrip_through_disk(tmp_path):
    original = _build_sample_pipeline()
    path = tmp_path / "job.apt.json"
    save_job(original, str(path))
    restored = load_job(str(path))
    # Params and positions survive.
    rest_blur = next(n for n in restored.nodes() if n.op_key == "gaussian_blur")
    assert rest_blur.params["ksize"] == 7
    assert rest_blur.position == (40.0, 50.0)
    rest_blend = next(n for n in restored.nodes() if n.op_key == "blend")
    assert rest_blend.params["alpha"] == pytest.approx(0.4)
    assert rest_blend.position == (300.0, 100.0)


def test_loaded_pipeline_executes_against_a_new_image(tmp_path):
    original = _build_sample_pipeline()
    path = tmp_path / "job.apt.json"
    save_job(original, str(path))
    restored = load_job(str(path))
    img = np.full((30, 30, 3), 120, dtype=np.uint8)
    restored.set_origin(img)
    leaf = next(n for n in restored.nodes() if n.op_key == "blend")
    out = restored.compute(leaf.id)
    assert out.shape[:2] == img.shape[:2]


def test_rejects_non_aivex_files(tmp_path):
    path = tmp_path / "other.json"
    path.write_text(json.dumps({"format": "something-else"}))
    with pytest.raises(JobFormatError):
        load_job(str(path))


def test_rejects_unsupported_version(tmp_path):
    path = tmp_path / "future.apt.json"
    payload = serialize_pipeline(_build_sample_pipeline())
    payload["version"] = 999
    path.write_text(json.dumps(payload))
    with pytest.raises(JobFormatError):
        load_job(str(path))


def test_rejects_unknown_op_keys(tmp_path):
    path = tmp_path / "bad.apt.json"
    path.write_text(json.dumps({
        "format": "aivex-preprocessing-job",
        "version": 1,
        "nodes": [{"id": "x_1", "op_key": "totally_made_up", "params": {}, "inputs": []}],
    }))
    with pytest.raises(JobFormatError):
        load_job(str(path))


def test_dangling_connection_silently_dropped(tmp_path):
    """If a saved input references an id we don't recreate, the edge is just
    skipped — the rest of the graph still loads cleanly."""
    path = tmp_path / "dangling.apt.json"
    payload = {
        "format": "aivex-preprocessing-job",
        "version": 1,
        "nodes": [
            {
                "id": "blur_1", "op_key": "gaussian_blur",
                "params": {"ksize": 3, "sigma": 0.0},
                "inputs": ["ghost_node"], "position": [0, 0],
            }
        ],
    }
    path.write_text(json.dumps(payload))
    restored = load_job(str(path))
    blur = next(n for n in restored.nodes() if n.op_key == "gaussian_blur")
    # No valid input wired — the connection list is empty.
    assert all(not src for src in blur.inputs)


def test_duplicate_with_origin_returns_id_map():
    p = _build_sample_pipeline()
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    clone, id_map = p.duplicate_with_origin(img)
    # The mapping must cover every node id in the source.
    src_ids = {n.id for n in p.nodes()}
    assert src_ids.issubset(id_map.keys())
    # Compute a leaf through the cloned id.
    leaf_src = next(n for n in p.nodes() if n.op_key == "blend")
    leaf_dst = id_map[leaf_src.id]
    out = clone.compute(leaf_dst)
    assert out.shape[:2] == img.shape[:2]


def test_duplicate_preserves_positions():
    p = _build_sample_pipeline()
    clone, id_map = p.duplicate_with_origin(np.zeros((10, 10, 3), dtype=np.uint8))
    blur_src = next(n for n in p.nodes() if n.op_key == "gaussian_blur")
    blur_dst = clone.get(id_map[blur_src.id])
    assert blur_dst.position == blur_src.position
