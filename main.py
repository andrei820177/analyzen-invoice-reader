from __future__ import annotations

import sys
import os

# Ensure the project root is in Python path when running as script or frozen
if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(sys.executable)
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import json

# NOTE: keep this module free of top-level Qt / UI imports. The batch extractor
# uses a process pool (spawn) whose workers re-import this module; importing Qt
# here would load it into every worker for nothing. ui.theme is Qt-light.
from ui.theme import THEME, apply_palette


def _initial_mode() -> str:
    try:
        with open(os.path.join(ROOT, "config", "settings.json"), encoding="utf-8") as f:
            return json.load(f).get("theme", "light")
    except Exception:
        return "light"


# Set the theme BEFORE the UI widgets are imported (done inside main), so the
# modules' import-time style constants pick up the correct light/dark tokens.
THEME.set_mode(_initial_mode())


# kept for backward compatibility (tests call apply_light_theme)
def apply_light_theme(app) -> None:
    apply_palette(app)


def main() -> None:
    # Make Windows show our taskbar icon (not python.exe's) by giving the
    # process its own explicit AppUserModelID. Must run before any window.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Analyzen.InvoiceReader")
        except Exception:
            pass

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    from ui.main_window import MainWindow
    from ui.assets import app_qicon

    # Crisp fractional DPI scaling. Must be set before QApplication is created.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Analyzen Invoice Reader")
    app.setOrganizationName("Analyzen")
    apply_palette(app)
    app.setWindowIcon(app_qicon())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()   # required for the process pool / frozen exe
    main()
