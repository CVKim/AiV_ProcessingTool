"""AIVEX Processing Tool (APT).

Re-export the application entry point and brand metadata so callers can simply
``from apt import APP_NAME, run`` without reaching into private modules.
"""

from apt.brand import APP_NAME, APP_VERSION, COMPANY, TAGLINE

__all__ = ["APP_NAME", "APP_VERSION", "COMPANY", "TAGLINE", "run"]


def run() -> int:
    from apt.app import main
    return main()
