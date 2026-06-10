import sys
import os

# Ensure the project root is in Python path when running as script or frozen
if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(sys.executable)
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Analyzen Invoice Reader")
    app.setOrganizationName("Analyzen")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
