"""QGraphicsScene that owns :class:`NodeItem`/:class:`EdgeItem` instances and
syncs UI gestures (drag-to-connect, delete, select) into a
:class:`~apt.preprocessing.pipeline.Pipeline`.
"""

from __future__ import annotations

import logging

from PyQt5.QtCore import QPointF, Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAction,
    QGraphicsScene,
    QGraphicsSceneContextMenuEvent,
    QGraphicsSceneMouseEvent,
    QMenu,
)

from apt.preprocessing import Operation, Pipeline, PipelineError
from apt.widgets.node_graph.edge_item import EdgeItem
from apt.widgets.node_graph.node_item import NODE_HEIGHT, NODE_WIDTH, NodeItem, PortItem, SNAP_STEP


class NodeScene(QGraphicsScene):
    nodeSelected = pyqtSignal(str)        # emitted with node_id on selection
    graphChanged = pyqtSignal()           # emitted whenever the topology changes
    statusMessage = pyqtSignal(str)       # transient errors / hints

    def __init__(self, pipeline: Pipeline, parent=None) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self.setBackgroundBrush(QColor("#0B0B0E"))
        self.setSceneRect(-1500, -1500, 3000, 3000)
        self._nodes: dict[str, NodeItem] = {}
        self._edges: list[EdgeItem] = []
        self._temp_edge: EdgeItem | None = None
        self._drag_origin: PortItem | None = None
        self.selectionChanged.connect(self._on_selection_changed)
        self._sync_from_pipeline()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_op_node(self, op: Operation, scene_pos: QPointF | None = None) -> str:
        node = self.pipeline.add_node(op.key)
        self._add_node_item(node.id, scene_pos=scene_pos)
        self.graphChanged.emit()
        return node.id

    def remove_selected(self) -> None:
        """Delete the currently selected node(s) and/or edge(s).

        Snapshots both lists *first*, then mutates — otherwise the per-item
        ``_rebuild_edges`` call would invalidate later iterations of the
        same press (the user's "Delete takes multiple presses" bug).
        """
        nodes_to_delete: list[str] = []
        edges_to_delete: list[EdgeItem] = []
        for item in self.selectedItems():
            if isinstance(item, EdgeItem) and not item.temporary:
                edges_to_delete.append(item)
            elif isinstance(item, NodeItem) and not item.is_origin:
                nodes_to_delete.append(item.node_id)

        if not nodes_to_delete and not edges_to_delete:
            return

        self._cancel_pending_grabs()

        # Edges first so node deletion can't double-process them.
        for edge in edges_to_delete:
            try:
                dst_id = edge.dst_port.node.node_id
                dst_port = edge.dst_port.index
                self.pipeline.disconnect(dst_id, dst_port)
                edge.detach()
                if edge.scene() is self:
                    self.removeItem(edge)
                if edge in self._edges:
                    self._edges.remove(edge)
            except Exception:
                logging.exception("remove_selected: failed to drop edge")

        # Then nodes.
        for node_id in nodes_to_delete:
            try:
                item = self._nodes.pop(node_id, None)
                if item is None:
                    continue
                for edge in [
                    e for e in list(self._edges)
                    if e.src_port.node is item or e.dst_port.node is item
                ]:
                    try:
                        edge.detach()
                        if edge.scene() is self:
                            self.removeItem(edge)
                        if edge in self._edges:
                            self._edges.remove(edge)
                    except Exception:
                        logging.exception("remove_selected: edge cleanup for node %s", node_id)
                if item.scene() is self:
                    self.removeItem(item)
                self.pipeline.remove_node(node_id)
            except Exception:
                logging.exception("remove_selected: failed to drop node %s", node_id)

        # Single rebuild at the end keeps everything consistent.
        self._rebuild_edges()
        self.graphChanged.emit()

    def reset_graph(self) -> None:
        self._cancel_pending_grabs()
        for edge in list(self._edges):
            try:
                edge.detach()
                if edge.scene() is self:
                    self.removeItem(edge)
            except Exception:
                logging.exception("reset_graph: edge cleanup")
        self._edges.clear()
        for nid, item in list(self._nodes.items()):
            if nid == Pipeline.ORIGIN_ID:
                continue
            try:
                if item.scene() is self:
                    self.removeItem(item)
                del self._nodes[nid]
            except Exception:
                logging.exception("reset_graph: removing node %s", nid)
        self.pipeline.clear()
        # Re-anchor origin position.
        origin = self._nodes.get(Pipeline.ORIGIN_ID)
        if origin is not None:
            origin.setPos(-300, 0)
        self.graphChanged.emit()

    # ------------------------------------------------------------------
    # Mouse handling for drag-to-connect
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        port = self._port_at(event.scenePos())
        if event.button() == Qt.LeftButton and isinstance(port, PortItem) and port.kind == "out":
            self._drag_origin = port
            self._temp_edge = EdgeItem(src_port=port, dst_port=None, temporary=True)
            self._temp_edge.set_free_end(event.scenePos())
            self.addItem(self._temp_edge)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._temp_edge is not None:
            self._temp_edge.set_free_end(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._temp_edge is not None and self._drag_origin is not None:
            target = self._port_at(event.scenePos())
            self.removeItem(self._temp_edge)
            self._temp_edge = None
            src = self._drag_origin
            self._drag_origin = None
            if isinstance(target, PortItem) and target.kind == "in" and target.node is not src.node:
                self._connect_or_fork(src, target)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Smart connect: replace vs auto-fork when the port is occupied
    # ------------------------------------------------------------------
    def _connect_or_fork(self, src: PortItem, target: PortItem) -> None:
        """Connect ``src.output`` → ``target.input``.

        If the input port already holds a different source AND the target op
        accepts only one input, clone the destination node so both incoming
        branches survive (same params, edit independently after). This matches
        the user's mental model of "wire two upstreams into the same op" —
        rather than silently replacing the older edge.

        For multi-input ops (the Combine category) we fall through to a
        plain replace because the user deliberately picked that specific
        port (port 0 or port 1).
        """
        from apt.preprocessing.operations import get_operation

        src_id = src.node.node_id
        dst_id = target.node.node_id
        port_idx = target.index

        try:
            dst_node = self.pipeline.get(dst_id)
        except PipelineError:
            return

        existing_src = (
            dst_node.inputs[port_idx] if port_idx < len(dst_node.inputs) else ""
        )

        # User dropped the same connection again — nothing to do.
        if existing_src == src_id:
            return

        # Empty port → plain connect.
        if not existing_src:
            self._do_connect(src_id, dst_id, port_idx)
            return

        # Port already holds a *different* source. For single-input ops, fork
        # the destination so we keep both branches.
        try:
            op = get_operation(dst_node.op_key)
        except KeyError:
            self._do_connect(src_id, dst_id, port_idx)
            return

        if op.inputs > 1:
            self._do_connect(src_id, dst_id, port_idx)
            return

        self._fork_destination(target.node, src_id)

    def _do_connect(self, src_id: str, dst_id: str, port_idx: int) -> None:
        try:
            self.pipeline.connect(src_id, dst_id, port_idx)
        except PipelineError as exc:
            self.statusMessage.emit(str(exc))
            return
        self._rebuild_edges()
        self.graphChanged.emit()

    def _fork_destination(self, dest_item: NodeItem, src_id: str) -> None:
        """Clone ``dest_item`` (op + params) and connect ``src_id`` to the clone.

        Called when the user drags a second connection into a single-input
        op's already-occupied port. Original node + its existing connection
        stay intact; only the clone is wired to the new source.
        """
        try:
            src_node = self.pipeline.get(dest_item.node_id)
        except PipelineError:
            return
        try:
            new_node = self.pipeline.add_node(src_node.op_key)
        except PipelineError as exc:
            self.statusMessage.emit(str(exc))
            return
        for k, v in src_node.params.items():
            self.pipeline.set_param(new_node.id, k, v)
        # Place the clone just below the original so the user can see what
        # happened. Snap-to-grid in itemChange keeps the placement clean.
        pos = dest_item.scenePos()
        x = float(pos.x())
        y = float(pos.y()) + NODE_HEIGHT + 30
        new_node.position = (x, y)
        self._add_node_item(
            new_node.id,
            scene_pos=QPointF(x + NODE_WIDTH / 2, y + NODE_HEIGHT / 2),
        )
        try:
            self.pipeline.connect(src_id, new_node.id, 0)
        except PipelineError as exc:
            self.statusMessage.emit(str(exc))
            return
        self._rebuild_edges()
        self.statusMessage.emit(
            f"Duplicated {dest_item.node_id} → {new_node.id} so both branches "
            f"are kept (same params · edit independently)."
        )
        # Select the new node so the inspector populates with its params.
        self.clearSelection()
        if new_node.id in self._nodes:
            self._nodes[new_node.id].setSelected(True)
        self.graphChanged.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        mods = event.modifiers()
        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            self.remove_selected()
            event.accept()
            return
        if key == Qt.Key_Escape:
            self.clearSelection()
            event.accept()
            return
        if key == Qt.Key_A and (mods & Qt.ControlModifier):
            for item in self._nodes.values():
                item.setSelected(True)
            event.accept()
            return
        if key == Qt.Key_D and (mods & Qt.ControlModifier):
            self.duplicate_selected()
            event.accept()
            return
        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            self._nudge_selected(key, fast=bool(mods & Qt.ShiftModifier))
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None:  # noqa: N802
        item = next(
            (it for it in self.items(event.scenePos()) if isinstance(it, NodeItem)),
            None,
        )
        if item is None:
            return
        if not item.isSelected():
            self.clearSelection()
            item.setSelected(True)

        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background-color: #15161B; color: #EDEDEF; border: 1px solid #2E3140; }"
            "QMenu::item { padding: 6px 18px; }"
            "QMenu::item:selected { background-color: #FF7029; color: #0B0B0E; }"
        )

        if not item.is_origin:
            dup_action = QAction("Duplicate  (Ctrl+D)", menu)
            dup_action.triggered.connect(self.duplicate_selected)
            menu.addAction(dup_action)

        disc_action = QAction("Disconnect inputs", menu)
        disc_action.triggered.connect(lambda: self._disconnect_inputs(item.node_id))
        menu.addAction(disc_action)

        menu.addSeparator()
        if not item.is_origin:
            del_action = QAction("Delete  (Del)", menu)
            del_action.triggered.connect(self.remove_selected)
            menu.addAction(del_action)

        menu.exec_(event.screenPos())
        event.accept()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _sync_from_pipeline(self) -> None:
        # Make sure origin exists.
        if Pipeline.ORIGIN_ID not in self._nodes:
            self._add_node_item(Pipeline.ORIGIN_ID, scene_pos=QPointF(-300, 0))

    def _add_node_item(self, node_id: str, scene_pos: QPointF | None = None) -> NodeItem:
        node = self.pipeline.get(node_id)
        item = NodeItem(
            node_id=node.id,
            op_key=node.op_key,
            is_origin=(node.op_key == "origin"),
        )
        item.update_params(node.params)
        # If the pipeline carries a position (e.g. loaded from a job file),
        # use it. Otherwise fall back to the caller-supplied scene_pos, then
        # to a diagonal default that avoids overlap with existing nodes.
        if node.position != (0.0, 0.0):
            item.setPos(node.position[0], node.position[1])
        else:
            if scene_pos is None:
                count = len(self._nodes)
                scene_pos = QPointF(60 * (count + 1), 80 * (count % 5))
            top_left_x = scene_pos.x() - NODE_WIDTH / 2
            top_left_y = scene_pos.y() - NODE_HEIGHT / 2
            item.setPos(top_left_x, top_left_y)
            node.position = (top_left_x, top_left_y)
        item.add_move_listener(lambda nid=node.id: self._sync_node_position(nid))
        self.addItem(item)
        self._nodes[node_id] = item
        return item

    def refresh_node_params(self, node_id: str) -> None:
        """Re-render the params summary line of ``node_id`` from the pipeline."""
        item = self._nodes.get(node_id)
        if item is None:
            return
        try:
            node = self.pipeline.get(node_id)
        except Exception:
            return
        item.update_params(node.params)

    def refresh_all_node_visuals(self) -> None:
        """Sync every NodeItem's status pip / time label from the pipeline.

        Called after a compute pass so the canvas shows fresh per-node
        timings (success / cached / error). Cheap: no graph mutation.
        """
        for node_id, item in self._nodes.items():
            try:
                node = self.pipeline.get(node_id)
            except PipelineError:
                continue
            item.update_status(node.last_time_ms, node.last_status, node.last_error)

    def set_pipeline(self, pipeline: Pipeline) -> None:
        """Replace the underlying pipeline and rebuild the scene visuals.

        Used after loading a job file (the entire graph is swapped out).
        """
        self._cancel_pending_grabs()
        self.clearSelection()
        for edge in list(self._edges):
            try:
                edge.detach()
                if edge.scene() is self:
                    self.removeItem(edge)
            except Exception:
                logging.exception("set_pipeline: edge cleanup")
        self._edges.clear()
        for item in list(self._nodes.values()):
            try:
                if item.scene() is self:
                    self.removeItem(item)
            except Exception:
                logging.exception("set_pipeline: node cleanup")
        self._nodes.clear()
        self.pipeline = pipeline
        # Recreate origin + every op node at its saved position.
        for node in pipeline.nodes():
            try:
                self._add_node_item(node.id)
            except Exception:
                logging.exception("set_pipeline: adding node %s", node.id)
        self._rebuild_edges()
        self.graphChanged.emit()

    def _cancel_pending_grabs(self) -> None:
        """Drop any in-flight temporary edge / port drag and release any
        currently-held mouse grab. Called before mutations that remove items
        from the scene to silence ``QGraphicsItem::ungrabMouse`` warnings.
        """
        if self._temp_edge is not None:
            try:
                if self._temp_edge.scene() is self:
                    self.removeItem(self._temp_edge)
            except Exception:
                logging.exception("_cancel_pending_grabs: temp edge")
            self._temp_edge = None
        self._drag_origin = None
        grabber = self.mouseGrabberItem()
        if grabber is not None:
            try:
                grabber.ungrabMouse()
            except Exception:
                # Some Qt builds whine here too — that's fine, we tried.
                pass

    def _sync_node_position(self, node_id: str) -> None:
        """Mirror an item's top-left pos back onto its pipeline ``Node``."""
        item = self._nodes.get(node_id)
        if item is None:
            return
        try:
            node = self.pipeline.get(node_id)
        except Exception:
            return
        p = item.scenePos()
        node.position = (float(p.x()), float(p.y()))

    # ------------------------------------------------------------------
    # Snap / duplicate / layout / nudge
    # ------------------------------------------------------------------
    def set_snap_enabled(self, enabled: bool) -> None:
        NodeItem.snap_enabled = bool(enabled)
        self.statusMessage.emit(
            "Snap-to-grid ON (hold Shift to free-place)" if enabled
            else "Snap-to-grid OFF"
        )

    def duplicate_selected(self) -> None:
        """Clone every selected op node (no inputs wired) with a small offset."""
        clones: list[str] = []
        for item in [it for it in self.selectedItems() if isinstance(it, NodeItem)]:
            if item.is_origin:
                continue
            try:
                src_node = self.pipeline.get(item.node_id)
            except PipelineError:
                continue
            new_node = self.pipeline.add_node(src_node.op_key)
            for k, v in src_node.params.items():
                self.pipeline.set_param(new_node.id, k, v)
            x = item.scenePos().x() + NODE_WIDTH + 30
            y = item.scenePos().y() + 30
            new_node.position = (x, y)
            self._add_node_item(new_node.id, scene_pos=QPointF(x + NODE_WIDTH / 2, y + NODE_HEIGHT / 2))
            clones.append(new_node.id)
        if clones:
            self.clearSelection()
            for nid in clones:
                self._nodes[nid].setSelected(True)
            self.graphChanged.emit()

    def auto_layout(self) -> None:
        """Hierarchical left→right layout: depth from Origin = column index.

        Origin gets depth 0; every other node's depth is ``max(input depths) + 1``.
        Within a column, nodes are stacked vertically with a constant gap.
        Disconnected nodes land in their own column past the deepest one.
        """
        depths: dict[str, int] = {Pipeline.ORIGIN_ID: 0}
        node_list = [n for n in self.pipeline.nodes()]

        # Iterate until every node has a depth (DAG, so this converges).
        changed = True
        while changed:
            changed = False
            for node in node_list:
                if node.id in depths:
                    continue
                src_depths = [
                    depths[src] for src in node.inputs if src and src in depths
                ]
                if not node.inputs or not any(node.inputs):
                    depths[node.id] = max(depths.values(), default=0) + 1
                    changed = True
                elif len(src_depths) == sum(1 for s in node.inputs if s):
                    depths[node.id] = max(src_depths) + 1
                    changed = True
        # Anything still missing (shouldn't happen but be defensive).
        for node in node_list:
            depths.setdefault(node.id, max(depths.values(), default=0) + 1)

        # Group by depth.
        columns: dict[int, list[str]] = {}
        for nid, d in depths.items():
            columns.setdefault(d, []).append(nid)

        col_gap_x = NODE_WIDTH + 60
        row_gap_y = NODE_HEIGHT + 24
        for depth, ids in sorted(columns.items()):
            ids_sorted = sorted(ids)
            n = len(ids_sorted)
            total_h = n * NODE_HEIGHT + (n - 1) * 24
            top = -total_h / 2
            x = depth * col_gap_x
            for i, nid in enumerate(ids_sorted):
                y = top + i * row_gap_y
                item = self._nodes.get(nid)
                if item is None:
                    continue
                item.setPos(x, y)
                try:
                    self.pipeline.get(nid).position = (float(x), float(y))
                except PipelineError:
                    pass
        # Edges follow because each NodeItem move listener was installed at
        # _add_node_item time.
        self.graphChanged.emit()
        self.statusMessage.emit("Auto-layout applied")

    def _nudge_selected(self, key: int, fast: bool = False) -> None:
        step = SNAP_STEP * (5 if fast else 1)
        dx, dy = {
            Qt.Key_Left: (-step, 0),
            Qt.Key_Right: (step, 0),
            Qt.Key_Up: (0, -step),
            Qt.Key_Down: (0, step),
        }.get(key, (0, 0))
        for item in [it for it in self.selectedItems() if isinstance(it, NodeItem)]:
            item.moveBy(dx, dy)

    def _disconnect_inputs(self, node_id: str) -> None:
        try:
            node = self.pipeline.get(node_id)
        except PipelineError:
            return
        for port_idx, src in enumerate(list(node.inputs)):
            if src:
                self.pipeline.disconnect(node_id, port_idx)
        self._rebuild_edges()
        self.graphChanged.emit()

    def _rebuild_edges(self) -> None:
        for edge in list(self._edges):
            try:
                edge.detach()
                if edge.scene() is self:
                    self.removeItem(edge)
            except Exception:
                logging.exception("_rebuild_edges: removing edge")
        self._edges.clear()
        for node in self.pipeline.nodes():
            for port_idx, src_id in enumerate(node.inputs):
                if not src_id:
                    continue
                src_item = self._nodes.get(src_id)
                dst_item = self._nodes.get(node.id)
                if src_item is None or dst_item is None:
                    continue
                if port_idx >= len(dst_item.inputs):
                    logging.warning(
                        "_rebuild_edges: %s port %d out of range (%d inputs)",
                        node.id, port_idx, len(dst_item.inputs),
                    )
                    continue
                try:
                    edge = EdgeItem(
                        src_port=src_item.output,
                        dst_port=dst_item.inputs[port_idx],
                    )
                    self.addItem(edge)
                    self._edges.append(edge)
                except Exception:
                    logging.exception(
                        "_rebuild_edges: creating edge %s -> %s", src_id, node.id
                    )

    def _port_at(self, pos: QPointF):
        for item in self.items(pos):
            if isinstance(item, PortItem):
                return item
        return None

    def _on_selection_changed(self) -> None:
        for item in self.selectedItems():
            if isinstance(item, NodeItem):
                self.nodeSelected.emit(item.node_id)
                return
        self.nodeSelected.emit("")
