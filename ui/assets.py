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
    """Path to the multi-resolution .ico (used for the packaged exe)."""
    return asset_path("app.ico")


def app_qicon():
    """A QIcon carrying every provided icon size, so Windows picks the crisp
    one for the title bar, taskbar and Alt-Tab."""
    from PyQt6.QtGui import QIcon

    icon = QIcon()
    added = False
    for size in (16, 32, 48, 64, 128, 256, 512):
        p = asset_path(os.path.join("taskbar_icon", f"icon-{size}.png"))
        if os.path.isfile(p):
            icon.addFile(p)
            added = True
    if not added:
        icon.addFile(app_icon())
    return icon
