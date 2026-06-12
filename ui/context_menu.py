"""Themed, localized right-click menu for text inputs.

A single application-wide event filter replaces the plain Qt context menu on
every QLineEdit (including the line edits inside spin boxes and editable combo
boxes) with one styled from the current theme and translated via L(). Widgets
that opt out with a custom context-menu policy are left untouched.
"""

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QApplication, QLineEdit, QMenu

from ui.lang import L
from ui.theme import C


def _menu_qss() -> str:
    return (
        f"QMenu{{background:{C('surface')};border:1px solid {C('line')};"
        "border-radius:8px;padding:5px;}"
        f"QMenu::item{{color:{C('ink')};padding:6px 16px;border-radius:6px;"
        "margin:1px 2px;}"
        f"QMenu::item:selected{{background:{C('surface3')};color:{C('ink')};}}"
        f"QMenu::item:disabled{{color:{C('ink4')};}}"
        f"QMenu::separator{{height:1px;background:{C('line')};margin:4px 6px;}}"
    )


def _build_menu(le: QLineEdit) -> QMenu:
    menu = QMenu(le)
    menu.setStyleSheet(_menu_qss())

    ro = le.isReadOnly()
    sel = le.hasSelectedText()
    has_text = bool(le.text())
    can_paste = bool(QApplication.clipboard().text())

    def add(label_key, slot, enabled):
        act = menu.addAction(L().t(label_key))
        act.setEnabled(enabled)
        act.triggered.connect(slot)
        return act

    add("ctx_undo", le.undo, not ro and le.isUndoAvailable())
    add("ctx_redo", le.redo, not ro and le.isRedoAvailable())
    menu.addSeparator()
    add("ctx_cut", le.cut, not ro and sel)
    add("ctx_copy", le.copy, sel)
    add("ctx_paste", le.paste, not ro and can_paste)
    add("ctx_delete", le.del_, not ro and sel)
    menu.addSeparator()
    add("ctx_select_all", le.selectAll, has_text)
    return menu


class _InputContextMenuFilter(QObject):
    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.ContextMenu
                and isinstance(obj, QLineEdit)
                and obj.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu):
            menu = _build_menu(obj)
            menu.exec(event.globalPos())
            return True
        return False


def install(parent: QObject) -> None:
    """Install the themed input context menu app-wide. The filter is parented to
    `parent` so it lives as long as the app does."""
    app = QApplication.instance()
    if app is None:
        return
    if getattr(app, "_input_ctx_filter", None) is not None:
        return
    flt = _InputContextMenuFilter(parent)
    app._input_ctx_filter = flt
    app.installEventFilter(flt)
