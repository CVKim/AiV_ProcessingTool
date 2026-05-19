"""Preprocessing pipeline panel — node-graph editor with live previews,
job save/load, multi-image batch + grid view, and one-shot export.

Layout::

    [Action toolbar]
    [Horizontal splitter]
      [Operations sidebar]
      [Vertical splitter]
        [Graph canvas]
        [Image strip (loaded images, click to set active)]
      [Inspector]
        [Parameters]
        [Tabbed preview: Active / All images grid]
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from apt.dialogs.base import BaseTaskPanel
from apt.preprocessing import (
    JobFormatError,
    Pipeline,
    PipelineError,
    load_job,
    save_job,
)
from apt.preprocessing.operations import get_operation
from apt.widgets.batch_grid import BatchResultGrid
from apt.widgets.image_preview import ImagePreview
from apt.widgets.image_strip import ImageStrip
from apt.widgets.op_picker import OpPicker
from apt.widgets.parameter_form import ParameterForm
from apt.widgets.node_graph import NodeScene, NodeView


_PREVIEW_MAX_DIM = 720
_SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".bmp")
_IMAGE_FILTER = "Images (*.jpg *.jpeg *.png *.bmp);;All files (*.*)"
_JOB_FILTER = "AIVEX job (*.apt.json *.json);;All files (*.*)"


@dataclass
class LoadedImage:
    path: str
    full: np.ndarray         # original-resolution BGR
    preview: np.ndarray      # downscaled BGR for interactive work

    @property
    def name(self) -> str:
        return os.path.basename(self.path)


class PreprocessingPanel(BaseTaskPanel):
    TITLE = "Preprocessing"
    SUBTITLE = (
        "그래프로 전처리 파이프라인을 짜고, 여러 이미지를 한꺼번에 처리하세요. "
        "Save Job 으로 그래프를 .apt.json 으로 저장하고 다른 이미지에 Load Job 으로 재적용할 수 있습니다. "
        "지원 포맷: JPG / PNG / BMP (MIM은 먼저 MIM to BMP 패널로 변환하세요)."
    )

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        self.pipeline = Pipeline()
        self._images: list[LoadedImage] = []
        self._active_index: int = -1
        self._selected_node_id: str = ""
        self._recompute_timer = QTimer()
        self._recompute_timer.setSingleShot(True)
        self._recompute_timer.setInterval(60)
        self._batch_timer = QTimer()
        self._batch_timer.setSingleShot(True)
        self._batch_timer.setInterval(120)
        super().__init__(parent)
        self._recompute_timer.timeout.connect(self._recompute_preview)
        self._batch_timer.timeout.connect(self._recompute_batch_grid)

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

        outer.addLayout(self._build_action_row())

        # 3-pane splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter, 1)

        splitter.addWidget(self._build_operations_panel())
        splitter.addWidget(self._build_center_pane())
        splitter.addWidget(self._build_inspector_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([260, 720, 420])

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)

        self.load_button = QPushButton("Load Images…")
        self.load_button.setObjectName("PrimaryButton")
        self.load_button.clicked.connect(lambda: self._load_images(replace=True))
        self.add_button = QPushButton("Add Images…")
        self.add_button.clicked.connect(lambda: self._load_images(replace=False))
        self.save_job_button = QPushButton("Save Job…")
        self.save_job_button.clicked.connect(self._save_job)
        self.load_job_button = QPushButton("Load Job…")
        self.load_job_button.clicked.connect(self._load_job)
        self.reset_button = QPushButton("Reset Graph")
        self.reset_button.clicked.connect(self._reset_graph)
        self.fit_button = QPushButton("Fit View")
        self.fit_button.clicked.connect(self._fit_view)
        self.fit_button.setToolTip("Fit all nodes in the canvas  (F)")
        self.layout_button = QPushButton("Auto-Layout")
        self.layout_button.clicked.connect(self._auto_layout)
        self.layout_button.setToolTip(
            "Rearrange nodes left → right by depth from Origin"
        )
        self.snap_button = QPushButton("Snap")
        self.snap_button.setCheckable(True)
        self.snap_button.setChecked(True)
        self.snap_button.setToolTip(
            "Snap nodes to the grid while dragging (hold Shift to free-place)"
        )
        self.snap_button.toggled.connect(self._on_snap_toggled)
        self.export_button = QPushButton("Save Outputs…")
        self.export_button.clicked.connect(self._export_outputs)

        for btn in (
            self.load_button, self.add_button, self.save_job_button,
            self.load_job_button, self.reset_button, self.fit_button,
            self.layout_button, self.snap_button, self.export_button,
        ):
            row.addWidget(btn)
        row.addSpacing(16)
        self.status_summary = QLabel("(no images loaded)")
        self.status_summary.setStyleSheet("color: #9A9CA3;")
        row.addWidget(self.status_summary, 1)
        return row

    # ---- operations sidebar -----------------------------------------
    def _build_operations_panel(self) -> QWidget:
        self.op_picker = OpPicker()
        self.op_picker.opActivated.connect(self._add_op)
        self.op_picker.setMinimumWidth(240)
        return self.op_picker

    # ---- center: graph + image strip --------------------------------
    def _build_center_pane(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Graph
        graph_box = QWidget()
        graph_layout = QVBoxLayout(graph_box)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(4)
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Pipeline Graph</b>"))
        header.addStretch(1)
        header.addWidget(
            self._dim_label(
                "Drag output (right) → input (left) to connect · "
                "Wheel = zoom · Mid-drag = pan · Del = remove"
            )
        )
        graph_layout.addLayout(header)
        self.scene = NodeScene(self.pipeline)
        self.scene.nodeSelected.connect(self._on_node_selected)
        self.scene.graphChanged.connect(self._on_graph_changed)
        self.scene.statusMessage.connect(self._show_status)
        self.view = NodeView(self.scene)
        graph_layout.addWidget(self.view, 1)
        shortcuts = self._dim_label(
            "Shortcuts:  F = fit  ·  Ctrl+0 = reset zoom  ·  Ctrl+D = duplicate  ·  "
            "Ctrl+A = select all  ·  Esc = deselect  ·  ←↑↓→ = nudge "
            "(Shift = ×5)  ·  Space + drag = pan  ·  Right-click node = menu"
        )
        graph_layout.addWidget(shortcuts)

        # Image strip
        self.image_strip = ImageStrip()
        self.image_strip.imageSelected.connect(self._on_image_selected)
        self.image_strip.imageRemoved.connect(self._on_image_removed)

        vsplit = QSplitter(Qt.Vertical)
        vsplit.setChildrenCollapsible(False)
        vsplit.addWidget(graph_box)
        vsplit.addWidget(self.image_strip)
        vsplit.setStretchFactor(0, 4)
        vsplit.setStretchFactor(1, 0)
        layout.addWidget(vsplit, 1)

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

        # Tabbed preview area
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_tabs = QTabWidget()
        # Tab 1: single active image
        active_tab = QWidget()
        active_layout = QVBoxLayout(active_tab)
        active_layout.setContentsMargins(4, 4, 4, 4)
        active_layout.setSpacing(4)
        self.preview = ImagePreview()
        active_layout.addWidget(self.preview, 1)
        self.preview_meta = QLabel("(no node selected)")
        self.preview_meta.setStyleSheet("color: #9A9CA3; font-size: 11px;")
        active_layout.addWidget(self.preview_meta)
        self.preview_tabs.addTab(active_tab, "Active")
        # Tab 2: all images grid
        self.batch_grid = BatchResultGrid()
        self.preview_tabs.addTab(self.batch_grid, "All Images")
        self.preview_tabs.currentChanged.connect(self._on_preview_tab_changed)
        preview_layout.addWidget(self.preview_tabs)
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
    # Image loading
    # ------------------------------------------------------------------
    def _load_images(self, replace: bool) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select images", "", _IMAGE_FILTER
        )
        if not paths:
            return
        valid: list[LoadedImage] = []
        rejected: list[str] = []
        for path in paths:
            ext = os.path.splitext(path)[1].lower()
            if ext not in _SUPPORTED_EXTS:
                rejected.append(f"{os.path.basename(path)} (unsupported extension)")
                continue
            img = _imread_bgr(path)
            if img is None:
                rejected.append(f"{os.path.basename(path)} (failed to read)")
                continue
            valid.append(LoadedImage(
                path=path,
                full=img,
                preview=_downscale(img, _PREVIEW_MAX_DIM),
            ))
        if rejected:
            QMessageBox.warning(
                self,
                "Some images skipped",
                "Skipped:\n  " + "\n  ".join(rejected) +
                "\n\nSupported: JPG / PNG / BMP. MIM은 'MIM to BMP' 패널로 먼저 변환하세요.",
            )
        if not valid:
            return
        if replace:
            self._images = list(valid)
            self._active_index = 0
        else:
            self._images.extend(valid)
            if self._active_index < 0:
                self._active_index = 0
        self._sync_image_strip()
        self._apply_active_image_to_pipeline()
        # Pick a sensible default tab: grid when >1 image, active otherwise.
        self.preview_tabs.setCurrentIndex(1 if len(self._images) > 1 else 0)
        self._refresh_all()

    def _sync_image_strip(self) -> None:
        entries = [(img.preview, img.name) for img in self._images]
        self.image_strip.set_images(entries)
        if 0 <= self._active_index < len(self._images):
            self.image_strip.set_active(self._active_index)

    def _apply_active_image_to_pipeline(self) -> None:
        if 0 <= self._active_index < len(self._images):
            self.pipeline.set_origin(self._images[self._active_index].preview)
        else:
            self.pipeline.set_origin(None)

    def _update_status_summary(self) -> None:
        if not self._images:
            self.status_summary.setText("(no images loaded)")
            return
        if self._active_index >= 0:
            active = self._images[self._active_index]
            self.status_summary.setText(
                f"{len(self._images)} image(s)  ·  active = {active.name}  "
                f"({active.full.shape[1]}×{active.full.shape[0]}, preview "
                f"{active.preview.shape[1]}×{active.preview.shape[0]})"
            )
        else:
            self.status_summary.setText(f"{len(self._images)} image(s)")

    def _on_image_selected(self, index: int) -> None:
        if not (0 <= index < len(self._images)):
            return
        self._active_index = index
        self.image_strip.set_active(index)
        self._apply_active_image_to_pipeline()
        self._refresh_all()

    def _on_image_removed(self, index: int) -> None:
        if not (0 <= index < len(self._images)):
            return
        del self._images[index]
        if not self._images:
            self._active_index = -1
        elif self._active_index >= len(self._images):
            self._active_index = len(self._images) - 1
        self._sync_image_strip()
        self._apply_active_image_to_pipeline()
        self._refresh_all()

    # ------------------------------------------------------------------
    # Graph ops
    # ------------------------------------------------------------------
    def _reset_graph(self) -> None:
        if QMessageBox.question(
            self,
            "Reset graph",
            "그래프의 모든 op 노드를 삭제할까요? 이미지는 유지됩니다.",
        ) != QMessageBox.Yes:
            return
        self.scene.reset_graph()
        self.param_form.clear()
        self._refresh_all()

    def _fit_view(self) -> None:
        self.view.fit_to_content()

    def _auto_layout(self) -> None:
        self.scene.auto_layout()
        QTimer.singleShot(50, self.view.fit_to_content)

    def _on_snap_toggled(self, enabled: bool) -> None:
        self.scene.set_snap_enabled(enabled)

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
            self.batch_grid.set_header("(no node selected)")
            return
        try:
            node = self.pipeline.get(node_id)
        except PipelineError:
            return
        if node.op_key == "origin":
            self.param_form.show_params("Origin", (), {})
        else:
            op = get_operation(node.op_key)
            self.param_form.show_params(op.label, op.params, node.params)
        self._refresh_all()

    def _on_graph_changed(self) -> None:
        self._refresh_all()

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
        self.scene.refresh_node_params(self._selected_node_id)
        self._recompute_timer.start()
        self._batch_timer.start()

    def _on_preview_tab_changed(self, _index: int) -> None:
        self._refresh_all()

    # ------------------------------------------------------------------
    # Preview / batch grid recomputation
    # ------------------------------------------------------------------
    def _refresh_all(self) -> None:
        self._update_status_summary()
        self._recompute_preview()
        self._recompute_batch_grid()

    def _recompute_preview(self) -> None:
        if not self._selected_node_id:
            self.preview.set_image(None)
            self.preview_meta.setText("(no node selected)")
            return
        if self._active_index < 0:
            self.preview.set_image(None)
            self.preview_meta.setText("Load an image first.")
            return
        try:
            result = self.pipeline.compute(self._selected_node_id)
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
        node = self.pipeline.get(self._selected_node_id)
        active_name = self._images[self._active_index].name
        self.preview_meta.setText(
            f"{node.display_title()} ({node.id}) · {active_name} · {w}×{h}px · {ch}ch"
        )

    def _recompute_batch_grid(self) -> None:
        if self.preview_tabs.currentIndex() != 1:
            return
        if not self._selected_node_id:
            self.batch_grid.set_header("(select a node to see all results)")
            self.batch_grid.set_results([])
            return
        if not self._images:
            self.batch_grid.set_header("Load images first.")
            self.batch_grid.set_results([])
            return
        try:
            node = self.pipeline.get(self._selected_node_id)
        except PipelineError:
            return
        self.batch_grid.set_header(
            f"<b>{node.display_title()}</b> ({node.id}) · {len(self._images)} image(s) · preview-resolution"
        )
        entries: list[tuple[str, np.ndarray | None, str | None]] = []
        # Reuse self.pipeline as a template and clone-per-image to avoid
        # clobbering the cached active preview.
        for img in self._images:
            try:
                clone, id_map = self.pipeline.duplicate_with_origin(img.preview)
                target = id_map.get(self._selected_node_id)
                if target is None:
                    entries.append((img.name, None, "missing in clone"))
                    continue
                result = clone.compute(target)
                entries.append((img.name, result, None))
            except PipelineError as exc:
                entries.append((img.name, None, str(exc)))
            except Exception as exc:  # noqa: BLE001
                entries.append((img.name, None, str(exc)))
        self.batch_grid.set_results(entries)

    # ------------------------------------------------------------------
    # Job save / load
    # ------------------------------------------------------------------
    def _save_job(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save preprocessing job", "preprocessing.apt.json", _JOB_FILTER
        )
        if not path:
            return
        try:
            save_job(self.pipeline, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self._show_status(f"Job saved → {os.path.basename(path)}")

    def _load_job(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load preprocessing job", "", _JOB_FILTER
        )
        if not path:
            return
        try:
            new_pipeline = load_job(path)
        except JobFormatError as exc:
            QMessageBox.critical(self, "Bad job file", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", str(exc))
            return
        # Confirm if the existing graph has user work.
        if any(n.op_key != "origin" for n in self.pipeline.nodes()):
            if QMessageBox.question(
                self,
                "Replace current graph?",
                "현재 그래프의 모든 노드를 덮어쓰고 job 파일을 불러올까요?",
            ) != QMessageBox.Yes:
                return
        self.pipeline = new_pipeline
        self.scene.set_pipeline(new_pipeline)
        # Re-attach the active image (loaded job has no images).
        self._apply_active_image_to_pipeline()
        self.param_form.clear()
        self._selected_node_id = ""
        self._show_status(f"Job loaded ← {os.path.basename(path)}")
        # Fit view so user sees the whole loaded graph immediately.
        QTimer.singleShot(50, self.view.fit_to_content)
        self._refresh_all()

    # ------------------------------------------------------------------
    # Export (all leaves × all images, full resolution)
    # ------------------------------------------------------------------
    def _export_outputs(self) -> None:
        if not self._images:
            QMessageBox.warning(self, "Export", "이미지를 먼저 로드하세요.")
            return
        leaves = [nid for nid in self.pipeline.output_ids() if nid != Pipeline.ORIGIN_ID]
        if not leaves:
            QMessageBox.information(
                self, "Export",
                "내보낼 leaf 노드가 없습니다. op 노드를 추가하고 Origin과 연결하세요.",
            )
            return
        target_dir = QFileDialog.getExistingDirectory(
            self, "Select export folder", "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if not target_dir:
            return

        saved: list[str] = []
        errors: list[str] = []
        # For each image, clone the pipeline at full resolution, compute every leaf.
        for img in self._images:
            try:
                full_pipeline, id_map = self.pipeline.duplicate_with_origin(img.full)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{img.name}: clone failed — {exc}")
                continue
            base = Path(img.path).stem
            for original_leaf in leaves:
                cloned_leaf = id_map.get(original_leaf)
                if cloned_leaf is None:
                    errors.append(f"{img.name}/{original_leaf}: missing in clone")
                    continue
                try:
                    result = full_pipeline.compute(cloned_leaf)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{img.name}/{original_leaf}: {exc}")
                    continue
                out_path = os.path.join(target_dir, f"{base}__{original_leaf}.png")
                try:
                    ok, buf = cv2.imencode(".png", result)
                    if not ok:
                        raise IOError("cv2.imencode failed")
                    with open(out_path, "wb") as fh:
                        fh.write(buf.tobytes())
                    saved.append(out_path)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{img.name}/{original_leaf}: write — {exc}")
        msg_lines = [f"Saved {len(saved)} file(s) to:\n{target_dir}\n"]
        if errors:
            msg_lines.append(f"⚠ {len(errors)} error(s):")
            msg_lines.extend("  " + e for e in errors[:20])
            if len(errors) > 20:
                msg_lines.append(f"  …and {len(errors) - 20} more (see error.log)")
                for e in errors:
                    logging.error("Export error: %s", e)
        QMessageBox.information(self, "Export complete", "\n".join(msg_lines))

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
    """Read JPG/PNG/BMP as BGR uint8 (Unicode-safe via cv2.imdecode)."""
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
