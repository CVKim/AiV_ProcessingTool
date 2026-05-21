"""Save / load preprocessing pipelines to JSON job files.

A job file captures the *structure* of a pipeline — every op node, its
parameters, its connections, and its canvas position. Loaded images are NOT
part of the job; the same job can therefore be re-applied to any image (or
batch of images).

File format (version 1)::

    {
      "format": "aivex-preprocessing-job",
      "version": 1,
      "saved_at": "2026-05-19T16:32:00",
      "nodes": [
        {
          "id": "rotate_1",
          "op_key": "rotate",
          "params": {"angle": 30.0, "keep_size": true},
          "inputs": ["origin"],
          "position": [60.0, 80.0]
        },
        ...
      ]
    }

Origin is implicit; its position is included for layout restoration but it
has no ``op_key`` requirement other than the literal ``"origin"``.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from apt.preprocessing.operations import get_operation
from apt.preprocessing.pipeline import Pipeline


FORMAT_TAG = "aivex-preprocessing-job"
CURRENT_VERSION = 1


class JobFormatError(ValueError):
    """Raised when a file does not look like a valid job dump."""


def serialize_pipeline(pipeline: Pipeline) -> dict[str, Any]:
    """Build the JSON-friendly dict representation of ``pipeline``.

    Includes the origin node (with its position) so the canvas layout
    survives a round-trip.
    """
    nodes: list[dict[str, Any]] = []
    for node in pipeline.nodes():
        nodes.append(
            {
                "id": node.id,
                "op_key": node.op_key,
                "params": dict(node.params),
                "inputs": list(node.inputs),
                "position": [float(node.position[0]), float(node.position[1])],
            }
        )
    return {
        "format": FORMAT_TAG,
        "version": CURRENT_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "nodes": nodes,
    }


def deserialize_pipeline(data: dict[str, Any]) -> Pipeline:
    """Reconstruct a :class:`Pipeline` from a parsed job dict.

    Validation:
    * Must carry the AIVEX format tag and a supported version.
    * Every op_key must be registered.
    * Connections referencing unknown ids are silently dropped (the
      pipeline reports them at compute time anyway).
    """
    if not isinstance(data, dict):
        raise JobFormatError("Job file root must be an object")
    if data.get("format") != FORMAT_TAG:
        raise JobFormatError(
            f"Not an AIVEX job file (format={data.get('format')!r})"
        )
    version = data.get("version")
    if version != CURRENT_VERSION:
        raise JobFormatError(
            f"Unsupported job-file version {version!r}; expected {CURRENT_VERSION}"
        )
    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, list):
        raise JobFormatError("Job file is missing the 'nodes' list")

    pipeline = Pipeline()
    pipeline.clear()  # ensure a fresh origin

    # First pass: create op nodes (origin already exists in a fresh pipeline).
    # We let the pipeline auto-assign ids, but remember the saved id → new id
    # mapping so the second pass can wire connections correctly.
    id_map: dict[str, str] = {Pipeline.ORIGIN_ID: Pipeline.ORIGIN_ID}
    # Apply origin position if it was saved.
    for raw in raw_nodes:
        if raw.get("op_key") == "origin":
            origin = pipeline.get(Pipeline.ORIGIN_ID)
            pos = raw.get("position") or [0.0, 0.0]
            origin.position = (float(pos[0]), float(pos[1]))
            break

    for raw in raw_nodes:
        op_key = raw.get("op_key")
        if op_key == "origin":
            continue
        if not isinstance(op_key, str):
            raise JobFormatError(f"Node missing op_key: {raw!r}")
        try:
            op = get_operation(op_key)
        except KeyError as exc:
            raise JobFormatError(str(exc)) from None
        node = pipeline.add_node(op.key)
        old_id = raw.get("id")
        if isinstance(old_id, str):
            id_map[old_id] = node.id
        # Merge saved params on top of defaults so missing/added params are tolerated.
        params = raw.get("params") or {}
        for k, v in params.items():
            if k in node.params:
                pipeline.set_param(node.id, k, v)
        pos = raw.get("position") or [0.0, 0.0]
        node.position = (float(pos[0]), float(pos[1]))

    # Second pass: rebuild connections.
    for raw in raw_nodes:
        if raw.get("op_key") == "origin":
            continue
        old_id = raw.get("id")
        if old_id not in id_map:
            continue
        new_id = id_map[old_id]
        for port_idx, src in enumerate(raw.get("inputs", []) or []):
            if not isinstance(src, str) or not src:
                continue
            src_new = id_map.get(src)
            if src_new is None:
                # Saved a dangling edge — skip silently.
                continue
            try:
                pipeline.connect(src_new, new_id, port_idx)
            except Exception:
                # A dropped connection is a soft failure — the user will see
                # the offending node light up red at compute time.
                pass

    return pipeline


def save_job(pipeline: Pipeline, path: str) -> None:
    payload = serialize_pipeline(pipeline)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_job(path: str) -> Pipeline:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return deserialize_pipeline(data)
