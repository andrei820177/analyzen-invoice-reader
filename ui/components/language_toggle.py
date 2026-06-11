import time

from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)
from PyQt6.QtGui import QGuiApplication, QPainterPath, QRegion

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


_RADIUS = 10


class _LangPopup(QFrame):
    """Frameless popup listing the languages; closes on outside click.

    Uses a solid (non-translucent) background plus a rounded mask. A
    translucent top-level window with a drop-shadow renders its "transparent"
    areas as opaque white under the Windows compositor, which made the popup
    appear light over a dark app -- a solid background avoids that entirely.
    """

    chosen = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, langs, current: str, min_width: int, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("langpop")
        self.setMinimumWidth(min_width)
        self.setStyleSheet(
            f"#langpop{{background:{C('surface')};border:1px solid {C('line')};"
            f"border-radius:{_RADIUS}px;}}"
        )

        v = QVBoxLayout(self)
        v.setContentsMargins(5, 5, 5, 5)
        v.setSpacing(2)
        for code, label in langs:
            row = _LangRow(code, label, selected=(code == current))
            row.clicked.connect(lambda c=code: self._pick(c))
            v.addWidget(row)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # round the window corners without translucency
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), _RADIUS, _RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def hideEvent(self, event):
        super().hideEvent(event)
        self.closed.emit()

    def _pick(self, code: str) -> None:
        self.chosen.emit(code)
        self.close()


class LanguageToggle(QWidget):
    language_changed = pyqtSignal(str)

    def __init__(self, current: str = "ro", parent=None):
        super().__init__(parent)
        self._langs = get_languages()
        self._code = current if current in dict(self._langs) else "ro"
        self._popup = None
        self._popup_closed_at = 0.0

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
        # If the field click is the same one that just dismissed an open popup
        # (Qt.Popup closes on press, the field then gets the release), treat it
        # as a toggle and leave the popup closed instead of reopening it.
        if time.monotonic() - self._popup_closed_at < 0.25:
            return
        popup = _LangPopup(self._langs, self._code, self._field.width(), self)
        popup.chosen.connect(lambda code: self._select(code, emit=True))
        popup.closed.connect(self._on_popup_closed)
        popup.adjustSize()
        ph = popup.sizeHint().height()

        below = self._field.mapToGlobal(self._field.rect().bottomLeft())
        above = self._field.mapToGlobal(self._field.rect().topLeft())
        screen = QGuiApplication.screenAt(below) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()

        x = below.x()
        y = below.y() + 3
        if y + ph > avail.bottom():        # not enough room below -> open upward
            y = above.y() - ph - 3
        popup.move(x, y)
        self._popup = popup
        popup.show()

    def _on_popup_closed(self) -> None:
        self._popup_closed_at = time.monotonic()
        self._popup = None

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
