"""Pytest fixtures shared across the AIVEX Processing Tool test suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make sure the project root is importable when pytest is run from anywhere.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.fixtures.tree_factory import (  # noqa: E402
    make_basic_sorting_tree,
    make_bmp_tree,
    make_ng_count_tree,
)


@pytest.fixture
def bmp_tree(tmp_path):
    """Create a small BMP tree (3 files in nested folders) and return its root."""
    return make_bmp_tree(tmp_path)


@pytest.fixture
def ng_count_tree(tmp_path):
    """Build a minimal NG-folder layout for counting tests."""
    return make_ng_count_tree(tmp_path)


@pytest.fixture
def basic_sorting_tree(tmp_path):
    """Build a minimal Inner-ID list / source pair for Basic Sorting tests."""
    return make_basic_sorting_tree(tmp_path)


@pytest.fixture
def qt_app():
    """Provide a headless QApplication so panel tests can construct widgets."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    yield app
