"""
Central theme tokens for light/dark mode.

Widgets build their stylesheets from C("token") instead of hard-coded hex, and
expose an apply_theme() that rebuilds the stylesheet. MainWindow.apply_theme_all()
re-themes the whole tree live when the mode changes.
"""

from __future__ import annotations

_LIGHT = {
    "desk":        "#e2e6ed",
    "surface":     "#fefefe",
    "surface2":    "#f6f7f9",
    "surface3":    "#f0f1f5",
    "sidebar":     "#f4f5f8",
    "header":      "#fefefe",

    "ink":         "#2e3552",
    "ink2":        "#5d6480",
    "ink3":        "#6b7291",
    "ink4":        "#939ab0",

    "line":        "#e3e5ec",
    "line2":       "#f0f1f5",

    "accent":      "#2f8f6b",
    "accent_press": "#1e7558",
    "accent_ink":  "#1a6b4f",
    "accent_soft": "#e6f0eb",
    "sel":         "rgba(47,143,107,0.12)",

    "warn":        "#d8a72e",
    "warn_soft":   "#f9f0dd",
    "warn_ink":    "#8a6d1a",
    "err":         "#e2483a",
    "err_soft":    "#faeae7",
    "err_ink":     "#b3261e",
    "ok":          "#2f8f6b",

    "scroll":      "#cdd0db",
    "scroll_hover": "#adb1c2",
    "on_accent":   "#ffffff",

    # palette-level (for native widgets)
    "disabled":    "#b8bdcc",
    "tooltip_border": "#d6d9e3",
    "shadow":      "rgba(16,24,40,0.16)",
}

_DARK = {
    "desk":        "#0f131b",
    "surface":     "#1a212e",
    "surface2":    "#222b3a",
    "surface3":    "#2b3445",
    "sidebar":     "#141a25",
    "header":      "#1a212e",

    "ink":         "#e7eaf3",
    "ink2":        "#aeb6c8",
    "ink3":        "#8a92a6",
    "ink4":        "#6a7286",

    "line":        "#2b3444",
    "line2":       "#232b39",

    "accent":      "#3aa57d",
    "accent_press": "#2f8f6b",
    "accent_ink":  "#7fd9b3",
    "accent_soft": "#1e3a30",
    "sel":         "rgba(58,165,125,0.22)",

    "warn":        "#e0b13f",
    "warn_soft":   "#3a3320",
    "warn_ink":    "#e6c878",
    "err":         "#e2483a",
    "err_soft":    "#3a2422",
    "err_ink":     "#f0a59c",
    "ok":          "#3aa57d",

    "scroll":      "#3a4456",
    "scroll_hover": "#4a5568",
    "on_accent":   "#ffffff",

    "disabled":    "#5a6275",
    "tooltip_border": "#3a4456",
    "shadow":      "rgba(0,0,0,0.45)",
}


class _Theme:
    def __init__(self) -> None:
        self._mode = "light"
        self._c = _LIGHT

    def set_mode(self, mode: str) -> None:
        self._mode = "dark" if str(mode).lower() == "dark" else "light"
        self._c = _DARK if self._mode == "dark" else _LIGHT

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_dark(self) -> bool:
        return self._mode == "dark"

    def color(self, key: str) -> str:
        return self._c.get(key, "#000000")


THEME = _Theme()


def C(key: str) -> str:
    """Current value of a theme token."""
    return THEME.color(key)
