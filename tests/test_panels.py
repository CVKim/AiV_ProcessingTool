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
