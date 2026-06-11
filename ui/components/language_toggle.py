from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QVBoxLayout, QWidget,
)
from PyQt6.QtGui import QColor, QGuiApplication

from ui.components.language_data import get_languages
from ui.theme import C


class _ClickFrame(QFrame):
    """A frame that emits clicked() on a left mouse release inside it."""

    clicked = pyqtSignal()

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class _LangRow(_ClickFrame):
    """One language row in the popup: native name + a check when selected."""

    def __init__(self, code: str, label: str, selected: bool, parent=None):
        super().__init__(parent)
        self.code = code
        self.setObjectName("langrow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        bg = C("accent_soft") if selected else "transparent"
        self.setStyleSheet(
            f"#langrow{{background:{bg};border-radius:7px;}}"
            f"#langrow:hover{{background:{C('surface3')};}}"
        )
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 6, 10, 6)
        h.setSpacing(8)
        name = QLabel(label)
        col = C("accent_ink") if selected else C("ink")
        weight = 700 if selected else 600
        name.setStyleSheet(
            f"color:{col};font-size:12px;font-weight:{weight};background:transparent;border:none;"
        )
        check = QLabel("✓" if selected else "")
        check.setStyleSheet(
            f"color:{C('accent')};font-size:12px;font-weight:800;background:transparent;border:none;"
        )
        h.addWidget(name)
        h.addStretch()
        h.addWidget(check)


class _LangPopup(QFrame):
    """Frameless popup listing the languages; closes on outside click."""

    chosen = pyqtSignal(str)

    def __init__(self, langs, current: str, min_width: int, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        wrap = QVBoxLayout(self)
        wrap.setContentsMargins(8, 8, 8, 8)   # room for the shadow

        card = QFrame()
        card.setObjectName("langcard")
        card.setMinimumWidth(min_width)
        card.setStyleSheet(
            f"#langcard{{background:{C('surface')};border:1px solid {C('line')};border-radius:10px;}}"
        )
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 80 if not _is_light() else 45))
        card.setGraphicsEffect(shadow)

        v = QVBoxLayout(card)
        v.setContentsMargins(5, 5, 5, 5)
        v.setSpacing(2)
        for code, label in langs:
            row = _LangRow(code, label, selected=(code == current))
            row.clicked.connect(lambda c=code: self._pick(c))
            v.addWidget(row)

        wrap.addWidget(card)

    def _pick(self, code: str) -> None:
        self.chosen.emit(code)
        self.close()


def _is_light() -> bool:
    from ui.theme import THEME
    return not THEME.is_dark


class LanguageToggle(QWidget):
    language_changed = pyqtSignal(str)

    def __init__(self, current: str = "ro", parent=None):
        super().__init__(parent)
        self._langs = get_languages()
        self._code = current if current in dict(self._langs) else "ro"
        self._popup = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        lbl = QLabel("Lang:")
        lbl.setStyleSheet(
            f"color:{C('ink4')};font-size:10px;font-weight:700;background:transparent;"
        )
        layout.addWidget(lbl)

        # custom "combo" field
        self._field = _ClickFrame()
        self._field.setObjectName("langfield")
        self._field.setCursor(Qt.CursorShape.PointingHandCursor)
        self._field.setStyleSheet(
            f"#langfield{{background:{C('surface')};border:1px solid {C('line')};"
            "border-radius:8px;}"
            f"#langfield:hover{{border-color:{C('accent')};}}"
        )
        self._field.setMinimumWidth(112)
        fl = QHBoxLayout(self._field)
        fl.setContentsMargins(9, 3, 8, 3)
        fl.setSpacing(6)
        self._field_lbl = QLabel(self._label_for(self._code))
        self._field_lbl.setStyleSheet(
            f"color:{C('ink')};font-size:11px;font-weight:600;background:transparent;border:none;"
        )
        chevron = QLabel("▾")
        chevron.setStyleSheet(
            f"color:{C('ink3')};font-size:11px;background:transparent;border:none;"
        )
        fl.addWidget(self._field_lbl)
        fl.addStretch()
        fl.addWidget(chevron)
        self._field.clicked.connect(self._open_popup)
        layout.addWidget(self._field)

    # ------------------------------------------------------------------

    def _label_for(self, code: str) -> str:
        return dict(self._langs).get(code, code)

    def _open_popup(self) -> None:
        popup = _LangPopup(self._langs, self._code, self._field.width() + 16, self)
        popup.chosen.connect(lambda code: self._select(code, emit=True))
        popup.adjustSize()
        ph = popup.sizeHint().height()

        below = self._field.mapToGlobal(self._field.rect().bottomLeft())
        above = self._field.mapToGlobal(self._field.rect().topLeft())
        screen = QGuiApplication.screenAt(below) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()

        x = below.x() - 8
        y = below.y() - 4
        if y + ph > avail.bottom():        # not enough room below -> open upward
            y = above.y() - ph + 8
        popup.move(x, y)
        self._popup = popup
        popup.show()

    def _select(self, lang: str, emit: bool = True) -> None:
        if lang not in dict(self._langs):
            return
        changed = lang != self._code
        self._code = lang
        self._field_lbl.setText(self._label_for(lang))
        if emit and changed:
            self.language_changed.emit(lang)

    def current(self) -> str:
        return self._code
