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
