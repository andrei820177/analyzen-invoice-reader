from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox


class NoScrollComboBox(QComboBox):
    """Combo box that ignores mouse-wheel events.

    Prevents the value from changing accidentally when the user scrolls the
    surrounding view with the pointer over the combo. The wheel event is
    passed through so the parent scroll area moves instead.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()
