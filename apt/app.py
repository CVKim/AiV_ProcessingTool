"""Main window and application entry point for the AIVEX Processing Tool."""

from __future__ import annotations

import logging
import os
import signal
import sys

from PyQt5.QtCore import Qt, QThreadPool
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)


# ---------------------------------------------------------------------------
# Logging — write WARN+ to ``error.log`` next to the app, INFO+ to stderr.
# We install this from ``main()`` so importing apt.app inside tests does not
# clobber any pytest-managed logging config.
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    has_file = any(
        isinstance(h, logging.FileHandler) and getattr(h, "_apt_marker", False)
        for h in root.handlers
    )
    if has_file:
        return
    formatter = logging.Formatter(LOG_FORMAT)
    file_handler = logging.FileHandler("error.log", encoding="utf-8")
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(formatter)
    file_handler._apt_marker = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)
    # Console handler — INFO+ so launching from a terminal still surfaces
    # important events without polluting error.log with noise.
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)


def _install_excepthook() -> None:
    """Funnel unhandled exceptions through ``logging.error`` so they land in
    ``error.log`` before Qt prints to stderr and (sometimes) eats the trace."""
    previous = sys.excepthook

    def hook(exc_type, exc_value, tb):
        logging.error("Unhandled exception", exc_info=(exc_type, exc_value, tb))
        try:
            previous(exc_type, exc_value, tb)
        except Exception:  # noqa: BLE001
            sys.__excepthook__(exc_type, exc_value, tb)

    sys.excepthook = hook

from apt.brand import APP_NAME, APP_VERSION, ICON_FILENAME
from apt.dialogs import (
    AttachFOVPanel,
    BasicSortingPanel,
    BMPtoJPGPanel,
    CropPanel,
    DateBasedCopyPanel,
    ImageFormatCopyPanel,
    MIMtoBMPPanel,
    NGCountPanel,
    NGSortingPanel,
    PreprocessingPanel,
    SimulationFolderingPanel,
)
from apt.theme import QSS, apply_palette
from apt.widgets.sidebar import Sidebar


def _resource_path(filename: str) -> str | None:
    """Locate a bundled resource whether running from source or PyInstaller."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore[attr-defined]
        candidate = os.path.join(base, filename)
        if os.path.exists(candidate):
            return candidate
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.join(here, "resources", filename),
        os.path.join(here, "..", filename),
    ):
        candidate = os.path.normpath(candidate)
        if os.path.exists(candidate):
            return candidate
    return None


class MainWindow(QMainWindow):
    """Sidebar + stacked-pages main shell."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        icon_path = _resource_path(ICON_FILENAME)
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1280, 820)
        self.setMinimumSize(1100, 700)

        self.stack = QStackedWidget()

        # Page order is the canonical operation order shown in the sidebar.
        self.pages: list[tuple[str, str, type]] = [
            ("Sorting",       "Basic Sorting",        BasicSortingPanel),
            ("Sorting",       "NG Folder Sorting",    NGSortingPanel),
            ("Sorting",       "NG Count",             NGCountPanel),
            ("Copy",          "Date-Based Copy",      DateBasedCopyPanel),
            ("Copy",          "Image Format Copy",    ImageFormatCopyPanel),
            ("Copy",          "Simulation Foldering", SimulationFolderingPanel),
            ("Image Ops",     "Crop",                 CropPanel),
            ("Image Ops",     "Attach FOV",           AttachFOVPanel),
            ("Image Ops",     "BMP to JPG (BTJ)",     BMPtoJPGPanel),
            ("Image Ops",     "Preprocessing",        PreprocessingPanel),
            ("Conversion",    "MIM to BMP",           MIMtoBMPPanel),
        ]
        sections: dict[str, list[tuple[str, int]]] = {}
        for idx, (section, label, panel_cls) in enumerate(self.pages):
            panel = panel_cls()
            self.stack.addWidget(panel)
            sections.setdefault(section, []).append((label, idx))

        # Preserve section insertion order based on `pages` declaration.
        ordered_sections: list[tuple[str, list[tuple[str, int]]]] = []
        for section, _label, _cls in self.pages:
            if not any(s == section for s, _ in ordered_sections):
                ordered_sections.append((section, sections[section]))

        self.sidebar = Sidebar(ordered_sections)
        self.sidebar.navigated.connect(self.stack.setCurrentIndex)
        self.sidebar.select(0)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(container)

        # Status bar: version stamp on the right.
        status = self.statusBar()
        status.showMessage(f"{APP_NAME}  ·  v{APP_VERSION}")

    def closeEvent(self, event) -> None:  # noqa: N802
        """Best-effort cleanup of any running workers before exit."""
        for i in range(self.stack.count()):
            panel = self.stack.widget(i)
            worker = getattr(panel, "worker", None)
            if worker is not None and worker.isRunning():
                worker.stop()
                worker.wait(500)
        QThreadPool.globalInstance().clear()
        super().closeEvent(event)


def main() -> int:
    # Allow Ctrl+C to terminate cleanly when launched from a terminal.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    _setup_logging()
    _install_excepthook()
    logging.info("Launching %s v%s", APP_NAME, APP_VERSION)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)
    apply_palette(app)
    app.setStyleSheet(QSS)

    icon_path = _resource_path(ICON_FILENAME)
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    # Make sure the OS knows we accept high-DPI rendering when available.
    try:
        app.setAttribute(Qt.AA_DontShowIconsInMenus, False)
    except Exception:
        pass

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
