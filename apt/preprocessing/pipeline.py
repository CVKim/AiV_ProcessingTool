"""Execute a directed graph of preprocessing :class:`Node` instances.

The pipeline is a DAG: the unique ``"origin"`` node holds the loaded image,
every other node references zero or more upstream nodes by id and an
:class:`~apt.preprocessing.operations.Operation` key. ``Pipeline.compute(node_id)``
runs the minimal subgraph needed for that node and caches results per node so
that interactive parameter tweaks only recompute the dirty subtree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from apt.preprocessing.operations import apply_operation, get_operation


class PipelineError(RuntimeError):
    """Raised for graph-level problems (cycles, missing inputs, …)."""


@dataclass
class Node:
    """A single step in a preprocessing pipeline.

    ``op_key`` is one of the registry keys in
    :data:`apt.preprocessing.operations.OPERATIONS`.  The special key
    ``"origin"`` denotes the input image and has zero inputs; its image is
    provided via :meth:`Pipeline.set_origin`.
    """

    id: str
    op_key: str
    inputs: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    title: str = ""

    def display_title(self) -> str:
        if self.title:
            return self.title
        if self.op_key == "origin":
            return "Origin"
        return get_operation(self.op_key).label


class Pipeline:
    """In-memory DAG of :class:`Node` instances with per-node result cache."""

    ORIGIN_ID = "origin"

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {
            self.ORIGIN_ID: Node(id=self.ORIGIN_ID, op_key="origin"),
        }
        self._origin_image: np.ndarray | None = None
        self._cache: dict[str, np.ndarray] = {}
        self._next_id = 1

    # ------------------------------------------------------------------
    # Origin
    # ------------------------------------------------------------------
    def set_origin(self, image: np.ndarray | None) -> None:
        self._origin_image = image
        self._cache.clear()

    def origin_image(self) -> np.ndarray | None:
        return self._origin_image

    # ------------------------------------------------------------------
    # Graph mutation
    # ------------------------------------------------------------------
    def nodes(self) -> Iterable[Node]:
        return self._nodes.values()

    def get(self, node_id: str) -> Node:
        if node_id not in self._nodes:
            raise PipelineError(f"Unknown node: {node_id!r}")
        return self._nodes[node_id]

    def add_node(self, op_key: str, inputs: list[str] | None = None) -> Node:
        if op_key == "origin":
            raise PipelineError("Origin node is implicit and unique.")
        op = get_operation(op_key)
        inputs = list(inputs or [])
        for src in inputs:
            if src not in self._nodes:
                raise PipelineError(f"Input node missing: {src!r}")
        node = Node(
            id=self._make_id(op_key),
            op_key=op_key,
            inputs=inputs,
            params=op.defaults(),
        )
        self._nodes[node.id] = node
        return node

    def remove_node(self, node_id: str) -> None:
        if node_id == self.ORIGIN_ID:
            raise PipelineError("Origin node cannot be removed.")
        if node_id not in self._nodes:
            return
        del self._nodes[node_id]
        for n in self._nodes.values():
            n.inputs = [i for i in n.inputs if i != node_id]
        self._invalidate_all()

    def connect(self, src_id: str, dst_id: str, dst_port: int) -> None:
        """Wire ``src_id``'s output into ``dst_id``'s ``dst_port``.

        ``dst_port`` is 0-indexed. Auto-grows the inputs list if needed.
        Refuses connections that would introduce a cycle.
        """
        if src_id not in self._nodes or dst_id not in self._nodes:
            raise PipelineError("Both endpoints must exist")
        if dst_id == self.ORIGIN_ID:
            raise PipelineError("Cannot connect into origin")
        dst = self._nodes[dst_id]
        if self._would_create_cycle(src_id, dst_id):
            raise PipelineError("Connection would create a cycle")
        # Pad inputs if needed.
        while len(dst.inputs) <= dst_port:
            dst.inputs.append("")
        dst.inputs[dst_port] = src_id
        self._invalidate_from(dst_id)

    def disconnect(self, dst_id: str, dst_port: int) -> None:
        dst = self._nodes.get(dst_id)
        if dst is None or dst_port >= len(dst.inputs):
            return
        dst.inputs[dst_port] = ""
        self._invalidate_from(dst_id)

    def set_param(self, node_id: str, name: str, value) -> None:
        node = self.get(node_id)
        node.params[name] = value
        self._invalidate_from(node_id)

    def clear(self) -> None:
        """Remove every node except origin (and clear origin's image)."""
        self._nodes = {self.ORIGIN_ID: Node(id=self.ORIGIN_ID, op_key="origin")}
        self._next_id = 1
        self._cache.clear()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def compute(self, node_id: str) -> np.ndarray:
        if node_id in self._cache:
            return self._cache[node_id]
        node = self.get(node_id)
        if node.op_key == "origin":
            if self._origin_image is None:
                raise PipelineError("Origin image is not loaded")
            self._cache[node_id] = self._origin_image
            return self._origin_image

        op = get_operation(node.op_key)
        required = op.inputs
        actual_inputs = [i for i in node.inputs if i]
        if len(actual_inputs) < required:
            raise PipelineError(
                f"Node {node_id!r} ({node.op_key}) needs {required} input(s), "
                f"has {len(actual_inputs)}"
            )
        images = [self.compute(src) for src in actual_inputs[:required]]
        result = apply_operation(node.op_key, images, **node.params)
        self._cache[node_id] = result
        return result

    def output_ids(self) -> list[str]:
        """Node ids that nothing else consumes (graph leaves, excluding origin
        if it's the only node)."""
        consumed: set[str] = set()
        for n in self._nodes.values():
            for src in n.inputs:
                if src:
                    consumed.add(src)
        leaves = [n.id for n in self._nodes.values() if n.id not in consumed]
        if len(self._nodes) > 1 and self.ORIGIN_ID in leaves:
            leaves.remove(self.ORIGIN_ID)
        return leaves

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _make_id(self, op_key: str) -> str:
        # Stable, human-friendly identifiers: ``blur_1``, ``blur_2``, …
        candidate = f"{op_key}_{self._next_id}"
        self._next_id += 1
        while candidate in self._nodes:
            candidate = f"{op_key}_{self._next_id}"
            self._next_id += 1
        return candidate

    def _would_create_cycle(self, src_id: str, dst_id: str) -> bool:
        # Adding edge src -> dst means dst will read from src. That closes a
        # cycle iff src already (transitively) reads from dst — i.e. dst is
        # upstream of src. Walk src's input chain and see if dst appears.
        if src_id == dst_id:
            return True
        upstream: set[str] = set()

        def walk(n_id: str) -> None:
            node = self._nodes.get(n_id)
            if node is None:
                return
            for src in node.inputs:
                if not src or src in upstream:
                    continue
                upstream.add(src)
                walk(src)

        walk(src_id)
        return dst_id in upstream

    def _invalidate_all(self) -> None:
        self._cache.clear()

    def _invalidate_from(self, node_id: str) -> None:
        if node_id not in self._cache and not any(node_id == n for n in self._cache):
            # Even if it wasn't cached, downstream nodes might be — recurse.
            pass
        dirty: set[str] = set()

        def mark(n_id: str) -> None:
            if n_id in dirty:
                return
            dirty.add(n_id)
            for n in self._nodes.values():
                if n_id in n.inputs:
                    mark(n.id)

        mark(node_id)
        for d in dirty:
            self._cache.pop(d, None)
