import sys
import os

# Ensure the project root is in Python path when running as script or frozen
if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(sys.executable)
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow

# Crisp fractional DPI scaling (125%, 150%, ...) so the window stays sharp and
# correctly sized across different monitor resolutions. Must be set before the
# QApplication is constructed.
QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)


def apply_light_theme(app: QApplication) -> None:
    """Force a consistent light theme regardless of the OS theme.

    The UI uses hard-coded light surfaces, so native widgets (message boxes,
    file dialogs, spin-box arrows, popups) must not inherit a dark OS palette —
    otherwise they render dark-on-dark or white-on-white. Fusion fully honours
    the palette below; the platform style only partially does.
    """
    app.setStyle("Fusion")

    pal = QPalette()
    ink      = QColor("#2e3552")
    muted    = QColor("#939ab0")
    surface  = QColor("#fefefe")
    desk     = QColor("#e2e6ed")
    accent   = QColor("#2f8f6b")

    pal.setColor(QPalette.ColorRole.Window,          desk)
    pal.setColor(QPalette.ColorRole.WindowText,      ink)
    pal.setColor(QPalette.ColorRole.Base,            surface)
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor("#f6f7f9"))
    pal.setColor(QPalette.ColorRole.Text,            ink)
    pal.setColor(QPalette.ColorRole.Button,          surface)
    pal.setColor(QPalette.ColorRole.ButtonText,      ink)
    pal.setColor(QPalette.ColorRole.ToolTipBase,     surface)
    pal.setColor(QPalette.ColorRole.ToolTipText,     ink)
    pal.setColor(QPalette.ColorRole.PlaceholderText, muted)
    pal.setColor(QPalette.ColorRole.Highlight,       accent)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))

    disabled = QColor("#b8bdcc")
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, disabled)

    app.setPalette(pal)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Analyzen Invoice Reader")
    app.setOrganizationName("Analyzen")
    apply_light_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
