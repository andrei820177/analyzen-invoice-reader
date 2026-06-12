"""Themed message boxes and file dialogs.

Qt's native file dialogs follow the OS theme, not the app, and a plain
QMessageBox looks like a default system dialog. These helpers build Qt
(non-native) dialogs styled from the current theme tokens so every popup
matches the app in both light and dark mode. Build the stylesheet fresh on
each call so it always reflects the live theme.
"""

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ui.theme import C


def _qss() -> str:
    return f"""
    QDialog, QMessageBox, QFileDialog {{ background:{C('surface')}; }}
    QMessageBox QLabel, QFileDialog QLabel {{ color:{C('ink')}; background:transparent; }}

    QMessageBox QPushButton, QFileDialog QPushButton {{
        background:{C('surface2')}; color:{C('ink')};
        border:1px solid {C('line')}; border-radius:7px;
        padding:5px 14px; min-width:74px; font-size:12px; font-weight:600;
    }}
    QMessageBox QPushButton:hover, QFileDialog QPushButton:hover {{
        background:{C('surface3')}; }}
    QMessageBox QPushButton:default, QFileDialog QPushButton:default {{
        background:{C('accent')}; color:{C('on_accent')}; border:none; }}
    QMessageBox QPushButton:default:hover, QFileDialog QPushButton:default:hover {{
        background:{C('accent_press')}; }}

    QFileDialog QToolButton {{
        background:transparent; border:none; border-radius:6px;
        padding:4px; color:{C('ink2')}; }}
    QFileDialog QToolButton:hover {{ background:{C('surface3')}; }}
    QFileDialog QLineEdit, QFileDialog QComboBox {{
        background:{C('surface')}; color:{C('ink')};
        border:1px solid {C('line')}; border-radius:7px;
        padding:4px 8px; min-height:24px; }}
    QFileDialog QComboBox::drop-down {{ border:none; width:20px; }}
    QFileDialog QComboBox QAbstractItemView {{
        background:{C('surface')}; color:{C('ink')};
        border:1px solid {C('line')};
        selection-background-color:{C('sel')};
        selection-color:{C('accent_ink')}; }}
    QFileDialog QListView, QFileDialog QTreeView {{
        background:{C('surface')}; color:{C('ink')};
        border:1px solid {C('line')}; border-radius:7px; outline:none;
        selection-background-color:{C('sel')};
        selection-color:{C('accent_ink')}; }}
    QFileDialog QListView::item:hover, QFileDialog QTreeView::item:hover {{
        background:{C('surface3')}; }}
    QFileDialog QHeaderView::section {{
        background:{C('surface2')}; color:{C('ink3')};
        border:none; border-bottom:1px solid {C('line')}; padding:4px; }}
    QFileDialog QScrollBar:vertical {{
        background:transparent; width:10px; margin:0; }}
    QFileDialog QScrollBar::handle:vertical {{
        background:{C('scroll')}; border-radius:5px; min-height:24px; }}
    QFileDialog QScrollBar::handle:vertical:hover {{ background:{C('scroll_hover')}; }}
    QFileDialog QScrollBar::add-line, QFileDialog QScrollBar::sub-line {{ height:0; }}
    """


# --------------------------------------------------------------------------
# Message boxes
# --------------------------------------------------------------------------

def _box(parent, icon, text: str, title: str) -> QMessageBox:
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStyleSheet(_qss())
    return box


def info(parent, text: str, title: str = "") -> None:
    box = _box(parent, QMessageBox.Icon.Information, text, title)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def warn(parent, text: str, title: str = "") -> None:
    box = _box(parent, QMessageBox.Icon.Warning, text, title)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def error(parent, text: str, title: str = "") -> None:
    box = _box(parent, QMessageBox.Icon.Critical, text, title)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def question(parent, text: str, title: str = "") -> bool:
    """Yes/No question. Returns True on Yes."""
    box = _box(parent, QMessageBox.Icon.Question, text, title)
    box.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    box.setDefaultButton(QMessageBox.StandardButton.No)
    return box.exec() == QMessageBox.StandardButton.Yes


def themed_box(parent, text: str, title: str = "",
               icon=QMessageBox.Icon.Question) -> QMessageBox:
    """A pre-styled QMessageBox for callers that add custom buttons."""
    return _box(parent, icon, text, title)


# --------------------------------------------------------------------------
# File dialogs (forced non-native so they follow the theme)
# --------------------------------------------------------------------------

def _dialog(parent, caption: str) -> QFileDialog:
    dlg = QFileDialog(parent, caption)
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dlg.setStyleSheet(_qss())
    return dlg


def get_open_files(parent, caption: str, name_filter: str) -> list:
    dlg = _dialog(parent, caption)
    dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
    dlg.setNameFilter(name_filter)
    if dlg.exec():
        return dlg.selectedFiles()
    return []


def get_open_file(parent, caption: str, name_filter: str) -> str:
    dlg = _dialog(parent, caption)
    dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
    dlg.setNameFilter(name_filter)
    if dlg.exec():
        files = dlg.selectedFiles()
        return files[0] if files else ""
    return ""


def get_save_file(parent, caption: str, initial: str, name_filter: str) -> str:
    import os
    dlg = _dialog(parent, caption)
    dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dlg.setFileMode(QFileDialog.FileMode.AnyFile)
    dlg.setNameFilter(name_filter)
    suffix = os.path.splitext(initial)[1].lstrip(".")
    if suffix:
        dlg.setDefaultSuffix(suffix)      # keep the extension like the native dialog
    if initial:
        dlg.selectFile(initial)
    if dlg.exec():
        files = dlg.selectedFiles()
        return files[0] if files else ""
    return ""


def get_existing_dir(parent, caption: str) -> str:
    dlg = _dialog(parent, caption)
    dlg.setFileMode(QFileDialog.FileMode.Directory)
    dlg.setOption(QFileDialog.Option.ShowDirsOnly, True)
    if dlg.exec():
        files = dlg.selectedFiles()
        return files[0] if files else ""
    return ""
