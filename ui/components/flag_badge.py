from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel


class FlagBadge(QLabel):
    _STYLES = {
        "duplicate": ("D", "#f39c12", "#fff3e0"),
        "outlier":   ("!", "#e74c3c", "#fdecea"),
        "near_due":  ("S", "#e67e22", "#fff8e1"),
        "scanned":   ("O", "#3498db", "#e3f2fd"),
        "low_conf":  ("?", "#9b59b6", "#f3e5f5"),
    }

    def __init__(self, flag_type: str, parent=None):
        super().__init__(parent)
        letter, fg, bg = self._STYLES.get(flag_type, ("?", "#888", "#eee"))
        self.setText(letter)
        self.setFixedSize(18, 18)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background:{bg};color:{fg};border-radius:9px;"
            f"font-size:10px;font-weight:bold;"
        )
        tooltips = {
            "duplicate": "Duplicat",
            "outlier":   "Valoare atipica",
            "near_due":  "Scadenta apropiata",
            "scanned":   "PDF scanat (OCR)",
            "low_conf":  "Incredere scazuta",
        }
        self.setToolTip(tooltips.get(flag_type, flag_type))
