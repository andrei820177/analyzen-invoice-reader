"""
Dialog shown when a required OCR language pack is missing.
Offers to download it automatically from tesseract-ocr/tessdata_fast.
"""

from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from core.ocr_lang_manager import download_for_lang, get_missing_packs


class _DownloadSignals(QObject):
    progress = pyqtSignal(str, int, int)   # pack, downloaded, total
    finished = pyqtSignal(int, int)        # success_count, total


class OcrLangDialog(QDialog):
    """Prompts the user to download missing Tesseract language packs."""

    def __init__(self, ui_lang: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._ui_lang = ui_lang
        self._missing = get_missing_packs(ui_lang)

        self.setWindowTitle("Pachete OCR lipsă")
        self.setMinimumWidth(420)
        self.setStyleSheet("QDialog{background:#f4f7f5;}")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        packs_str = ", ".join(self._missing)
        info = QLabel(
            f"Pentru OCR in limba selectată sunt necesare pachetele:\n"
            f"<b>{packs_str}</b>\n\n"
            f"Descarcă automat de pe GitHub (~5-10 MB fiecare)?"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#1a2332;font-size:13px;")
        info.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(info)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#6b8a7a;font-size:12px;")
        root.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setFixedHeight(8)
        self._bar.setStyleSheet("""
            QProgressBar{background:#e0e8e4;border-radius:4px;border:none;}
            QProgressBar::chunk{background:#2f8f6b;border-radius:4px;}
        """)
        self._bar.setVisible(False)
        root.addWidget(self._bar)

        self._buttons = QDialogButtonBox()
        self._dl_btn = self._buttons.addButton(
            "Descarcă", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._skip_btn = self._buttons.addButton(
            "Continuă fără OCR", QDialogButtonBox.ButtonRole.RejectRole
        )
        self._dl_btn.setStyleSheet(
            "QPushButton{background:#2f8f6b;color:white;border-radius:6px;"
            "border:none;padding:8px 18px;font-size:13px;}"
            "QPushButton:hover{background:#1e7558;}"
            "QPushButton:disabled{background:#a8cfc0;}"
        )
        self._skip_btn.setStyleSheet(
            "QPushButton{background:#e0e8e4;color:#1a2332;border-radius:6px;"
            "border:none;padding:8px 18px;font-size:13px;}"
        )
        self._buttons.accepted.connect(self._start_download)
        self._buttons.rejected.connect(self.reject)
        root.addWidget(self._buttons)

        self._signals = _DownloadSignals()
        self._signals.progress.connect(self._on_progress)
        self._signals.finished.connect(self._on_finished)

    def _start_download(self) -> None:
        self._dl_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._bar.setVisible(True)
        self._status.setText("Download în curs...")

        def _run() -> None:
            def _cb(pack: str, dl: int, total: int) -> None:
                self._signals.progress.emit(pack, dl, total)

            ok, total = download_for_lang(self._ui_lang, progress_callback=_cb)
            self._signals.finished.emit(ok, total)

        threading.Thread(target=_run, daemon=True).start()

    def _on_progress(self, pack: str, downloaded: int, total: int) -> None:
        self._status.setText(f"Descarcă: {pack}.traineddata …")
        if total > 0:
            self._bar.setValue(int(downloaded / total * 100))

    def _on_finished(self, ok: int, total: int) -> None:
        self._bar.setValue(100)
        if ok == total:
            self._status.setText(f"Descărcat cu succes ({ok}/{total} pachete).")
            self.accept()
        else:
            self._status.setText(
                f"Eroare: {total - ok} pachete nu au putut fi descărcate. "
                f"Verificați conexiunea la internet."
            )
            self._dl_btn.setEnabled(True)
            self._skip_btn.setEnabled(True)


def ensure_ocr_lang(ui_lang: str, parent: QWidget | None = None) -> bool:
    """Check language packs and prompt download if missing. Returns True if ready."""
    from core.ocr_lang_manager import is_lang_ready
    if is_lang_ready(ui_lang):
        return True
    dlg = OcrLangDialog(ui_lang, parent)
    result = dlg.exec()
    return result == QDialog.DialogCode.Accepted and is_lang_ready(ui_lang)
