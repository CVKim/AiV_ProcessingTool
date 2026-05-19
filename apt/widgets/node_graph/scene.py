"""QGraphicsScene that owns :class:`NodeItem`/:class:`EdgeItem` instances and
syncs UI gestures (drag-to-connect, delete, select) into a
:class:`~apt.preprocessing.pipeline.Pipeline`.
"""

from __future__ import annotations

from PyQt5.QtCore import QPointF, Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsSceneMouseEvent

from apt.preprocessing import Operation, Pipeline, PipelineError
from apt.widgets.node_graph.edge_item import EdgeItem
from apt.widgets.node_graph.node_item import NODE_HEIGHT, NODE_WIDTH, NodeItem, PortItem


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
        """Delete the currently selected node(s) and/or edge(s)."""
        removed = False
        for item in list(self.selectedItems()):
            if isinstance(item, EdgeItem) and not item.temporary:
                self._delete_edge(item)
                removed = True
            elif isinstance(item, NodeItem) and not item.is_origin:
                self._delete_node(item.node_id)
                removed = True
        if removed:
            self.graphChanged.emit()

    def reset_graph(self) -> None:
        for edge in list(self._edges):
            edge.detach()
            self.removeItem(edge)
        self._edges.clear()
        for nid, item in list(self._nodes.items()):
            if nid != Pipeline.ORIGIN_ID:
                self.removeItem(item)
                del self._nodes[nid]
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
                try:
                    self.pipeline.connect(src.node.node_id, target.node.node_id, target.index)
                except PipelineError as exc:
                    self.statusMessage.emit(str(exc))
                else:
                    self._rebuild_edges()
                    self.graphChanged.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.remove_selected()
            event.accept()
            return
        super().keyPressEvent(event)

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
        if scene_pos is None:
            # Lay nodes out diagonally so a newly added node never lands on top
            # of an existing one. The scene's view will pan to fit on demand.
            count = len(self._nodes)
            scene_pos = QPointF(60 * (count + 1), 80 * (count % 5))
        item.setPos(scene_pos.x() - NODE_WIDTH / 2, scene_pos.y() - NODE_HEIGHT / 2)
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

    def _delete_node(self, node_id: str) -> None:
        item = self._nodes.pop(node_id, None)
        if item is None:
            return
        # Drop edges touching this node.
        for edge in [e for e in self._edges if e.src_port.node is item or e.dst_port.node is item]:
            edge.detach()
            self.removeItem(edge)
            self._edges.remove(edge)
        self.removeItem(item)
        self.pipeline.remove_node(node_id)
        self._rebuild_edges()

    def _delete_edge(self, edge: EdgeItem) -> None:
        dst_id = edge.dst_port.node.node_id
        dst_port = edge.dst_port.index
        self.pipeline.disconnect(dst_id, dst_port)
        edge.detach()
        self.removeItem(edge)
        if edge in self._edges:
            self._edges.remove(edge)
        self._rebuild_edges()

    def _rebuild_edges(self) -> None:
        for edge in list(self._edges):
            edge.detach()
            self.removeItem(edge)
        self._edges.clear()
        for node in self.pipeline.nodes():
            for port_idx, src_id in enumerate(node.inputs):
                if not src_id:
                    continue
                src_item = self._nodes.get(src_id)
                dst_item = self._nodes.get(node.id)
                if src_item is None or dst_item is None:
                    continue
                edge = EdgeItem(src_port=src_item.output, dst_port=dst_item.inputs[port_idx])
                self.addItem(edge)
                self._edges.append(edge)

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
