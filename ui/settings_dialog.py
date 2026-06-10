import json
import os

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QDoubleSpinBox, QTabWidget, QVBoxLayout, QWidget,
)
from core.currency import SOURCE_LABELS

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


_INPUT_STYLE = (
    "QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox{"
    "background:#fefefe;border:1px solid #e3e5ec;border-radius:8px;"
    "padding:4px 8px;font-size:13px;color:#2e3552;min-height:28px;}"
    "QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus,QComboBox:focus{"
    "border-color:#2f8f6b;}"
    "QComboBox::drop-down{border:none;}"
    # dropdown popup: explicit colors so items are never white-on-white
    "QComboBox QAbstractItemView{"
    "background:#fefefe;color:#2e3552;border:1px solid #e3e5ec;"
    "selection-background-color:rgba(47,143,107,0.12);selection-color:#1a6b4f;}"
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setari")
        self.setMinimumWidth(500)
        self.setStyleSheet(
            "QDialog{background:#e2e6ed;}"
            "QLabel{color:#2e3552;background:transparent;}"
            "QCheckBox{color:#2e3552;background:transparent;}"
        )

        self._settings = _load()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane{background:#fefefe;border:1px solid #e3e5ec;border-radius:8px;}
            QTabBar::tab{background:#f4f5f8;color:#6b7291;padding:8px 16px;border:none;font-size:12px;}
            QTabBar::tab:selected{background:#fefefe;color:#2f8f6b;font-weight:bold;
              border-bottom:2px solid #2f8f6b;}
        """)

        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_currency_tab(), "Valuta")
        tabs.addTab(self._build_ocr_tab(), "OCR")
        tabs.addTab(self._build_email_tab(), "Email")
        tabs.addTab(self._build_advanced_tab(), "Avansat")
        root.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setStyleSheet("""
            QPushButton{background:#2f8f6b;color:white;border:none;border-radius:8px;
              padding:8px 20px;font-size:13px;font-weight:600;}
            QPushButton:hover{background:#1e7558;}
            QPushButton[text="Cancel"]{background:#fefefe;color:#2e3552;
              border:1px solid #e3e5ec;}
            QPushButton[text="Cancel"]:hover{background:#eeeff3;}
        """)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _combo(self, items: list, current: str) -> QComboBox:
        c = QComboBox()
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

        self._lang_ro = QCheckBox("Romana")
        self._lang_en = QCheckBox("English")
        lang = self._settings.get("language", "ro")
        self._lang_ro.setChecked(lang == "ro")
        self._lang_en.setChecked(lang == "en")
        self._lang_ro.toggled.connect(lambda c: self._lang_en.setChecked(not c) if c else None)
        self._lang_en.toggled.connect(lambda c: self._lang_ro.setChecked(not c) if c else None)
        lang_row = QHBoxLayout()
        lang_row.addWidget(self._lang_ro)
        lang_row.addWidget(self._lang_en)
        lang_row.addStretch()
        form.addRow("Limba:", lang_row)

        watch_row = QHBoxLayout()
        self._watch_folder = QLineEdit(self._settings.get("watch_folder", ""))
        self._watch_folder.setStyleSheet(_INPUT_STYLE)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(36)
        browse_btn.setStyleSheet(
            "QPushButton{background:#fefefe;border:1px solid #e3e5ec;"
            "border-radius:8px;padding:4px;}"
            "QPushButton:hover{background:#eeeff3;}"
        )
        browse_btn.clicked.connect(self._browse_watch_folder)
        watch_row.addWidget(self._watch_folder, 1)
        watch_row.addWidget(browse_btn)
        form.addRow("Folder monitorizat:", watch_row)

        self._due_days = QSpinBox()
        self._due_days.setRange(1, 90)
        self._due_days.setValue(self._settings.get("due_date_alert_days", 7))
        self._due_days.setStyleSheet(_INPUT_STYLE)
        form.addRow("Alerta scadenta (zile):", self._due_days)

        return w

    def _build_currency_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        self._base_currency = self._combo(
            _CURRENCIES, self._settings.get("base_currency", "RON")
        )
        form.addRow("Moneda de baza:", self._base_currency)

        # Source combo shows display labels; data stored as keys
        self._fx_source = QComboBox()
        self._fx_source.setStyleSheet(_INPUT_STYLE)
        current_src = self._settings.get("fx_source", "BNR")
        for key, label in SOURCE_LABELS.items():
            self._fx_source.addItem(label, key)
        idx = self._fx_source.findData(current_src)
        if idx >= 0:
            self._fx_source.setCurrentIndex(idx)
        form.addRow("Sursa curs valutar:", self._fx_source)

        note = QLabel(
            "Cursurile se actualizeaza zilnic de la banca nationala selectata.\n"
            "Bank of England si Federal Reserve (SUA) nu ofera API public gratuit; "
            "pentru baza GBP sau USD folositi open.er-api, care suporta orice moneda."
        )
        note.setStyleSheet("color:#6b7291;font-size:11px;")
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
        self._tesseract_path.setPlaceholderText("Auto-detectat daca este in PATH")
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(36)
        browse_btn.setStyleSheet(
            "QPushButton{background:#fefefe;border:1px solid #e3e5ec;"
            "border-radius:8px;padding:4px;}"
            "QPushButton:hover{background:#eeeff3;}"
        )
        browse_btn.clicked.connect(self._browse_tesseract)
        tess_row.addWidget(self._tesseract_path, 1)
        tess_row.addWidget(browse_btn)
        form.addRow("Cale Tesseract OCR:", tess_row)

        note = QLabel(
            "Tesseract OCR este necesar pentru facturile scanate.\n"
            "Descarca de la: https://github.com/UB-Mannheim/tesseract/wiki"
        )
        note.setStyleSheet("color:#6b7291;font-size:11px;")
        note.setWordWrap(True)
        form.addRow("", note)

        return w

    def _build_email_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        self._smtp_host = QLineEdit(self._settings.get("smtp_host", ""))
        self._smtp_host.setStyleSheet(_INPUT_STYLE)
        self._smtp_host.setPlaceholderText("smtp.gmail.com")
        form.addRow("Server SMTP:", self._smtp_host)

        self._smtp_port = QSpinBox()
        self._smtp_port.setRange(1, 65535)
        self._smtp_port.setValue(self._settings.get("smtp_port", 587))
        self._smtp_port.setStyleSheet(_INPUT_STYLE)
        form.addRow("Port SMTP:", self._smtp_port)

        self._smtp_user = QLineEdit(self._settings.get("smtp_user", ""))
        self._smtp_user.setStyleSheet(_INPUT_STYLE)
        form.addRow("Utilizator:", self._smtp_user)

        self._smtp_pass = QLineEdit(self._settings.get("smtp_password", ""))
        self._smtp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._smtp_pass.setStyleSheet(_INPUT_STYLE)
        form.addRow("Parola:", self._smtp_pass)

        self._smtp_from = QLineEdit(self._settings.get("smtp_from", ""))
        self._smtp_from.setStyleSheet(_INPUT_STYLE)
        form.addRow("De la (email):", self._smtp_from)

        to_list = self._settings.get("smtp_to", [])
        self._smtp_to = QLineEdit(", ".join(to_list) if isinstance(to_list, list) else to_list)
        self._smtp_to.setStyleSheet(_INPUT_STYLE)
        self._smtp_to.setPlaceholderText("email1@domain.com, email2@domain.com")
        form.addRow("Catre (email-uri):", self._smtp_to)

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
        form.addRow("Multiplicator deviatia standard:", self._outlier_mult)

        self._conf_threshold = QDoubleSpinBox()
        self._conf_threshold.setRange(0.0, 1.0)
        self._conf_threshold.setSingleStep(0.05)
        self._conf_threshold.setDecimals(2)
        self._conf_threshold.setValue(self._settings.get("confidence_threshold", 0.6))
        self._conf_threshold.setStyleSheet(_INPUT_STYLE)
        form.addRow("Prag incredere minima:", self._conf_threshold)

        return w

    def _browse_watch_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Selecteaza folder")
        if folder:
            self._watch_folder.setText(folder)

    def _browse_tesseract(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecteaza tesseract.exe", "", "Executabile (*.exe)"
        )
        if path:
            self._tesseract_path.setText(path)

    def _on_save(self) -> None:
        lang    = "ro" if self._lang_ro.isChecked() else "en"
        to_list = [e.strip() for e in self._smtp_to.text().split(",") if e.strip()]

        data = dict(self._settings)
        data.update({
            "language":                  lang,
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
            "outlier_std_dev_multiplier": self._outlier_mult.value(),
            "confidence_threshold":      self._conf_threshold.value(),
        })
        _save(data)
        self.accept()
