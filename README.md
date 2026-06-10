# Analyzen — Invoice Reader

A desktop application for bulk processing of PDF invoices. Extracts fields automatically via text parsing and OCR, validates against duplicates and anomalies, visualises data on a dashboard, and exports to Excel or PDF.

Built with PyQt6. Targets Romanian invoices but handles French, Italian, German, English, and other European formats.

---

## Features

- **Bulk PDF import** — drag-and-drop or folder select; parallel processing via `ThreadPoolExecutor`
- **Smart parser** — multi-strategy field extraction (keyword match → last 40% of document → arithmetic cross-validation); exclusion patterns prevent capital social, CUI, IBAN from being misidentified as invoice totals
- **OCR fallback** — scanned PDFs are processed through Tesseract; additional language packs downloaded at runtime
- **Multilingual UI** — 11 languages: Romanian, English, German, French, Italian, Spanish, Portuguese, Polish, Russian, Dutch, Danish; switch live without restarting
- **Validation** — duplicate detection (invoice number + supplier CUI), outlier flagging (mean ± N·σ), near-due alerts
- **Dashboard** — KPI cards, monthly bar chart, category donut chart, top-10 supplier chart
- **Table view** — sortable, filterable by flag type, full-text search
- **Export** — multi-sheet Excel (all invoices + summary + flagged), PDF report, email via SMTP
- **Folder watcher** — monitors a directory and auto-processes new PDFs (2 s debounce)
- **Windows installer** — Inno Setup script with bundled Tesseract (ron + eng); other language packs downloaded on demand

---

## Screenshots

> Dashboard with KPI cards and charts after loading a batch of invoices.

---

## Requirements

- Python 3.10+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (optional — only needed for scanned PDFs)
- Windows 10/11 (tested); Linux/macOS should work with minor path adjustments

---

## Installation

```bash
git clone https://github.com/andrei820177/analyzen-invoice-reader.git
cd analyzen-invoice-reader

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
```

Copy the example settings file before first run:

```bash
copy config\settings.example.json config\settings.json
```

---

## Running

```bash
python main.py
```

---

## Project Structure

```
analyzen-invoice-reader/
├── main.py                     # Entry point
├── requirements.txt
├── build.spec                  # PyInstaller spec
├── installer.iss               # Inno Setup script
│
├── config/
│   ├── settings.json           # User config (gitignored)
│   ├── settings.example.json   # Template
│   └── lang/                   # 11 language JSON files
│
├── core/
│   ├── parser.py               # Field extraction + smart total resolver
│   ├── extractor.py            # PDF → Invoice (pdfplumber + OCR fallback)
│   ├── classifier.py           # Category classifier (8 categories)
│   ├── ocr.py                  # Tesseract wrapper
│   ├── ocr_lang_manager.py     # Runtime tessdata downloader
│   └── watcher.py              # Folder watcher (watchdog)
│
├── data/
│   ├── models.py               # Invoice / LineItem dataclasses
│   ├── processor.py            # InvoiceDataFrame (pandas wrapper)
│   └── validator.py            # Duplicate / outlier / near-due checks
│
├── export/
│   ├── excel_exporter.py       # openpyxl multi-sheet export
│   ├── pdf_reporter.py         # reportlab report
│   └── email_sender.py         # SMTP with attachment
│
├── ui/
│   ├── main_window.py          # QMainWindow, worker thread, drop zone
│   ├── dashboard.py            # KPI cards, pyqtgraph charts, donut chart
│   ├── table_view.py           # QAbstractTableModel + proxy filter
│   ├── log_panel.py            # Processing log (Ctrl+L to toggle)
│   ├── settings_dialog.py      # 4-tab settings dialog
│   ├── lang.py                 # Global translator singleton L()
│   ├── ocr_lang_dialog.py      # Runtime tessdata downloader dialog
│   └── components/
│       ├── sidebar.py          # Navigation sidebar
│       ├── language_toggle.py  # Language selector combo
│       └── progress_bar.py     # Processing progress strip
│
├── tools/
│   └── build_installer.py      # PyInstaller → Tesseract copy → ISCC
│
└── design/
    └── reference.html          # UI reference mockup
```

---

## Configuration

Edit `config/settings.json` (created from `settings.example.json`):

| Key | Default | Description |
|-----|---------|-------------|
| `language` | `"ro"` | UI language code |
| `watch_folder` | `""` | Folder to auto-monitor for new PDFs |
| `auto_watch` | `false` | Start watching on launch |
| `due_date_alert_days` | `7` | Days before due date to flag |
| `outlier_std_dev_multiplier` | `2.0` | σ multiplier for outlier detection |
| `tesseract_path` | `""` | Path to `tesseract.exe` (auto-detected if empty) |
| `confidence_threshold` | `0.6` | Minimum parse confidence score |
| `smtp_*` | — | SMTP credentials for email export |

---

## Building the Windows Installer

Requires Inno Setup 6 and a local Tesseract installation in `tools/tesseract/`.

```bash
python tools/build_installer.py
```

This runs PyInstaller, copies the Tesseract binaries, downloads `ron.traineddata` and `eng.traineddata`, then compiles the Inno Setup script.

---

## Supported Invoice Languages

The parser handles Romanian keywords natively. Additional keyword sets cover:

| Language | Date labels | VAT label | Total label |
|----------|-------------|-----------|-------------|
| Romanian | Data, Data emiterii | TVA, Valoare TVA | Total de plata, De achitat |
| French | Date, Date de facture | TVA, Montant TVA | Total TTC, Net à payer |
| Italian | Data fattura, Data emissione | IVA, Importo IVA | Totale fattura, Totale da pagare |
| German | Datum, Rechnungsdatum | MwSt., MwSt-Betrag | Gesamtbetrag, Rechnungsbetrag |
| English | Date, Invoice date | VAT amount, Tax amount | Grand total, Amount due |

---

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Stable releases |
| `beta` | Pre-release features under testing |
| `test` | Experimental work and CI |

---

## License

MIT
