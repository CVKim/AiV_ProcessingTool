"""Preprocessing pipeline panel — node-graph editor with live previews.

Layout (left → right):

    [Operations sidebar]  [Node graph canvas]  [Parameters + Preview]
"""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from apt.dialogs.base import BaseTaskPanel
from apt.preprocessing import Pipeline, PipelineError
from apt.preprocessing.operations import get_operation
from apt.widgets.image_preview import ImagePreview
from apt.widgets.op_picker import OpPicker
from apt.widgets.parameter_form import ParameterForm
from apt.widgets.node_graph import NodeScene, NodeView


_PREVIEW_MAX_DIM = 720
_SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".bmp")


class PreprocessingPanel(BaseTaskPanel):
    TITLE = "Preprocessing"
    SUBTITLE = (
        "Origin 이미지를 불러와 좌측의 전처리 op들을 그래프로 연결하세요. "
        "노드를 클릭하면 우측에서 파라미터를 조정하고 결과를 미리볼 수 있습니다. "
        "Export는 모든 leaf 노드의 결과를 폴더에 저장합니다. "
        "지원 포맷: JPG / PNG / BMP (MIM은 먼저 MIM to BMP 패널로 변환하세요)."
    )

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        self.pipeline = Pipeline()
        self._origin_path: str = ""
        self._origin_full: np.ndarray | None = None
        self._origin_preview: np.ndarray | None = None
        self._selected_node_id: str = ""
        self._recompute_timer = QTimer()
        self._recompute_timer.setSingleShot(True)
        self._recompute_timer.setInterval(50)  # debounce parameter changes
        super().__init__(parent)
        self._recompute_timer.timeout.connect(self._recompute_preview)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(8)

        title = QLabel(self.TITLE)
        title.setObjectName("PageTitle")
        outer.addWidget(title)
        sub = QLabel(self.SUBTITLE)
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        # Top action row
        action_row = QHBoxLayout()
        self.load_button = QPushButton("Load Image…")
        self.load_button.setObjectName("PrimaryButton")
        self.load_button.clicked.connect(self._load_image)
        self.reset_button = QPushButton("Reset Graph")
        self.reset_button.clicked.connect(self._reset_graph)
        self.fit_button = QPushButton("Fit View")
        self.fit_button.clicked.connect(self._fit_view)
        self.export_button = QPushButton("Export Outputs…")
        self.export_button.clicked.connect(self._export_outputs)
        self.origin_label = QLabel("Origin: (not loaded)")
        self.origin_label.setStyleSheet("color: #9A9CA3;")
        action_row.addWidget(self.load_button)
        action_row.addWidget(self.reset_button)
        action_row.addWidget(self.fit_button)
        action_row.addWidget(self.export_button)
        action_row.addSpacing(16)
        action_row.addWidget(self.origin_label, 1)
        outer.addLayout(action_row)

        # 3-pane splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter, 1)

        splitter.addWidget(self._build_operations_panel())
        splitter.addWidget(self._build_graph_panel())
        splitter.addWidget(self._build_inspector_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([260, 720, 400])

    # ---- operations sidebar -----------------------------------------
    def _build_operations_panel(self) -> QWidget:
        self.op_picker = OpPicker()
        self.op_picker.opActivated.connect(self._add_op)
        self.op_picker.setMinimumWidth(240)
        return self.op_picker

    # ---- graph canvas -----------------------------------------------
    def _build_graph_panel(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Pipeline Graph</b>"))
        header.addStretch(1)
        header.addWidget(
            self._dim_label(
                "Drag output (right) → input (left) to connect · "
                "Wheel = zoom · Mid-drag = pan · Del = remove"
            )
        )
        layout.addLayout(header)

        self.scene = NodeScene(self.pipeline)
        self.scene.nodeSelected.connect(self._on_node_selected)
        self.scene.graphChanged.connect(self._on_graph_changed)
        self.scene.statusMessage.connect(self._show_status)

        self.view = NodeView(self.scene)
        layout.addWidget(self.view, 1)
        self.status_label = QLabel(" ")
        self.status_label.setStyleSheet("color: #FF7029; font-size: 11px;")
        layout.addWidget(self.status_label)
        return wrap

    # ---- inspector (right) ------------------------------------------
    def _build_inspector_panel(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        params_group = QGroupBox("Parameters")
        params_layout = QVBoxLayout(params_group)
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(0)
        self.param_form = ParameterForm()
        self.param_form.valueChanged.connect(self._on_param_changed)
        scroller.setWidget(self.param_form)
        params_layout.addWidget(scroller)
        layout.addWidget(params_group, 1)

        preview_group = QGroupBox("Preview (selected node)")
        preview_layout = QVBoxLayout(preview_group)
        self.preview = ImagePreview()
        preview_layout.addWidget(self.preview, 1)
        self.preview_meta = QLabel("(no node selected)")
        self.preview_meta.setStyleSheet("color: #9A9CA3; font-size: 11px;")
        preview_layout.addWidget(self.preview_meta)
        layout.addWidget(preview_group, 2)
        return wrap

    # ------------------------------------------------------------------
    # BaseTaskPanel overrides (this panel doesn't use the worker plumbing)
    # ------------------------------------------------------------------
    def build_form(self, form: QFormLayout) -> None:
        return

    def get_parameters(self) -> dict:
        return {}

    def validate_parameters(self, params: dict) -> bool:
        return True

    def start_task(self) -> None:
        return

    def stop_task(self) -> None:
        return

    # ------------------------------------------------------------------
    # Origin
    # ------------------------------------------------------------------
    def _load_image(self) -> None:
        filter_ = "Images (*.jpg *.jpeg *.png *.bmp);;All files (*.*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select Origin Image", "", filter_)
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext not in _SUPPORTED_EXTS:
            QMessageBox.warning(
                self,
                "Unsupported format",
                "Preprocessing supports JPG / PNG / BMP only.\n"
                "MIM 파일은 먼저 'MIM to BMP' 패널로 BMP로 변환한 뒤 사용해주세요.",
            )
            return

        image = _imread_bgr(path)
        if image is None:
            QMessageBox.critical(self, "Load failed", f"이미지를 불러올 수 없습니다:\n{path}")
            return

        self._origin_path = path
        self._origin_full = image
        self._origin_preview = _downscale(image, _PREVIEW_MAX_DIM)
        self.pipeline.set_origin(self._origin_preview)
        self.origin_label.setText(
            f"Origin: {os.path.basename(path)}  ·  {image.shape[1]}×{image.shape[0]}px"
            f"  ·  preview {self._origin_preview.shape[1]}×{self._origin_preview.shape[0]}"
        )
        # Select origin and refresh preview
        from apt.widgets.node_graph import NodeItem
        for item in self.scene.items():
            if isinstance(item, NodeItem) and item.node_id == Pipeline.ORIGIN_ID:
                self.scene.clearSelection()
                item.setSelected(True)
                break
        self._recompute_preview()

    def _reset_graph(self) -> None:
        if QMessageBox.question(
            self,
            "Reset graph",
            "그래프의 모든 op 노드를 삭제할까요? Origin과 로드된 이미지는 유지됩니다.",
        ) != QMessageBox.Yes:
            return
        self.scene.reset_graph()
        self.param_form.clear()
        self.preview.set_image(self._origin_preview)
        self.preview_meta.setText("Origin (graph reset)")

    def _fit_view(self) -> None:
        self.view.fit_to_content()

    # ------------------------------------------------------------------
    # Operation list interactions
    # ------------------------------------------------------------------
    def _add_op(self, op_key: str | None) -> None:
        if not op_key:
            return
        try:
            op = get_operation(op_key)
        except KeyError:
            return
        try:
            new_id = self.scene.add_op_node(op)
        except PipelineError as exc:
            self._show_status(str(exc))
            return
        # Auto-select the newly added node so the inspector populates.
        from apt.widgets.node_graph import NodeItem
        for it in self.scene.items():
            if isinstance(it, NodeItem) and it.node_id == new_id:
                self.scene.clearSelection()
                it.setSelected(True)
                break

    # ------------------------------------------------------------------
    # Scene events
    # ------------------------------------------------------------------
    def _on_node_selected(self, node_id: str) -> None:
        self._selected_node_id = node_id
        if not node_id:
            self.param_form.clear()
            self.preview_meta.setText("(no node selected)")
            return
        node = self.pipeline.get(node_id)
        if node.op_key == "origin":
            self.param_form.show_params("Origin", (), {})
            self.preview.set_image(self._origin_preview)
            if self._origin_preview is None:
                self.preview_meta.setText("Origin not loaded yet")
            else:
                h, w = self._origin_preview.shape[:2]
                self.preview_meta.setText(f"Origin · {w}×{h} preview")
            return
        op = get_operation(node.op_key)
        self.param_form.show_params(op.label, op.params, node.params)
        self._refresh_preview_for(node_id)

    def _on_graph_changed(self) -> None:
        if self._selected_node_id:
            self._refresh_preview_for(self._selected_node_id)

    def _on_param_changed(self, name: str, value) -> None:
        if not self._selected_node_id:
            return
        node = self.pipeline.get(self._selected_node_id)
        if node.op_key == "origin":
            return
        try:
            self.pipeline.set_param(self._selected_node_id, name, value)
        except PipelineError as exc:
            self._show_status(str(exc))
            return
        # Update the node card's params-summary line so the canvas reflects the new value.
        self.scene.refresh_node_params(self._selected_node_id)
        self._recompute_timer.start()

    def _recompute_preview(self) -> None:
        if self._selected_node_id:
            self._refresh_preview_for(self._selected_node_id)

    def _refresh_preview_for(self, node_id: str) -> None:
        if self._origin_preview is None:
            self.preview.set_image(None)
            self.preview_meta.setText("Load an origin image first.")
            return
        try:
            result = self.pipeline.compute(node_id)
        except PipelineError as exc:
            self.preview.set_image(None)
            self.preview_meta.setText(f"⚠ {exc}")
            return
        except Exception as exc:  # noqa: BLE001
            self.preview.set_image(None)
            self.preview_meta.setText(f"⚠ {exc}")
            return
        self.preview.set_image(result)
        h, w = result.shape[:2]
        ch = 1 if result.ndim == 2 else result.shape[2]
        node = self.pipeline.get(node_id)
        self.preview_meta.setText(
            f"{node.display_title()} ({node.id}) · {w}×{h}px · {ch}ch"
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export_outputs(self) -> None:
        if self._origin_full is None:
            QMessageBox.warning(self, "Export", "Origin 이미지를 먼저 로드하세요.")
            return
        original_leaves = [
            nid for nid in self.pipeline.output_ids() if nid != Pipeline.ORIGIN_ID
        ]
        if not original_leaves:
            QMessageBox.information(
                self,
                "Export",
                "내보낼 leaf 노드가 없습니다. op 노드를 추가하고 Origin과 연결하세요.",
            )
            return

        target = QFileDialog.getExistingDirectory(
            self,
            "Select export folder",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if not target:
            return

        # Build a full-resolution clone of the pipeline; remember which new id
        # corresponds to each original leaf so we compute the right nodes.
        full_pipeline, id_map = self._clone_pipeline_for_full_res()
        base = Path(self._origin_path).stem
        saved: list[str] = []
        errors: list[str] = []
        for original_leaf in original_leaves:
            cloned_leaf = id_map.get(original_leaf)
            if cloned_leaf is None:
                errors.append(f"{original_leaf}: missing in cloned pipeline")
                continue
            try:
                result = full_pipeline.compute(cloned_leaf)
            except PipelineError as exc:
                errors.append(f"{original_leaf}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{original_leaf}: {exc}")
                continue
            out_path = os.path.join(target, f"{base}__{original_leaf}.png")
            try:
                ok = cv2.imwrite(out_path, result)
                if not ok:
                    raise IOError("cv2.imwrite returned False")
                saved.append(out_path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{original_leaf}: write failed — {exc}")

        msg_lines = [f"Saved {len(saved)} file(s) to:\n{target}\n"]
        if saved:
            msg_lines.append("\n".join("  • " + os.path.basename(p) for p in saved))
        if errors:
            msg_lines.append("\nErrors:")
            msg_lines.extend("  ⚠ " + e for e in errors)
        QMessageBox.information(self, "Export complete", "\n".join(msg_lines))

    def _clone_pipeline_for_full_res(self) -> tuple[Pipeline, dict[str, str]]:
        clone = Pipeline()
        clone.set_origin(self._origin_full)
        id_map: dict[str, str] = {Pipeline.ORIGIN_ID: Pipeline.ORIGIN_ID}
        for node in self.pipeline.nodes():
            if node.op_key == "origin":
                continue
            new = clone.add_node(node.op_key)
            id_map[node.id] = new.id
            for k, v in node.params.items():
                clone.set_param(new.id, k, v)
        for node in self.pipeline.nodes():
            if node.op_key == "origin":
                continue
            new_id = id_map[node.id]
            for port_idx, src in enumerate(node.inputs):
                if src and src in id_map:
                    clone.connect(id_map[src], new_id, port_idx)
        return clone, id_map

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    def _show_status(self, text: str) -> None:
        self.status_label.setText(text)
        QTimer.singleShot(4000, lambda: self.status_label.setText(" "))

    @staticmethod
    def _dim_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #9A9CA3; font-size: 11px;")
        label.setWordWrap(True)
        return label


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _imread_bgr(path: str) -> np.ndarray | None:
    """Read JPG/PNG/BMP as BGR uint8.

    Uses numpy + cv2.imdecode so Unicode paths work on Windows.
    """
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return img


def _downscale(image: np.ndarray, max_dim: int) -> np.ndarray:
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return image.copy()
    scale = max_dim / longest
    new_size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)
