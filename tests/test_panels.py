"""Smoke tests that construct every panel under a headless QApplication
and verify ``get_parameters`` returns the expected operation key.
"""

from __future__ import annotations

import pytest

from apt.constants import (
    OP_ATTACH_FOV,
    OP_BASIC_SORTING,
    OP_BTJ,
    OP_CROP,
    OP_DATE_COPY,
    OP_IMAGE_COPY,
    OP_MIM_TO_BMP,
    OP_NG_COUNT,
    OP_NG_SORTING,
    OP_SIMULATION,
)


@pytest.mark.parametrize(
    "import_path, expected_op",
    [
        ("apt.dialogs.basic_sorting.BasicSortingPanel",        OP_BASIC_SORTING),
        ("apt.dialogs.ng_sorting.NGSortingPanel",              OP_NG_SORTING),
        ("apt.dialogs.ng_count.NGCountPanel",                  OP_NG_COUNT),
        ("apt.dialogs.date_copy.DateBasedCopyPanel",           OP_DATE_COPY),
        ("apt.dialogs.image_copy.ImageFormatCopyPanel",        OP_IMAGE_COPY),
        ("apt.dialogs.simulation.SimulationFolderingPanel",    OP_SIMULATION),
        ("apt.dialogs.crop.CropPanel",                         OP_CROP),
        ("apt.dialogs.mim_to_bmp.MIMtoBMPPanel",               OP_MIM_TO_BMP),
        ("apt.dialogs.attach_fov.AttachFOVPanel",              OP_ATTACH_FOV),
        ("apt.dialogs.btj.BMPtoJPGPanel",                      OP_BTJ),
    ],
)
def test_each_panel_constructs_and_reports_its_operation(qt_app, import_path, expected_op):
    module_path, class_name = import_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    panel_cls = getattr(module, class_name)
    panel = panel_cls()
    params = panel.get_parameters()
    assert params.get("operation") == expected_op


def test_main_window_lists_all_pages(qt_app):
    from apt.app import MainWindow

    win = MainWindow()
    titles = [win.stack.widget(i).TITLE for i in range(win.stack.count())]
    assert len(titles) == 11
    assert "Basic Sorting" in titles
    assert "MIM to BMP" in titles
    assert "Preprocessing" in titles


def test_preprocessing_delete_clears_multiselection_in_one_call(qt_app):
    """Regression: multi-select + Delete used to leave items behind because
    _rebuild_edges fired per-item and invalidated the snapshot mid-iteration."""
    from apt.app import MainWindow
    from apt.dialogs.preprocessing import PreprocessingPanel
    from apt.preprocessing import Pipeline
    from apt.widgets.node_graph import NodeItem

    win = MainWindow()
    panel = next(
        win.stack.widget(i) for i in range(win.stack.count())
        if isinstance(win.stack.widget(i), PreprocessingPanel)
    )
    panel._add_op("gaussian_blur")
    panel._add_op("canny")
    panel._add_op("brightness_contrast")
    panel._add_op("blend")
    ids = {n.op_key: n.id for n in panel.pipeline.nodes() if n.op_key != "origin"}
    panel.pipeline.connect(Pipeline.ORIGIN_ID, ids["gaussian_blur"], 0)
    panel.pipeline.connect(ids["gaussian_blur"], ids["canny"], 0)
    panel.pipeline.connect(Pipeline.ORIGIN_ID, ids["brightness_contrast"], 0)
    panel.pipeline.connect(ids["canny"], ids["blend"], 0)
    panel.pipeline.connect(ids["brightness_contrast"], ids["blend"], 1)
    panel.scene._rebuild_edges()

    # Select two non-origin nodes and call remove_selected once.
    panel.scene.clearSelection()
    target_ids = {ids["canny"], ids["brightness_contrast"]}
    for it in panel.scene.items():
        if isinstance(it, NodeItem) and it.node_id in target_ids:
            it.setSelected(True)
    panel.scene.remove_selected()

    keys = {n.op_key for n in panel.pipeline.nodes()}
    assert "canny" not in keys
    assert "brightness_contrast" not in keys
    assert {"origin", "gaussian_blur", "blend"} <= keys


def test_preprocessing_image_switch_is_stable(qt_app):
    """Regression: swapping the active image used to leave the preview /
    params stale because exceptions in the refresh path were silenced."""
    import numpy as np
    from apt.app import MainWindow
    from apt.dialogs.preprocessing import LoadedImage, PreprocessingPanel

    win = MainWindow()
    panel = next(
        win.stack.widget(i) for i in range(win.stack.count())
        if isinstance(win.stack.widget(i), PreprocessingPanel)
    )
    panel._images = [
        LoadedImage("a.bmp", np.full((30, 30, 3), 50, np.uint8),
                    np.full((30, 30, 3), 50, np.uint8)),
        LoadedImage("b.bmp", np.full((30, 30, 3), 200, np.uint8),
                    np.full((30, 30, 3), 200, np.uint8)),
    ]
    panel._active_index = 0
    panel._sync_image_strip()
    panel._apply_active_image_to_pipeline()
    panel._on_image_selected(1)
    assert panel._active_index == 1
    panel._on_image_selected(0)
    assert panel._active_index == 0


def test_preprocessing_properties_panel_populates_from_compute(qt_app):
    """After a compute, the inspector's Properties panel shows the selected
    node's Name / Type / Status / Time / I-O / Shape — the data needed to
    reproduce the Cognex-style per-tool readout."""
    import numpy as np
    from apt.app import MainWindow
    from apt.dialogs.preprocessing import LoadedImage, PreprocessingPanel
    from apt.preprocessing import Pipeline

    win = MainWindow()
    panel = next(
        win.stack.widget(i) for i in range(win.stack.count())
        if isinstance(win.stack.widget(i), PreprocessingPanel)
    )
    img = np.full((50, 50, 3), 80, dtype=np.uint8)
    panel._images = [LoadedImage("t.bmp", img, img)]
    panel._active_index = 0
    panel._sync_image_strip()
    panel._apply_active_image_to_pipeline()

    panel._add_op("gaussian_blur")
    blur_id = next(n.id for n in panel.pipeline.nodes() if n.op_key == "gaussian_blur")
    panel.pipeline.connect(Pipeline.ORIGIN_ID, blur_id, 0)
    panel.scene._rebuild_edges()
    panel._selected_node_id = blur_id
    panel._recompute_preview()

    node = panel.pipeline.get(blur_id)
    assert node.last_status == "success"
    assert node.last_time_ms >= 0.0
    # Properties widget should reflect that the node has 1 wired input and 0 downstream.
    panel._refresh_properties_for(blur_id)
    # Smoke: widget renders without raising; status text is the success label.
    assert panel.properties._status_label.text() == "Success"
    assert "Gaussian Blur" in panel.properties._type.text()


def test_preprocessing_drag_to_occupied_port_forks_single_input_op(qt_app):
    """Dragging a second connection to a single-input op's already-connected
    port must NOT silently overwrite. The destination node should be cloned
    with the same params so both upstream branches survive."""
    from apt.app import MainWindow
    from apt.dialogs.preprocessing import PreprocessingPanel
    from apt.preprocessing import Pipeline
    from apt.widgets.node_graph import NodeItem

    win = MainWindow()
    panel = next(
        win.stack.widget(i) for i in range(win.stack.count())
        if isinstance(win.stack.widget(i), PreprocessingPanel)
    )

    panel._add_op("crop_xywh")
    panel._add_op("resize")
    panel._add_op("window_stretch")
    ids = {n.op_key: n.id for n in panel.pipeline.nodes() if n.op_key != "origin"}
    panel.pipeline.connect(Pipeline.ORIGIN_ID, ids["crop_xywh"], 0)
    panel.pipeline.connect(Pipeline.ORIGIN_ID, ids["resize"], 0)
    panel.pipeline.connect(ids["crop_xywh"], ids["window_stretch"], 0)
    panel.pipeline.set_param(ids["window_stretch"], "lower", 100)
    panel.pipeline.set_param(ids["window_stretch"], "upper", 200)
    panel.scene._rebuild_edges()

    ws_item = panel.scene._nodes[ids["window_stretch"]]
    resize_item = panel.scene._nodes[ids["resize"]]

    # Simulate dragging Resize → WS (port already taken by Crop)
    panel.scene._connect_or_fork(resize_item.output, ws_item.inputs[0])

    ws_nodes = [n for n in panel.pipeline.nodes() if n.op_key == "window_stretch"]
    assert len(ws_nodes) == 2, "destination should have been auto-forked"
    original = panel.pipeline.get(ids["window_stretch"])
    forked = next(n for n in ws_nodes if n.id != ids["window_stretch"])

    # Original keeps its input; fork wires to Resize.
    assert original.inputs[0] == ids["crop_xywh"]
    assert forked.inputs[0] == ids["resize"]
    # Params copied verbatim — user can edit independently afterwards.
    assert forked.params["lower"] == 100
    assert forked.params["upper"] == 200


def test_preprocessing_drag_to_occupied_port_replaces_for_multi_input_op(qt_app):
    """Combine ops (Blend, Add, ...) take 2 deliberate inputs. Dragging a
    second source to an already-connected specific port should REPLACE,
    not fork — the user is changing that particular input by hand."""
    from apt.app import MainWindow
    from apt.dialogs.preprocessing import PreprocessingPanel
    from apt.preprocessing import Pipeline

    win = MainWindow()
    panel = next(
        win.stack.widget(i) for i in range(win.stack.count())
        if isinstance(win.stack.widget(i), PreprocessingPanel)
    )

    panel._add_op("crop_xywh")
    panel._add_op("resize")
    panel._add_op("blend")
    ids = {n.op_key: n.id for n in panel.pipeline.nodes() if n.op_key != "origin"}
    panel.pipeline.connect(Pipeline.ORIGIN_ID, ids["crop_xywh"], 0)
    panel.pipeline.connect(Pipeline.ORIGIN_ID, ids["resize"], 0)
    panel.pipeline.connect(ids["crop_xywh"], ids["blend"], 0)
    panel.scene._rebuild_edges()

    blend_item = panel.scene._nodes[ids["blend"]]
    resize_item = panel.scene._nodes[ids["resize"]]
    panel.scene._connect_or_fork(resize_item.output, blend_item.inputs[0])

    # No fork — input 0 was simply replaced.
    blend_nodes = [n for n in panel.pipeline.nodes() if n.op_key == "blend"]
    assert len(blend_nodes) == 1
    assert blend_nodes[0].inputs[0] == ids["resize"]


def test_preprocessing_redrop_same_source_is_noop(qt_app):
    """Dropping the exact same connection onto the same port shouldn't
    create a fork or change anything."""
    from apt.app import MainWindow
    from apt.dialogs.preprocessing import PreprocessingPanel
    from apt.preprocessing import Pipeline

    win = MainWindow()
    panel = next(
        win.stack.widget(i) for i in range(win.stack.count())
        if isinstance(win.stack.widget(i), PreprocessingPanel)
    )
    panel._add_op("gaussian_blur")
    blur_id = next(n.id for n in panel.pipeline.nodes() if n.op_key == "gaussian_blur")
    panel.pipeline.connect(Pipeline.ORIGIN_ID, blur_id, 0)
    panel.scene._rebuild_edges()

    blur_item = panel.scene._nodes[blur_id]
    origin_item = panel.scene._nodes[Pipeline.ORIGIN_ID]
    pre_count = len(list(panel.pipeline.nodes()))
    panel.scene._connect_or_fork(origin_item.output, blur_item.inputs[0])
    assert len(list(panel.pipeline.nodes())) == pre_count


def test_zoomable_preview_preserves_zoom_for_same_shape(qt_app):
    """When a new image of the same shape replaces the current one, the
    user's manual zoom should be kept. Different shape → auto-refit."""
    import numpy as np
    from apt.widgets.zoomable_image import ZoomableImageView

    view = ZoomableImageView()
    view.resize(400, 300)
    img = np.full((200, 300, 3), 128, dtype=np.uint8)
    view.set_image(img)
    view.zoom_to_100()
    assert view.current_zoom() == 1.0

    # Same shape — zoom must be preserved.
    img2 = np.full((200, 300, 3), 80, dtype=np.uint8)
    view.set_image(img2)
    assert view.current_zoom() == 1.0

    # Different shape — view should refit (zoom changes).
    img3 = np.full((100, 100, 3), 200, dtype=np.uint8)
    view.set_image(img3)
    # Just assert it changed away from 1.0 — exact factor depends on viewport.
    assert view.current_zoom() != 1.0


def test_preprocessing_image_navigation_shortcuts_step_and_wrap(qt_app):
    """``]`` / ``[`` (and ``.`` / ``,``) walk the loaded image set with
    wrap-around. Active index updates, ``_on_image_selected`` runs the
    refresh, and the strip's active highlight follows."""
    import numpy as np
    from apt.app import MainWindow
    from apt.dialogs.preprocessing import LoadedImage, PreprocessingPanel

    win = MainWindow()
    panel = next(
        win.stack.widget(i) for i in range(win.stack.count())
        if isinstance(win.stack.widget(i), PreprocessingPanel)
    )
    panel._images = [
        LoadedImage(f"{ch}.bmp", np.zeros((8, 8, 3), np.uint8),
                    np.zeros((8, 8, 3), np.uint8))
        for ch in "abcd"
    ]
    panel._active_index = 1
    panel._sync_image_strip()
    panel._apply_active_image_to_pipeline()

    panel._activate_next_image()
    assert panel._active_index == 2
    panel._activate_next_image()
    panel._activate_next_image()
    assert panel._active_index == 0   # wrapped past the end
    panel._activate_prev_image()
    assert panel._active_index == 3   # wrapped past the start


def test_preprocessing_navigation_is_noop_with_under_two_images(qt_app):
    import numpy as np
    from apt.app import MainWindow
    from apt.dialogs.preprocessing import LoadedImage, PreprocessingPanel

    win = MainWindow()
    panel = next(
        win.stack.widget(i) for i in range(win.stack.count())
        if isinstance(win.stack.widget(i), PreprocessingPanel)
    )
    # Zero images
    panel._images = []
    panel._active_index = -1
    panel._activate_next_image()
    panel._activate_prev_image()
    assert panel._active_index == -1

    # One image — shortcuts should not move it.
    panel._images = [
        LoadedImage("only.bmp", np.zeros((4, 4, 3), np.uint8),
                    np.zeros((4, 4, 3), np.uint8)),
    ]
    panel._active_index = 0
    panel._sync_image_strip()
    panel._activate_next_image()
    panel._activate_prev_image()
    assert panel._active_index == 0


def test_preprocessing_remove_active_image_picks_safe_index(qt_app):
    import numpy as np
    from apt.app import MainWindow
    from apt.dialogs.preprocessing import LoadedImage, PreprocessingPanel

    win = MainWindow()
    panel = next(
        win.stack.widget(i) for i in range(win.stack.count())
        if isinstance(win.stack.widget(i), PreprocessingPanel)
    )
    panel._images = [
        LoadedImage(f"{ch}.bmp", np.zeros((10, 10, 3), np.uint8),
                    np.zeros((10, 10, 3), np.uint8))
        for ch in "abc"
    ]
    panel._active_index = 2
    panel._sync_image_strip()
    panel._on_image_removed(2)  # remove the active one
    assert len(panel._images) == 2
    assert panel._active_index == 1   # falls back to previous
    panel._on_image_removed(0)  # remove a non-active before active
    assert len(panel._images) == 1
    assert panel._active_index == 0   # shifted down
