"""Themed message boxes + thin file-dialog wrappers.

A plain QMessageBox looks like a default system popup, so these helpers style
it from the current theme tokens (built fresh each call so it tracks the live
theme). File/folder pickers are intentionally left as the native Windows
dialogs -- the OS browser is more capable and familiar than a styled Qt one.
"""

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ui.theme import C


def _qss() -> str:
    return f"""
    QMessageBox {{ background:{C('surface')}; }}
    QMessageBox QLabel {{ color:{C('ink')}; background:transparent; }}
    QMessageBox QPushButton {{
        background:{C('surface2')}; color:{C('ink')};
        border:1px solid {C('line')}; border-radius:7px;
        padding:5px 14px; min-width:74px; font-size:12px; font-weight:600;
    }}
    QMessageBox QPushButton:hover {{ background:{C('surface3')}; }}
    QMessageBox QPushButton:default {{
        background:{C('accent')}; color:{C('on_accent')}; border:none; }}
    QMessageBox QPushButton:default:hover {{ background:{C('accent_press')}; }}
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


def accent_button_css() -> str:
    """Accent (primary) button style, e.g. for equivalent custom choices."""
    return (
        f"QPushButton{{background:{C('accent')};color:{C('on_accent')};border:none;"
        "border-radius:7px;padding:5px 14px;min-width:74px;font-size:12px;font-weight:600;}"
        f"QPushButton:hover{{background:{C('accent_press')};}}"
    )


# --------------------------------------------------------------------------
# File dialogs -- kept as the native Windows pickers (the OS file/folder
# browser is more capable and familiar than a styled Qt one).
# --------------------------------------------------------------------------

def get_open_files(parent, caption: str, name_filter: str) -> list:
    paths, _ = QFileDialog.getOpenFileNames(parent, caption, "", name_filter)
    return paths


def get_open_file(parent, caption: str, name_filter: str) -> str:
    path, _ = QFileDialog.getOpenFileName(parent, caption, "", name_filter)
    return path


def get_save_file(parent, caption: str, initial: str, name_filter: str) -> str:
    path, _ = QFileDialog.getSaveFileName(parent, caption, initial, name_filter)
    return path


def get_existing_dir(parent, caption: str) -> str:
    return QFileDialog.getExistingDirectory(parent, caption)
