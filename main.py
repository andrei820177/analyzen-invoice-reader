import sys
import os

# Ensure the project root is in Python path when running as script or frozen
if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(sys.executable)
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ui.theme import THEME, apply_palette


def _initial_mode() -> str:
    try:
        with open(os.path.join(ROOT, "config", "settings.json"), encoding="utf-8") as f:
            return json.load(f).get("theme", "light")
    except Exception:
        return "light"


# Set the theme BEFORE importing the UI widgets, so module-level style constants
# (computed at import time) pick up the correct light/dark tokens.
THEME.set_mode(_initial_mode())

from ui.main_window import MainWindow  # noqa: E402

# Crisp fractional DPI scaling (125%, 150%, ...) so the window stays sharp and
# correctly sized across different monitor resolutions. Must be set before the
# QApplication is constructed.
QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)


# kept for backward compatibility (tests call apply_light_theme)
def apply_light_theme(app: QApplication) -> None:
    apply_palette(app)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Analyzen Invoice Reader")
    app.setOrganizationName("Analyzen")
    apply_palette(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
