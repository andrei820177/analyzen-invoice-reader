"""Resolve bundled asset paths (logos) for both dev and frozen builds."""

import os
import sys

from ui.theme import THEME


def asset_path(name: str) -> str:
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", name)


def logo_mark() -> str:
    """Transparent icon mark for the current theme (white on dark / ink on light)."""
    return asset_path("mark_dark.png" if THEME.is_dark else "mark_light.png")


def logo_full() -> str:
    """Transparent full logo (mark + wordmark) for the current theme."""
    return asset_path("logo_dark.png" if THEME.is_dark else "logo_light.png")


def app_icon() -> str:
    """Window/taskbar icon (full logo on its solid brand tile)."""
    return asset_path("darkmode_logo.png")
