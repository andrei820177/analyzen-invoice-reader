import json
import os

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QDoubleSpinBox, QTabWidget, QVBoxLayout, QWidget,
)
from core.currency import SOURCE_LABELS
from ui.components.widgets import NoScrollComboBox
from ui.lang import L
from ui.theme import C, register_reload

_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")

_CURRENCIES = ["RON", "EUR", "USD", "GBP", "CHF", "PLN", "CZK", "HUF",
               "SEK", "NOK", "DKK", "CAD", "JPY", "RUB"]
_FX_SOURCES  = list(SOURCE_LABELS.keys())


def _load() -> dict:
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _input_style() -> str:
    return (
    "QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox{"
    f"background:{C('surface')};border:1px solid {C('line')};border-radius:8px;"
    f"padding:4px 8px;font-size:13px;color:{C('ink')};min-height:28px;}}"
    "QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus,QComboBox:focus{"
    f"border-color:{C('accent')};}}"
    "QComboBox::drop-down{border:none;width:22px;}"
    # dropdown popup: explicit colors so items are never white-on-white
    "QComboBox QAbstractItemView{"
    f"background:{C('surface')};color:{C('ink')};border:1px solid {C('line')};"
    f"selection-background-color:{C('sel')};selection-color:{C('accent_ink')};}}"
    # flat, modern spin buttons (no 3D bevel); native Fusion arrows are kept
    "QSpinBox::up-button,QDoubleSpinBox::up-button{subcontrol-origin:border;"
    "subcontrol-position:top right;width:20px;border:none;"
    f"border-left:1px solid {C('line')};border-top-right-radius:8px;background:{C('surface2')};}}"
    "QSpinBox::down-button,QDoubleSpinBox::down-button{subcontrol-origin:border;"
    "subcontrol-position:bottom right;width:20px;border:none;"
    f"border-left:1px solid {C('line')};border-bottom-right-radius:8px;background:{C('surface2')};}}"
    "QSpinBox::up-button:hover,QDoubleSpinBox::up-button:hover,"
    f"QSpinBox::down-button:hover,QDoubleSpinBox::down-button:hover{{background:{C('accent_soft')};}}"
    )


_INPUT_STYLE = _input_style()


def _reload():
    global _INPUT_STYLE
    _INPUT_STYLE = _input_style()


register_reload(_reload)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(L().t("set_title"))
        self.setMinimumWidth(500)
        self.setStyleSheet(
            f"QDialog{{background:{C('desk')};}}"
            f"QLabel{{color:{C('ink')};background:transparent;}}"
            f"QCheckBox{{color:{C('ink')};background:transparent;}}"
        )

        self._settings = _load()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane{{background:{C('surface')};border:1px solid {C('line')};border-radius:8px;}}
            QTabBar::tab{{background:{C('sidebar')};color:{C('ink3')};padding:8px 16px;border:none;font-size:12px;}}
            QTabBar::tab:selected{{background:{C('surface')};color:{C('accent')};font-weight:bold;
              border-bottom:2px solid {C('accent')};}}
        """)

        tabs.addTab(self._build_general_tab(), L().t("tab_general"))
        tabs.addTab(self._build_currency_tab(), L().t("tab_currency"))
        tabs.addTab(self._build_ocr_tab(), L().t("tab_ocr"))
        tabs.addTab(self._build_email_tab(), L().t("tab_email"))
        tabs.addTab(self._build_advanced_tab(), L().t("tab_advanced"))
        tabs.addTab(self._build_debug_tab(), L().t("tab_debugging"))
        root.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setStyleSheet(f"""
            QPushButton{{background:{C('accent')};color:white;border:none;border-radius:8px;
              padding:8px 20px;font-size:13px;font-weight:600;}}
            QPushButton:hover{{background:{C('accent_press')};}}
            QPushButton[text="Cancel"]{{background:{C('surface')};color:{C('ink')};
              border:1px solid {C('line')};}}
            QPushButton[text="Cancel"]:hover{{background:{C('surface3')};}}
        """)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _combo(self, items: list, current: str) -> QComboBox:
        c = NoScrollComboBox()
        c.setStyleSheet(_INPUT_STYLE)
        for item in items:
            c.addItem(item)
        idx = c.findText(current)
        if idx >= 0:
            c.setCurrentIndex(idx)
        return c

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        # Language is chosen from the sidebar toggle, not here.
        self._theme = NoScrollComboBox()
        self._theme.setStyleSheet(_INPUT_STYLE)
        self._theme.addItem(L().t("theme_light"), "light")
        self._theme.addItem(L().t("theme_dark"), "dark")
        idx = self._theme.findData(self._settings.get("theme", "light"))
        self._theme.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow(L().t("theme_label"), self._theme)

        watch_row = QHBoxLayout()
        self._watch_folder = QLineEdit(self._settings.get("watch_folder", ""))
        self._watch_folder.setStyleSheet(_INPUT_STYLE)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(36)
        browse_btn.setStyleSheet(
            f"QPushButton{{background:{C('surface')};border:1px solid {C('line')};"
            "border-radius:8px;padding:4px;}"
            f"QPushButton:hover{{background:{C('surface3')};}}"
        )
        browse_btn.clicked.connect(self._browse_watch_folder)
        watch_row.addWidget(self._watch_folder, 1)
        watch_row.addWidget(browse_btn)
        form.addRow(L().t("set_watch_folder"), watch_row)

        self._due_days = QSpinBox()
        self._due_days.setRange(1, 90)
        self._due_days.setValue(self._settings.get("due_date_alert_days", 7))
        self._due_days.setStyleSheet(_INPUT_STYLE)
        form.addRow(L().t("set_due_alert"), self._due_days)

        return w

    def _build_currency_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        self._base_currency = self._combo(
            _CURRENCIES, self._settings.get("base_currency", "RON")
        )
        form.addRow(L().t("set_base_currency"), self._base_currency)

        # Source combo shows display labels; data stored as keys
        self._fx_source = NoScrollComboBox()
        self._fx_source.setStyleSheet(_INPUT_STYLE)
        current_src = self._settings.get("fx_source", "BNR")
        for key, label in SOURCE_LABELS.items():
            self._fx_source.addItem(label, key)
        idx = self._fx_source.findData(current_src)
        if idx >= 0:
            self._fx_source.setCurrentIndex(idx)
        form.addRow(L().t("set_fx_source"), self._fx_source)

        note = QLabel(L().t("set_fx_note"))
        note.setStyleSheet(f"color:{C('ink3')};font-size:11px;")
        note.setWordWrap(True)
        form.addRow("", note)

        return w

    def _build_ocr_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        tess_row = QHBoxLayout()
        self._tesseract_path = QLineEdit(self._settings.get("tesseract_path", ""))
        self._tesseract_path.setStyleSheet(_INPUT_STYLE)
        self._tesseract_path.setPlaceholderText(L().t("set_tesseract_ph"))
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(36)
        browse_btn.setStyleSheet(
            f"QPushButton{{background:{C('surface')};border:1px solid {C('line')};"
            "border-radius:8px;padding:4px;}"
            f"QPushButton:hover{{background:{C('surface3')};}}"
        )
        browse_btn.clicked.connect(self._browse_tesseract)
        tess_row.addWidget(self._tesseract_path, 1)
        tess_row.addWidget(browse_btn)
        form.addRow(L().t("set_tesseract_path"), tess_row)

        note = QLabel(L().t("set_ocr_note"))
        note.setStyleSheet(f"color:{C('ink3')};font-size:11px;")
        note.setWordWrap(True)
        form.addRow("", note)

        return w

    def _build_email_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        # how "Send email report" opens a message
        self._email_method = NoScrollComboBox()
        self._email_method.setStyleSheet(_INPUT_STYLE)
        self._email_method.addItem(L().t("email_method_outlook"), "outlook")
        self._email_method.addItem(L().t("email_method_default"), "mailto")
        idx = self._email_method.findData(self._settings.get("email_method", "outlook"))
        self._email_method.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow(L().t("set_email_method"), self._email_method)

        method_note = QLabel(L().t("set_email_method_note"))
        method_note.setStyleSheet(f"color:{C('ink3')};font-size:11px;")
        method_note.setWordWrap(True)
        form.addRow("", method_note)

        self._smtp_host = QLineEdit(self._settings.get("smtp_host", ""))
        self._smtp_host.setStyleSheet(_INPUT_STYLE)
        self._smtp_host.setPlaceholderText("smtp.gmail.com")
        form.addRow(L().t("set_smtp_host"), self._smtp_host)

        self._smtp_port = QSpinBox()
        self._smtp_port.setRange(1, 65535)
        self._smtp_port.setValue(self._settings.get("smtp_port", 587))
        self._smtp_port.setStyleSheet(_INPUT_STYLE)
        form.addRow(L().t("set_smtp_port"), self._smtp_port)

        self._smtp_user = QLineEdit(self._settings.get("smtp_user", ""))
        self._smtp_user.setStyleSheet(_INPUT_STYLE)
        form.addRow(L().t("set_smtp_user"), self._smtp_user)

        self._smtp_pass = QLineEdit(self._settings.get("smtp_password", ""))
        self._smtp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._smtp_pass.setStyleSheet(_INPUT_STYLE)
        form.addRow(L().t("set_smtp_pass"), self._smtp_pass)

        self._smtp_from = QLineEdit(self._settings.get("smtp_from", ""))
        self._smtp_from.setStyleSheet(_INPUT_STYLE)
        form.addRow(L().t("set_smtp_from"), self._smtp_from)

        to_list = self._settings.get("smtp_to", [])
        self._smtp_to = QLineEdit(", ".join(to_list) if isinstance(to_list, list) else to_list)
        self._smtp_to.setStyleSheet(_INPUT_STYLE)
        self._smtp_to.setPlaceholderText("email1@domain.com, email2@domain.com")
        form.addRow(L().t("set_smtp_to"), self._smtp_to)

        return w

    def _build_advanced_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        self._outlier_mult = QDoubleSpinBox()
        self._outlier_mult.setRange(0.5, 10.0)
        self._outlier_mult.setSingleStep(0.5)
        self._outlier_mult.setValue(self._settings.get("outlier_std_dev_multiplier", 2.0))
        self._outlier_mult.setStyleSheet(_INPUT_STYLE)
        form.addRow(L().t("set_outlier_mult"), self._outlier_mult)

        self._conf_threshold = QDoubleSpinBox()
        self._conf_threshold.setRange(0.0, 1.0)
        self._conf_threshold.setSingleStep(0.05)
        self._conf_threshold.setDecimals(2)
        self._conf_threshold.setValue(self._settings.get("confidence_threshold", 0.6))
        self._conf_threshold.setStyleSheet(_INPUT_STYLE)
        form.addRow(L().t("set_conf_threshold"), self._conf_threshold)

        return w

    def _build_debug_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        self._show_log = QCheckBox(L().t("set_show_log"))
        self._show_log.setChecked(bool(self._settings.get("show_log", False)))
        form.addRow(L().t("set_log_row"), self._show_log)

        note = QLabel(L().t("set_debug_note"))
        note.setStyleSheet(f"color:{C('ink3')};font-size:11px;")
        note.setWordWrap(True)
        form.addRow("", note)

        return w

    def _browse_watch_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, L().t("set_choose_folder"))
        if folder:
            self._watch_folder.setText(folder)

    def _browse_tesseract(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, L().t("set_choose_tesseract"), "", L().t("set_exe_filter")
        )
        if path:
            self._tesseract_path.setText(path)

    def _on_save(self) -> None:
        to_list = [e.strip() for e in self._smtp_to.text().split(",") if e.strip()]

        data = dict(self._settings)
        data.update({
            "theme":                     self._theme.currentData(),
            "watch_folder":              self._watch_folder.text().strip(),
            "due_date_alert_days":       self._due_days.value(),
            "base_currency":             self._base_currency.currentText(),
            "fx_source":                 self._fx_source.currentData(),
            "tesseract_path":            self._tesseract_path.text().strip(),
            "smtp_host":                 self._smtp_host.text().strip(),
            "smtp_port":                 self._smtp_port.value(),
            "smtp_user":                 self._smtp_user.text().strip(),
            "smtp_password":             self._smtp_pass.text(),
            "smtp_from":                 self._smtp_from.text().strip(),
            "smtp_to":                   to_list,
            "email_method":              self._email_method.currentData(),
            "outlier_std_dev_multiplier": self._outlier_mult.value(),
            "confidence_threshold":      self._conf_threshold.value(),
            "show_log":                  self._show_log.isChecked(),
        })
        _save(data)
        self.accept()
