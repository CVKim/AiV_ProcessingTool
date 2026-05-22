"""Capture deterministic screenshots of the AIVEX Processing Tool UI.

Runs Qt in offscreen mode and uses ``widget.grab()`` to render each scenario
to a PNG without ever opening a real window — so it works on a build server
or any headless environment.

Output:
    docs/screenshots/*.png

Re-run any time the UI changes; ``build_manual.py`` consumes whatever is
sitting in the screenshots folder.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the project root importable so `import apt` works when this script
# is launched from anywhere.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Use the native Windows platform so children actually paint. We then set
# Qt.WA_DontShowOnScreen on the main window so it never actually appears on
# the user's desktop — layout + paint events still fire, grab() captures the
# real rendering.
# (Pure offscreen platform paints QSS backgrounds but skips child widget
# content, producing near-blank PNGs.)
os.environ.pop("QT_QPA_PLATFORM", None)

# Korean Windows defaults stdout to cp949 — em-dashes in our log lines blow
# that up. Reconfigure to UTF-8 if available (Python 3.7+).
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from ctypes import windll

import win32gui
import win32ui
from PIL import Image
from PyQt5.QtCore import QPointF
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication


# PrintWindow flag for capturing a window via its DirectComposition surface,
# i.e. it works even when the window is occluded / off-screen.
PW_RENDERFULLCONTENT = 0x00000002


def capture_hwnd(hwnd: int) -> Image.Image:
    """Capture a Windows HWND's actual pixels regardless of occlusion."""
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    width, height = right - left, bottom - top
    # GetWindowRect → includes the title bar / non-client area; we want the
    # client area only so the captured PNG matches the on-screen widget.
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bitmap)
    try:
        result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)
        if not result:
            raise RuntimeError(f"PrintWindow failed for hwnd {hwnd}")
        info = bitmap.GetInfo()
        raw = bitmap.GetBitmapBits(True)
        img = Image.frombuffer(
            "RGB", (info["bmWidth"], info["bmHeight"]),
            raw, "raw", "BGRX", 0, 1,
        )
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
    return img


def _settle(ms: int = 200) -> None:
    """Pump the Qt event loop for ``ms`` milliseconds.

    ``processEvents()`` alone often isn't enough — the OS compositor needs
    real wall-clock time to actually paint into a newly-shown window's
    backing store. ``QTest.qWait`` blocks for the given duration while
    still processing events, which gives Windows time to draw.
    """
    QTest.qWait(ms)
    QApplication.processEvents()
    QApplication.sendPostedEvents()
    QApplication.processEvents()


def main() -> int:
    app = QApplication(sys.argv)

    # Apply the brand palette + stylesheet the same way apt.app:main does.
    from apt.theme import QSS, apply_palette
    apply_palette(app)
    app.setStyleSheet(QSS)

    from apt.app import MainWindow
    from apt.dialogs.preprocessing import PreprocessingPanel
    from apt.preprocessing import Pipeline
    from apt.widgets.node_graph import NodeItem

    win = MainWindow()
    WIN_X, WIN_Y, WIN_W, WIN_H = 80, 80, 1400, 900
    win.setGeometry(WIN_X, WIN_Y, WIN_W, WIN_H)
    # We need a REAL on-screen window so that QSplitter / QGraphicsView
    # children actually compute their sizes and paint their content.
    # Briefly visible on the user's desktop while the script cycles.
    win.show()
    win.raise_()
    win.activateWindow()
    _settle(700)  # let the OS compositor allocate + paint the window

    out_dir = Path("docs/screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)

    def save(name: str) -> None:
        from PyQt5.QtCore import QRectF
        from PyQt5.QtWidgets import QGraphicsScene
        cw = win.stack.currentWidget()
        from apt.dialogs.preprocessing import PreprocessingPanel
        if isinstance(cw, PreprocessingPanel):
            print(
                f"    state: {len(cw._images)} image(s), "
                f"{len(list(cw.pipeline.nodes()))} node(s)",
                flush=True,
            )
            # Hard-invalidate the entire scene + viewport. scene.update()
            # alone uses an internal cached layer for QGraphicsScene; only
            # invalidate(rect, AllLayers) blasts it open.
            cw.scene.invalidate(QRectF(), QGraphicsScene.AllLayers)
            cw.view.viewport().update()
            cw.view.viewport().repaint()
            cw.update()
            cw.repaint()
        win.repaint()
        _settle(500)
        # PrintWindow captures the window's actual pixels regardless of
        # whether another window (terminal, IDE) is sitting on top of it.
        hwnd = int(win.winId())
        img = capture_hwnd(hwnd)
        path = out_dir / f"{name}.png"
        img.save(str(path))
        print(f"  → {path}  ({img.size[0]}×{img.size[1]})", flush=True)

    def find_panel(cls):
        for i in range(win.stack.count()):
            w = win.stack.widget(i)
            if isinstance(w, cls):
                return i, w
        raise RuntimeError(f"{cls.__name__} not in main window")

    # =====================================================================
    # 01 — Main window on Basic Sorting (shows the sidebar + a typical
    # form-based panel)
    # =====================================================================
    print("\n[01] Main window — Basic Sorting")
    win.sidebar.select(0); win.stack.setCurrentIndex(0)
    save("01_main_basic_sorting")

    # =====================================================================
    # 02 — Preprocessing panel, empty canvas
    # =====================================================================
    print("\n[02] Preprocessing — empty canvas")
    pre_idx, panel = find_panel(PreprocessingPanel)
    win.sidebar.select(pre_idx)
    win.stack.setCurrentIndex(pre_idx)
    _settle()
    panel.view.fit_to_content()
    save("02_preprocessing_empty")

    # =====================================================================
    # 03 — Preprocessing after Load Samples (image strip populated, single
    # active preview visible)
    # =====================================================================
    print("\n[03] Preprocessing — samples loaded")
    panel._load_sample_images()
    _settle()
    panel.preview_tabs.setCurrentIndex(0)  # Active tab
    save("03_preprocessing_samples_loaded")

    # =====================================================================
    # 04 — Add one Grayscale node + connect to origin
    # =====================================================================
    print("\n[04] Preprocessing — first node")
    panel._add_op("to_gray")
    gray_id = next(n.id for n in panel.pipeline.nodes() if n.op_key == "to_gray")
    panel.pipeline.connect(Pipeline.ORIGIN_ID, gray_id, 0)
    panel.scene._rebuild_edges()
    panel._selected_node_id = gray_id
    panel._on_node_selected(gray_id)
    panel._recompute_preview()
    panel.scene.refresh_all_node_visuals()
    panel.view.fit_to_content()
    _settle()
    save("04_preprocessing_one_node")

    # =====================================================================
    # 05 — Full crack-detection pipeline (Origin → Grayscale → Crop →
    # Window Stretch → Resize Smooth) with auto-layout + leaf selected
    # =====================================================================
    print("\n[05] Preprocessing — full chain (crack-detection recipe)")
    for op in ("crop_xywh", "window_stretch", "resize_smooth"):
        panel._add_op(op)
    ids = {n.op_key: n.id for n in panel.pipeline.nodes() if n.op_key != "origin"}
    chain = ["to_gray", "crop_xywh", "window_stretch", "resize_smooth"]
    for prev, curr in zip(chain, chain[1:]):
        panel.pipeline.connect(ids[prev], ids[curr], 0)
    # Sensible parameter values matching the demo recipe.
    panel.pipeline.set_param(ids["crop_xywh"], "x", 100)
    panel.pipeline.set_param(ids["crop_xywh"], "y", 80)
    panel.pipeline.set_param(ids["crop_xywh"], "width", 600)
    panel.pipeline.set_param(ids["crop_xywh"], "height", 400)
    panel.pipeline.set_param(ids["window_stretch"], "lower", 80)
    panel.pipeline.set_param(ids["window_stretch"], "upper", 180)
    panel.pipeline.set_param(ids["resize_smooth"], "scale", 0.5)
    for nid in ids.values():
        panel.scene.refresh_node_params(nid)
    panel.scene._rebuild_edges()
    panel.scene.auto_layout()
    leaf_id = ids["resize_smooth"]
    panel._selected_node_id = leaf_id
    panel._on_node_selected(leaf_id)
    panel._recompute_preview()
    panel.scene.refresh_all_node_visuals()
    panel.view.fit_to_content()
    _settle()
    save("05_preprocessing_full_pipeline_active")

    # =====================================================================
    # 06 — Same pipeline, All Images tab (grid of leaf results)
    # =====================================================================
    print("\n[06] Preprocessing — All Images grid")
    panel.preview_tabs.setCurrentIndex(1)
    panel._recompute_batch_grid()
    _settle()
    save("06_preprocessing_all_images_grid")

    # =====================================================================
    # 07 — Fan-out branch (Crop output feeds two Window Stretches with
    # different windows — demonstrates the auto-fork affordance)
    # =====================================================================
    print("\n[07] Preprocessing — fan-out (3 window stretches)")
    crop_id = ids["crop_xywh"]
    extra_ws_ids = []
    for lower, upper in ((120, 200), (160, 240)):
        node = panel.pipeline.add_node("window_stretch")
        panel.pipeline.set_param(node.id, "lower", lower)
        panel.pipeline.set_param(node.id, "upper", upper)
        panel.pipeline.connect(crop_id, node.id, 0)
        panel.scene._add_node_item(node.id)
        extra_ws_ids.append(node.id)
    panel.scene._rebuild_edges()
    panel.scene.auto_layout()
    panel._selected_node_id = ids["window_stretch"]
    panel._on_node_selected(panel._selected_node_id)
    panel._recompute_preview()
    panel.scene.refresh_all_node_visuals()
    panel.view.fit_to_content()
    panel.preview_tabs.setCurrentIndex(0)
    _settle()
    save("07_preprocessing_fanout")

    # =====================================================================
    # 08 — NG Count panel (table layout, different visual style)
    # =====================================================================
    print("\n[08] NG Count panel")
    win.sidebar.select(2); win.stack.setCurrentIndex(2)  # NG Count is the 3rd entry in Sorting
    _settle()
    save("08_ng_count")

    # =====================================================================
    # 09 — MIM to BMP panel (showcases the INI editor)
    # =====================================================================
    print("\n[09] MIM to BMP panel")
    # Find the MIM to BMP panel by class name (last entry).
    from apt.dialogs.mim_to_bmp import MIMtoBMPPanel
    mim_idx, _ = find_panel(MIMtoBMPPanel)
    win.sidebar.select(mim_idx); win.stack.setCurrentIndex(mim_idx)
    _settle()
    save("09_mim_to_bmp")

    # =====================================================================
    # 10 — Crop panel (classic Image Ops form)
    # =====================================================================
    print("\n[10] Crop panel")
    from apt.dialogs.crop import CropPanel
    crop_idx, _ = find_panel(CropPanel)
    win.sidebar.select(crop_idx); win.stack.setCurrentIndex(crop_idx)
    _settle()
    save("10_crop_panel")

    print(f"\nAll screenshots → {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
