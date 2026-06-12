from __future__ import annotations

import json
import os
import time
from typing import List

from PyQt6.QtCore import QObject, QPoint, QThread, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMenu, QMessageBox, QPushButton, QSizePolicy, QStackedWidget,
    QVBoxLayout, QWidget,
)

from core.currency import configure as configure_currency
from core.extractor import extract_batch
from core.watcher import FolderWatcher
from data.models import Invoice
from data.processor import InvoiceDataFrame
from data.validator import validate_batch
from export.excel_exporter import export_excel
from export.pdf_reporter import export_pdf
from ui.components.progress_bar import ProcessingProgressBar
from ui.components.sidebar import Sidebar
from ui.dashboard import DashboardPage
from ui.lang import L, init_lang
from ui.log_panel import LogPanel
from ui.settings_dialog import SettingsDialog
from ui.table_view import InvoiceTableView
from ui.theme import C, THEME, apply_palette, reload_all

_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")


def _load_settings() -> dict:
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class InvoiceWorker(QObject):
    invoice_processed = pyqtSignal(object)
    progress          = pyqtSignal(int, int)
    log_message       = pyqtSignal(str, str)
    finished          = pyqtSignal(float)

    def __init__(self, file_paths: List[str], max_workers: int = 0):
        super().__init__()
        self._paths = file_paths
        self._max_workers = max_workers

    @pyqtSlot()
    def run(self) -> None:
        t0 = time.perf_counter()

        def _cb(current: int, total: int, inv: Invoice) -> None:
            self.progress.emit(current, total)
            level = "success" if not inv.parse_errors else "warning"
            msg = f"[{current}/{total}] {inv.file_name}"
            if inv.is_scanned:
                msg += " (OCR)"
            if inv.parse_errors:
                msg += f" — {inv.parse_errors[0]}"
            self.log_message.emit(msg, level)
            self.invoice_processed.emit(inv)

        self.log_message.emit(
            L().t("log_processing", f"{len(self._paths)} {L().t('nav_invoices').lower()}"),
            "info",
        )
        extract_batch(self._paths, progress_callback=_cb, max_workers=self._max_workers)
        self.finished.emit(time.perf_counter() - t0)


# ---------------------------------------------------------------------------
# Drop Zone
# ---------------------------------------------------------------------------

class DropZone(QWidget):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._card = QFrame()
        self._card.setFixedSize(360, 290)
        self._card.setStyleSheet(
            f"QFrame {{ background: {C('surface')}; border-radius: 11px; border: 2px dashed {C('accent')}; }}"
        )
        card_layout = QVBoxLayout(self._card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(10)

        arrow = QLabel("↓")
        arrow.setStyleSheet(f"color: {C('accent')}; font-size: 44px; font-weight: bold; border: none;")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title = QLabel(L().t("drop_zone_title"))
        self._title.setStyleSheet(f"color: {C('ink')}; font-size: 15px; font-weight: 700; border: none;")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setWordWrap(True)

        self._subtitle = QLabel(L().t("drop_zone_subtitle"))
        self._subtitle.setStyleSheet(f"color: {C('ink3')}; font-size: 12px; border: none;")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._btn = QPushButton(L().t("btn_open_files"))
        self._btn.setFixedSize(210, 40)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(
            f"QPushButton {{ background: {C('accent')}; color: {C('on_accent')}; border-radius: 8px;"
            " border: none; font-size: 13px; font-weight: 600; }"
            f"QPushButton:hover {{ background: {C('accent_press')}; }}"
        )
        self._btn.clicked.connect(self._open_file_dialog)

        card_layout.addWidget(arrow)
        card_layout.addWidget(self._title)
        card_layout.addWidget(self._subtitle)
        card_layout.addSpacing(6)
        card_layout.addWidget(self._btn, 0, Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(self._card)

    def retranslate(self) -> None:
        self._title.setText(L().t("drop_zone_title"))
        self._subtitle.setText(L().t("drop_zone_subtitle"))
        self._btn.setText(L().t("btn_open_files"))

    def _open_file_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, L().t("btn_open_files"), "", "PDF Files (*.pdf)"
        )
        if paths:
            self.files_dropped.emit(paths)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [
            u.toLocalFile() for u in event.mimeData().urls()
            if u.toLocalFile().lower().endswith(".pdf")
        ]
        if paths:
            self.files_dropped.emit(paths)


# ---------------------------------------------------------------------------
# Export page
# ---------------------------------------------------------------------------

class ExportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._idf: InvoiceDataFrame | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._title_lbl = QLabel(L().t("nav_export"))
        self._title_lbl.setStyleSheet(f"color: {C('ink')}; font-size: 18px; font-weight: 700;")
        layout.addWidget(self._title_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {C('line')}; max-height: 1px;")
        layout.addWidget(sep)
        layout.addSpacing(8)

        self._btn_excel = self._make_btn("#2f8f6b", self._export_excel)
        self._btn_pdf   = self._make_btn("#3498db", self._export_pdf_rep)
        self._btn_email = self._make_btn("#9b59b6", self._export_email)

        layout.addWidget(self._btn_excel)
        layout.addWidget(self._btn_pdf)
        layout.addWidget(self._btn_email)
        layout.addStretch()

        self.retranslate()

    def _make_btn(self, color: str, slot) -> QPushButton:
        btn = QPushButton()
        btn.setFixedHeight(48)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background: {color}; color: white; border-radius: 8px;"
            " border: none; font-size: 14px; font-weight: 600;"
            " text-align: left; padding-left: 20px; }}"
            f"QPushButton:hover {{ background: {color}cc; }}"
        )
        btn.clicked.connect(slot)
        return btn

    def retranslate(self) -> None:
        self._title_lbl.setText(L().t("nav_export"))
        self._btn_excel.setText(L().t("export_excel"))
        self._btn_pdf.setText(L().t("export_pdf"))
        self._btn_email.setText(L().t("export_email"))

    def set_idf(self, idf: InvoiceDataFrame) -> None:
        self._idf = idf

    def _export_excel(self) -> None:
        if not self._idf or len(self._idf) == 0:
            QMessageBox.information(self, "Export", L().t("no_invoices"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, L().t("export_excel"), "facturi_export.xlsx", "Excel (*.xlsx)"
        )
        if path:
            try:
                export_excel(self._idf, path)
                QMessageBox.information(self, "Export", f"{L().t('done')}: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _export_pdf_rep(self) -> None:
        if not self._idf or len(self._idf) == 0:
            QMessageBox.information(self, "Export", L().t("no_invoices"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, L().t("export_pdf"), "raport_facturi.pdf", "PDF (*.pdf)"
        )
        if path:
            try:
                export_pdf(self._idf, path)
                QMessageBox.information(self, "Export", f"{L().t('done')}: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _export_email(self) -> None:
        QMessageBox.information(self, "Email", L().t("settings_email"))


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

_PAGE_TITLE_KEYS = {
    "dashboard": "nav_dashboard",
    "invoices":  "nav_invoices",
    "export":    "nav_export",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        init_lang()

        self.setWindowTitle(L().t("app_title"))
        # generous lower bound so the app stays usable on smaller resolutions
        self.setMinimumSize(880, 560)
        self.resize(1280, 800)
        self._apply_window_style()

        self._idf = InvoiceDataFrame()
        self._watcher = FolderWatcher()
        self._worker_thread: QThread | None = None
        self._current_page = "dashboard"
        self._collected_invoices: List[Invoice] = []

        settings = _load_settings()
        configure_currency(
            settings.get("fx_source", "BNR"),
            settings.get("base_currency", "RON"),
        )

        self._build_ui()
        self._dashboard.set_base_currency(settings.get("base_currency", "RON"))
        self._connect_signals()

        # Ctrl+L toggles the log (created once, survives theme rebuilds)
        shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        shortcut.activated.connect(self._toggle_log)

        self._check_auto_watch()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _apply_window_style(self) -> None:
        self.setStyleSheet(f"""
            QMainWindow {{ background: {C('desk')}; }}
            QWidget {{ font-family: 'Segoe UI', system-ui, sans-serif; font-size: 13px; color: {C('ink')}; }}

            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px 2px 2px 0; }}
            QScrollBar::handle:vertical {{ background: {C('scroll')}; border-radius: 4px; min-height: 30px; }}
            QScrollBar::handle:vertical:hover {{ background: {C('scroll_hover')}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

            QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0 2px 2px 2px; }}
            QScrollBar::handle:horizontal {{ background: {C('scroll')}; border-radius: 4px; min-width: 30px; }}
            QScrollBar::handle:horizontal:hover {{ background: {C('scroll_hover')}; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
        """)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._sidebar = Sidebar()
        main_layout.addWidget(self._sidebar)

        content_frame = QWidget()
        content_frame.setStyleSheet(f"background: {C('desk')};")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Header
        self._header = QWidget()
        self._header.setFixedHeight(56)
        self._header.setStyleSheet(
            f"background: {C('header')}; border-bottom: 1px solid {C('line')};"
        )
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(24, 0, 16, 0)
        hl.setSpacing(8)

        self._page_title = QLabel(L().t("nav_dashboard"))
        self._page_title.setStyleSheet(f"color: {C('ink')}; font-size: 15px; font-weight: 700;")
        hl.addWidget(self._page_title)
        hl.addStretch()

        self._btn_open_files  = self._make_header_btn("btn_open_files",  primary=True)
        self._btn_open_folder = self._make_header_btn("btn_open_folder", primary=False)
        self._btn_watch       = self._make_header_btn("btn_watch",       primary=False)
        self._btn_clear       = self._make_header_btn("btn_clear",       primary=False)

        # "Open folder" + a small caret that drops down the recent-folders menu
        self._btn_recent = self._make_caret_btn()
        folder_group = QWidget()
        fg = QHBoxLayout(folder_group)
        fg.setContentsMargins(0, 0, 0, 0)
        fg.setSpacing(2)
        fg.addWidget(self._btn_open_folder)
        fg.addWidget(self._btn_recent)

        hl.addWidget(self._btn_open_files)
        hl.addWidget(folder_group)
        hl.addWidget(self._btn_watch)
        hl.addWidget(self._btn_clear)

        content_layout.addWidget(self._header)

        # Progress strip
        self._progress_strip = QWidget()
        self._progress_strip.setFixedHeight(16)
        self._progress_strip.setStyleSheet(f"background: {C('header')}; border-bottom: 1px solid {C('line')};")
        ps_layout = QHBoxLayout(self._progress_strip)
        ps_layout.setContentsMargins(24, 4, 24, 4)
        self._progress_bar = ProcessingProgressBar()
        ps_layout.addWidget(self._progress_bar)
        self._progress_strip.setVisible(False)
        content_layout.addWidget(self._progress_strip)

        # Stacked pages
        self._stack = QStackedWidget()
        self._drop_zone   = DropZone()
        self._dashboard   = DashboardPage()
        self._table_view  = InvoiceTableView()
        self._export_page = ExportPage()
        self._stack.addWidget(self._drop_zone)    # 0
        self._stack.addWidget(self._dashboard)    # 1
        self._stack.addWidget(self._table_view)   # 2
        self._stack.addWidget(self._export_page)  # 3
        content_layout.addWidget(self._stack, 1)

        # Log panel — visibility controlled from Settings > Debugging (or Ctrl+L)
        self._log = LogPanel()
        self._log.setVisible(_load_settings().get("show_log", False))
        content_layout.addWidget(self._log)

        main_layout.addWidget(content_frame, 1)

    def _make_header_btn(self, key: str, primary: bool) -> QPushButton:
        btn = QPushButton(L().t(key))
        btn.setProperty("lang_key", key)
        btn.setFixedHeight(32)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if primary:
            btn.setStyleSheet(
                f"QPushButton {{ background: {C('accent')}; color: {C('on_accent')}; border-radius: 8px;"
                " border: none; font-size: 12px; font-weight: 600; padding: 0 14px; }"
                f"QPushButton:hover {{ background: {C('accent_press')}; }}"
                f"QPushButton:disabled {{ background: {C('accent_soft')}; color: {C('ink4')}; }}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton {{ background: {C('surface')}; color: {C('ink')}; border-radius: 8px;"
                f" border: 1px solid {C('line')}; font-size: 12px; font-weight: 600; padding: 0 14px; }}"
                f"QPushButton:hover {{ background: {C('surface3')}; }}"
                f"QPushButton:disabled {{ color: {C('ink4')}; }}"
            )
        return btn

    def _make_caret_btn(self) -> QPushButton:
        btn = QPushButton("▾")
        btn.setFixedHeight(32)
        btn.setFixedWidth(26)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(L().t("recent_folders"))
        btn.setStyleSheet(
            f"QPushButton {{ background: {C('surface')}; color: {C('ink3')}; border-radius: 8px;"
            f" border: 1px solid {C('line')}; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {C('surface3')}; color: {C('accent')}; }}"
            f"QPushButton:disabled {{ color: {C('ink4')}; }}"
        )
        return btn

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._sidebar.page_changed.connect(self._on_page_changed)
        self._sidebar.language_changed.connect(self._on_language_changed)
        self._sidebar.settings_requested.connect(self._open_settings)

        self._btn_open_files.clicked.connect(self._open_files)
        self._btn_open_folder.clicked.connect(self._open_folder)
        self._btn_recent.clicked.connect(self._show_recent_menu)
        self._btn_watch.clicked.connect(self._toggle_watch)
        self._btn_clear.clicked.connect(self._clear_data)

        self._drop_zone.files_dropped.connect(self._process_files)
        self._table_view.invoice_updated.connect(self._on_invoice_updated)
        self._export_page.set_idf(self._idf)

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------

    def _on_language_changed(self, lang: str) -> None:
        L().load(lang)
        try:
            with open(_SETTINGS_PATH, encoding="utf-8") as f:
                s = json.load(f)
            s["language"] = lang
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=2)
        except Exception:
            pass
        self._retranslate_all()

    def _retranslate_all(self) -> None:
        self.setWindowTitle(L().t("app_title"))
        self._page_title.setText(L().t(_PAGE_TITLE_KEYS.get(self._current_page, "nav_dashboard")))

        for btn in (self._btn_open_files, self._btn_open_folder,
                    self._btn_watch, self._btn_clear):
            key = btn.property("lang_key")
            if key:
                btn.setText(L().t(key))

        if self._watcher.is_running:
            self._btn_watch.setText(L().t("btn_stop_watch"))
        self._btn_recent.setToolTip(L().t("recent_folders"))

        self._sidebar.retranslate()
        self._drop_zone.retranslate()
        self._dashboard.retranslate()
        self._table_view.retranslate()
        self._table_view.retranslate_drawer()
        self._export_page.retranslate()
        self._log.retranslate()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_page_changed(self, key: str) -> None:
        self._current_page = key
        self._page_title.setText(L().t(_PAGE_TITLE_KEYS.get(key, key)))

        if len(self._idf) == 0:
            self._stack.setCurrentIndex(0)
            return

        self._stack.setCurrentIndex({"dashboard": 1, "invoices": 2, "export": 3}.get(key, 1))

    # ------------------------------------------------------------------
    # Log toggle
    # ------------------------------------------------------------------

    def _toggle_log(self) -> None:
        self._log.setVisible(not self._log.isVisible())

    # ------------------------------------------------------------------
    # File processing
    # ------------------------------------------------------------------

    def _open_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, L().t("btn_open_files"), "", "PDF Files (*.pdf)"
        )
        if paths:
            self._process_files(paths)

    def _open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, L().t("btn_open_folder"))
        if folder:
            self._process_folder(folder)

    def _process_folder(self, folder: str) -> None:
        if not os.path.isdir(folder):
            QMessageBox.information(self, "Info", L().t("folder_missing"))
            self._remove_recent(folder)
            return
        paths = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(".pdf")
        ]
        if paths:
            self._add_recent(folder)
            self._process_files(paths)
        else:
            QMessageBox.information(self, "Info", L().t("no_invoices"))

    # ------------------------------------------------------------------
    # Recent folders (history for "Open folder")
    # ------------------------------------------------------------------

    def _recent_folders(self) -> list:
        recents = _load_settings().get("recent_folders", [])
        return [p for p in recents if isinstance(p, str)]

    def _save_recent(self, recents: list) -> None:
        try:
            with open(_SETTINGS_PATH, encoding="utf-8") as f:
                s = json.load(f)
        except Exception:
            s = {}
        s["recent_folders"] = recents
        try:
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _add_recent(self, folder: str) -> None:
        folder = os.path.normpath(folder)
        recents = [p for p in self._recent_folders()
                   if os.path.normpath(p).lower() != folder.lower()]
        recents.insert(0, folder)
        self._save_recent(recents[:8])

    def _remove_recent(self, folder: str) -> None:
        target = os.path.normpath(folder).lower()
        self._save_recent([p for p in self._recent_folders()
                            if os.path.normpath(p).lower() != target])

    def _clear_recent(self) -> None:
        self._save_recent([])

    def _show_recent_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{C('surface')};border:1px solid {C('line')};"
            "border-radius:8px;padding:5px;}"
            f"QMenu::item{{color:{C('ink')};padding:6px 12px;border-radius:6px;}}"
            f"QMenu::item:selected{{background:{C('surface3')};color:{C('ink')};}}"
            f"QMenu::item:disabled{{color:{C('ink4')};}}"
            f"QMenu::separator{{height:1px;background:{C('line')};margin:4px 6px;}}"
        )
        recents = self._recent_folders()
        if not recents:
            act = menu.addAction(L().t("recent_empty"))
            act.setEnabled(False)
        else:
            for path in recents:
                act = menu.addAction(self._short_path(path))
                act.setToolTip(path)
                act.triggered.connect(lambda _checked, p=path: self._process_folder(p))
            menu.addSeparator()
            clear = menu.addAction(L().t("recent_clear"))
            clear.triggered.connect(self._clear_recent)
        menu.exec(self._btn_recent.mapToGlobal(QPoint(0, self._btn_recent.height() + 2)))

    @staticmethod
    def _short_path(path: str, max_len: int = 48) -> str:
        name = os.path.basename(path.rstrip("/\\")) or path
        parent = os.path.basename(os.path.dirname(path.rstrip("/\\")))
        label = f"{parent}/{name}" if parent else name
        if len(path) <= max_len:
            return path
        return "..." + os.sep + label

    def _toggle_watch(self) -> None:
        if self._watcher.is_running:
            self._watcher.stop()
            self._btn_watch.setText(L().t("btn_watch"))
            self._log.append(L().t("btn_stop_watch"), "warning")
        else:
            settings = _load_settings()
            folder = settings.get("watch_folder", "").strip()
            if not folder:
                folder = QFileDialog.getExistingDirectory(self, L().t("btn_watch"))
            if folder:
                self._watcher.start(folder, self._on_new_pdf_detected)
                self._btn_watch.setText(L().t("btn_stop_watch"))
                self._log.append(f"{L().t('btn_watch')}: {folder}", "success")

    def _on_new_pdf_detected(self, path: str) -> None:
        from PyQt6.QtCore import QMetaObject, Q_ARG
        QMetaObject.invokeMethod(
            self, "_process_files_slot",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(object, [path]),
        )

    @pyqtSlot(object)
    def _process_files_slot(self, paths) -> None:
        self._process_files(paths)

    def _process_files(self, paths: List[str]) -> None:
        if self._worker_thread and self._worker_thread.isRunning():
            QMessageBox.warning(self, "Info", L().t("processing"))
            return

        settings = _load_settings()
        self._progress_strip.setVisible(True)
        self._progress_bar.reset()
        self._btn_open_files.setEnabled(False)
        self._btn_open_folder.setEnabled(False)
        self._btn_recent.setEnabled(False)
        self._collected_invoices = []

        self._worker = InvoiceWorker(paths, max_workers=settings.get("max_workers", 0))
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.log_message.connect(self._log.append)
        self._worker.invoice_processed.connect(self._collected_invoices.append)
        self._worker.finished.connect(self._on_processing_done)
        self._worker_thread.start()

    @pyqtSlot(int, int)
    def _on_progress(self, current: int, total: int) -> None:
        self._progress_bar.set_progress(current, total)

    @pyqtSlot(float)
    def _on_processing_done(self, elapsed: float) -> None:
        invoices = self._collected_invoices
        validate_batch(invoices)
        self._idf.add_invoices(invoices)

        self._worker_thread.quit()
        self._worker_thread.wait()
        self._worker_thread = None
        self._progress_strip.setVisible(False)
        self._btn_open_files.setEnabled(True)
        self._btn_open_folder.setEnabled(True)
        self._btn_recent.setEnabled(True)

        count = len(invoices)
        self._log.append(L().t("log_done", count, elapsed), "success")

        flagged = sum(
            1 for inv in invoices if inv.is_duplicate or inv.is_outlier or inv.is_near_due
        )
        if flagged:
            self._log.append(f"{flagged} {L().t('kpi_flagged').lower()}!", "warning")

        self._refresh_views()
        self._sidebar.set_active("dashboard")

    def _refresh_views(self) -> None:
        summary = self._idf.get_summary()
        self._dashboard.update_summary(summary)
        self._table_view.load_data(self._idf.get_all())
        self._export_page.set_idf(self._idf)
        self._update_sidebar()
        if len(self._idf) > 0:
            self._on_page_changed("dashboard")

    def _update_sidebar(self) -> None:
        stats = self._idf.get_sidebar_stats()
        self._sidebar.set_counts({"invoices": stats["count"]})
        # full-precision amounts, one currency per row in the card
        chips = [
            (code, f"{amt:,.2f}")
            for code, amt in sorted(
                stats["per_currency"].items(), key=lambda kv: kv[1], reverse=True
            )
        ]
        total_text = f"{stats['total_base']:,.2f} {stats['base']}"
        s = stats["status"]
        self._sidebar.set_summary(
            total_text, chips, (s["valid"], s["warning"], s["error"])
        )

    @pyqtSlot(dict)
    def _on_invoice_updated(self, fields: dict) -> None:
        path = fields.pop("file_path", "")
        if not path:
            return
        self._idf.update_invoice(path, fields)
        # refresh data without leaving the invoices page
        self._dashboard.update_summary(self._idf.get_summary())
        self._table_view.load_data(self._idf.get_all())
        self._update_sidebar()
        self._log.append(f"{path.split(chr(92))[-1].split('/')[-1]}: {L().t('done')}", "success")

    def _clear_data(self) -> None:
        if len(self._idf) == 0:
            return
        reply = QMessageBox.question(
            self, L().t("btn_clear"), L().t("confirm_clear"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._idf.clear()
            self._table_view.clear()
            self._dashboard.update_summary(self._idf.get_summary())
            self._update_sidebar()
            self._stack.setCurrentIndex(0)
            self._log.append(L().t("btn_clear"), "warning")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        old_theme = _load_settings().get("theme", "light")
        dlg = SettingsDialog(self)
        if dlg.exec():
            settings = _load_settings()
            new_theme = settings.get("theme", "light")
            if new_theme != old_theme:
                # defer to the next loop tick so the current signal finishes
                # before the central widget (incl. the sidebar) is rebuilt
                QTimer.singleShot(0, lambda m=new_theme: self._apply_theme(m))
            new_lang = settings.get("language", "ro")
            if new_lang != L().code:
                L().load(new_lang)
                self._sidebar.set_language(new_lang)
                self._retranslate_all()

            configure_currency(
                settings.get("fx_source", "BNR"),
                settings.get("base_currency", "RON"),
            )
            self._dashboard.set_base_currency(settings.get("base_currency", "RON"))
            self._dashboard.refresh_fx()
            self._log.setVisible(settings.get("show_log", False))
            if len(self._idf) > 0:
                self._refresh_views()

    def _apply_theme(self, mode: str) -> None:
        """Switch theme live: rebuild the UI from refreshed tokens, keep data."""
        if self._worker_thread and self._worker_thread.isRunning():
            QMessageBox.information(self, L().t("app_title"), L().t("theme_restart"))
            return
        THEME.set_mode(mode)
        reload_all()                       # refresh module-level colour caches
        apply_palette(QApplication.instance())

        page = self._current_page
        self._apply_window_style()         # window chrome, scrollbars, base text
        self._build_ui()                   # recreate the central widget tree
        settings = _load_settings()
        self._dashboard.set_base_currency(settings.get("base_currency", "RON"))
        self._connect_signals()
        if self._watcher.is_running:
            self._btn_watch.setText(L().t("btn_stop_watch"))
        if len(self._idf) > 0:
            self._refresh_views()
        self._sidebar.set_active(page)
        self._on_page_changed(page)

    def _check_auto_watch(self) -> None:
        settings = _load_settings()
        if settings.get("auto_watch") and settings.get("watch_folder"):
            self._watcher.start(settings["watch_folder"], self._on_new_pdf_detected)
            self._btn_watch.setText(L().t("btn_stop_watch"))
            self._log.append(f"Auto-watch: {settings['watch_folder']}", "info")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._watcher.stop()
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(2000)
        event.accept()
