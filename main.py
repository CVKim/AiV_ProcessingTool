"""AIVEX Processing Tool — application entry point.

The whole UI / worker stack lives under the ``apt/`` package; this file simply
boots it. PyInstaller builds also use this file as the entry script.
"""

from __future__ import annotations

import sys

from apt.app import main


if __name__ == "__main__":
    sys.exit(main())
