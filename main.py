"""AIVEX Processing Tool — application entry point.

The whole UI / worker stack lives under the ``apt/`` package; this file simply
boots it. PyInstaller builds also use this file as the entry script.
"""

from __future__ import annotations

import sys

from apt.app import main


if __name__ == "__main__":
    sys.exit(main())

# ----------------------------------------------------------------------
# Build to .exe (PyInstaller) — run from the repo root in PowerShell:
#
# 1) Install PyInstaller into the project venv:
#    AiV_ProTool\Scripts\python.exe -m pip install pyinstaller
#
# 2) Build (uses APT.spec, outputs to dist/APT/APT.exe):
#    AiV_ProTool\Scripts\python.exe -m PyInstaller APT.spec
#
# Notes:
#   - Copy mim2color.exe into dist/APT/ if you need the MIM to BMP panel
#     (it's an external tool, intentionally not bundled by the spec).
#   - Clean rebuild: delete build/ and dist/ first, then re-run step 2.
# ----------------------------------------------------------------------
