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

_log = logging.getLogger("apt.preprocessing.panel")

import cv2
import numpy as np
from PyQt5.QtCore import QEvent, Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
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
from apt.widgets.image_strip import ImageStrip
from apt.widgets.node_properties import NodePropertiesPanel
from apt.widgets.op_picker import OpPicker
from apt.widgets.parameter_form import ParameterForm
from apt.widgets.node_graph import NodeScene, NodeView
from apt.widgets.zoomable_image import ZoomableImageView


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
        # Hook an app-wide key filter so A/D can navigate images without
        # stealing keystrokes from text-entry widgets (search box, etc.).
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

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
            "Canvas:  F = fit  ·  Ctrl+0 = reset zoom  ·  Ctrl+D = duplicate  ·  "
            "Ctrl+A = select all  ·  Esc = deselect  ·  ←↑↓→ = nudge "
            "(Shift = ×5)  ·  Space + drag = pan  ·  Right-click node = menu"
            "<br>Images:  <b>A</b> = previous  ·  <b>D</b> = next  "
            "<span style='color:#6E7079;'>(disabled while typing in a field)</span>"
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

        properties_group = QGroupBox("Properties")
        properties_layout = QVBoxLayout(properties_group)
        properties_layout.setContentsMargins(10, 14, 10, 10)
        self.properties = NodePropertiesPanel()
        properties_layout.addWidget(self.properties)
        layout.addWidget(properties_group, 0)

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
        # Tab 1: single active image (zoomable / pannable)
        active_tab = QWidget()
        active_layout = QVBoxLayout(active_tab)
        active_layout.setContentsMargins(4, 4, 4, 4)
        active_layout.setSpacing(4)
        self.preview = ZoomableImageView()
        active_layout.addWidget(self.preview, 1)
        self.preview_meta = QLabel("(no node selected)")
        self.preview_meta.setStyleSheet("color: #9A9CA3; font-size: 11px;")
        self.preview_meta.setToolTip(
            "Wheel = zoom · drag = pan · double-click = toggle fit / 1:1"
        )
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
            _log.warning("Image select: index %d out of range (have %d)", index, len(self._images))
            return
        if index == self._active_index:
            return  # no-op click on the already-active card
        self._active_index = index
        self.image_strip.set_active(index)
        self._apply_active_image_to_pipeline()
        # Show "computing…" placeholder so the user doesn't think the click
        # was lost while the batch grid is being rebuilt.
        if self.preview_tabs.currentIndex() == 1 and len(self._images) > 1:
            self.batch_grid.set_header(
                f"Switching to <b>{self._images[index].name}</b> — recomputing…"
            )
        self._refresh_all()

    def _on_image_removed(self, index: int) -> None:
        if not (0 <= index < len(self._images)):
            return
        removed_name = self._images[index].name
        del self._images[index]
        if not self._images:
            self._active_index = -1
        elif self._active_index == index:
            # Removed the active one — pick the previous (or 0).
            self._active_index = max(0, index - 1)
        elif self._active_index > index:
            # Active index shifts down by one.
            self._active_index -= 1
        self._sync_image_strip()
        self._apply_active_image_to_pipeline()
        self._show_status(f"Removed {removed_name}")
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

    # ------------------------------------------------------------------
    # Keyboard navigation across loaded images
    # ------------------------------------------------------------------
    # Bindings: D = next image, A = previous image (WASD-style).
    #
    # Implemented as an application-level event filter rather than a
    # QShortcut because A/D are valid letters in the operation search
    # field; we must let those keystrokes pass through whenever the
    # focused widget is a text-entry control. QShortcut would
    # unconditionally swallow the key.

    _NAV_TEXT_TYPES = (QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() != QEvent.KeyPress:
            return super().eventFilter(obj, event)
        if event.modifiers() != Qt.NoModifier:
            return super().eventFilter(obj, event)
        key = event.key()
        if key not in (Qt.Key_A, Qt.Key_D):
            return super().eventFilter(obj, event)
        # Only intercept while focus is inside *this* panel — otherwise other
        # panels (Basic Sorting, NG Count, …) would lose their A/D too.
        focus = QApplication.focusWidget()
        if focus is None or (focus is not self and not self.isAncestorOf(focus)):
            return super().eventFilter(obj, event)
        # Hand the key back to text-entry widgets verbatim.
        if isinstance(focus, self._NAV_TEXT_TYPES):
            return super().eventFilter(obj, event)
        if isinstance(focus, QComboBox) and focus.isEditable():
            return super().eventFilter(obj, event)
        if key == Qt.Key_D:
            self._activate_next_image()
            return True
        if key == Qt.Key_A:
            self._activate_prev_image()
            return True
        return super().eventFilter(obj, event)

    def _activate_next_image(self) -> None:
        self._step_active_image(+1)

    def _activate_prev_image(self) -> None:
        self._step_active_image(-1)

    def _step_active_image(self, delta: int) -> None:
        count = len(self._images)
        if count < 2:
            if count == 1:
                self._show_status("Only one image loaded.")
            return
        new_index = (self._active_index + delta) % count
        self._on_image_selected(new_index)
        active_name = self._images[new_index].name
        arrow = "→" if delta > 0 else "←"
        self._show_status(f"{arrow} Active: {active_name}  ({new_index + 1}/{count})")

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
            self.properties.clear()
            self.preview.set_image(None)
            self.preview_meta.setText("(no node selected)")
            self.batch_grid.set_header("(no node selected)")
            self.batch_grid.set_results([])
            return
        try:
            node = self.pipeline.get(node_id)
        except PipelineError as exc:
            _log.warning("Selected node %r missing from pipeline: %s", node_id, exc)
            self.param_form.clear()
            self.properties.clear()
            self.preview.set_image(None)
            self.preview_meta.setText(f"⚠ Node not found ({node_id})")
            return
        except Exception:
            _log.exception("_on_node_selected: failed to look up node %r", node_id)
            return
        try:
            if node.op_key == "origin":
                self.param_form.show_params("Origin", (), {})
            else:
                op = get_operation(node.op_key)
                self.param_form.show_params(op.label, op.params, node.params)
        except Exception:
            _log.exception("_on_node_selected: param form for %r", node_id)
        self._refresh_properties_for(node_id)
        self._refresh_all()

    def _on_graph_changed(self) -> None:
        try:
            self._refresh_all()
        except Exception:
            _log.exception("_on_graph_changed: refresh failed")

    def _on_param_changed(self, name: str, value) -> None:
        if not self._selected_node_id:
            return
        try:
            node = self.pipeline.get(self._selected_node_id)
        except PipelineError as exc:
            _log.warning("Param change on missing node %r: %s", self._selected_node_id, exc)
            return
        if node.op_key == "origin":
            return
        try:
            self.pipeline.set_param(self._selected_node_id, name, value)
        except PipelineError as exc:
            self._show_status(str(exc))
            return
        except Exception:
            _log.exception("_on_param_changed: set_param failed (%s=%r)", name, value)
            return
        self.scene.refresh_node_params(self._selected_node_id)
        self._recompute_timer.start()
        if self.preview_tabs.currentIndex() == 1:
            self._batch_timer.start()

    def _on_preview_tab_changed(self, index: int) -> None:
        # Switching to the batch tab triggers a (deferred) recompute; the
        # active tab is already up to date from the last preview run.
        if index == 1:
            self._batch_timer.start()

    # ------------------------------------------------------------------
    # Preview / batch grid recomputation
    # ------------------------------------------------------------------
    def _refresh_all(self) -> None:
        """Refresh status + previews. Single-image preview is synchronous
        because it's cheap and the user expects to see it on click; the
        batch-grid recompute is deferred via a 120 ms timer so switching
        images / clicking nodes stays responsive even with many images
        loaded.
        """
        self._update_status_summary()
        try:
            self._recompute_preview()
        except Exception:
            logging.exception("preprocessing: _recompute_preview failed")
        if self.preview_tabs.currentIndex() == 1:
            self._batch_timer.start()

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
            self.scene.refresh_all_node_visuals()
            self._refresh_properties_for(self._selected_node_id)
            return
        except Exception as exc:  # noqa: BLE001
            self.preview.set_image(None)
            self.preview_meta.setText(f"⚠ {exc}")
            self.scene.refresh_all_node_visuals()
            self._refresh_properties_for(self._selected_node_id)
            return
        self.preview.set_image(result)
        h, w = result.shape[:2]
        ch = 1 if result.ndim == 2 else result.shape[2]
        node = self.pipeline.get(self._selected_node_id)
        active_name = self._images[self._active_index].name
        self.preview_meta.setText(
            f"{node.display_title()} ({node.id}) · {active_name} · {w}×{h}px · {ch}ch"
        )
        # Push per-node timings to the canvas + properties panel.
        self.scene.refresh_all_node_visuals()
        self._refresh_properties_for(self._selected_node_id)

    def _refresh_properties_for(self, node_id: str) -> None:
        if not node_id:
            self.properties.clear()
            return
        try:
            node = self.pipeline.get(node_id)
        except PipelineError:
            self.properties.clear()
            return
        downstream = NodePropertiesPanel.count_downstream(self.pipeline, node_id)
        self.properties.show_node(node, downstream)

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
        except PipelineError as exc:
            _log.warning("Batch grid: selected node %r gone (%s)", self._selected_node_id, exc)
            self.batch_grid.set_header(f"⚠ Selected node not found ({self._selected_node_id})")
            self.batch_grid.set_results([])
            return
        except Exception:
            _log.exception("Batch grid: lookup failed")
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
                _log.exception("Batch grid: compute failed for %s", img.name)
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
