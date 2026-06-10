import re
import logging
from datetime import date
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Amount sanity bounds
# ---------------------------------------------------------------------------

_MAX_INVOICE_AMOUNT = 2_000_000.0   # above this it's almost certainly not an invoice total
_MIN_INVOICE_AMOUNT = 0.01

def _is_reasonable(val: Optional[float]) -> bool:
    return val is not None and _MIN_INVOICE_AMOUNT <= val <= _MAX_INVOICE_AMOUNT


# ---------------------------------------------------------------------------
# Context exclusion — amounts near these strings are NOT invoice totals
# ---------------------------------------------------------------------------

_EXCLUSION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in [
    r'capital\s+social',
    r'capital\s+subscris',
    r'capitalul\s+social',
    r'capital\s+varsat',
    r'nr\.?\s*(?:inmatriculare|înregistrare|ordine|ord\.?)',
    r'registrul?\s+comer',
    r'cod\s+(?:fiscal|unic)',
    r'c\.?u\.?i\.?\s*:',
    r'c\.?i\.?f\.?\s*:',
    r'sold\s+(?:precedent|anterior|initial|vechi|curent)',
    r'(?:index|contor)\s+(?:vechi|precedent|anterior|nou)',
    r'nr\.?\s+contract',
    r'cont\s+(?:bancar|curent)',
    r'\biban\b',
    r'bilan',
    r'actionar',
    r'fond\s+de\s+rezerv',
    r'profit\s+(?:net|brut)',
    r'cifr[aă]\s+de\s+afaceri',
]]

_EXCL_WINDOW = 150  # chars to look BEFORE the matched amount


def _context_is_excluded(text: str, pos: int) -> bool:
    # Only scan backwards — a footer IBAN/CUI that appears AFTER the total
    # amount should not invalidate it; only header context before the amount matters.
    snippet = text[max(0, pos - _EXCL_WINDOW): pos]
    return any(p.search(snippet) for p in _EXCLUSION_PATTERNS)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

_DATE_YMD = re.compile(r'(\d{4})[.\-](\d{2})[.\-](\d{2})')
_DATE_DMY = re.compile(r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})')
_DATE_TEXT = re.compile(
    r'(\d{1,2})\s+'
    r'(ianuarie|ian|februarie|feb|martie|mar|aprilie|apr|mai|iunie|iun'
    r'|iulie|iul|august|aug|septembrie|sep|octombrie|oct|noiembrie|noi|decembrie|dec)'
    r'\s+(\d{4})',
    re.IGNORECASE,
)
_MONTH_RO = {
    'ian': 1, 'ianuarie': 1, 'feb': 2, 'februarie': 2,
    'mar': 3, 'martie': 3, 'apr': 4, 'aprilie': 4, 'mai': 5,
    'iun': 6, 'iunie': 6, 'iul': 7, 'iulie': 7,
    'aug': 8, 'august': 8, 'sep': 9, 'septembrie': 9,
    'oct': 10, 'octombrie': 10, 'noi': 11, 'noiembrie': 11,
    'dec': 12, 'decembrie': 12,
}


def _parse_date(text: str) -> Optional[date]:
    for pat, order in [(_DATE_YMD, 'ymd'), (_DATE_DMY, 'dmy')]:
        m = pat.search(text)
        if m:
            try:
                if order == 'ymd':
                    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1 <= mo <= 12 and 1 <= d <= 31:
                    return date(y, mo, d)
            except ValueError:
                pass

    m = _DATE_TEXT.search(text)
    if m:
        try:
            month = _MONTH_RO.get(m.group(2).lower(), 0)
            if month:
                return date(int(m.group(3)), month, int(m.group(1)))
        except ValueError:
            pass
    return None


def _extract_date_near_keywords(text: str, keywords: List[str]) -> Optional[date]:
    for kw in keywords:
        m = re.search(re.escape(kw) + r'\s*:?\s*(.{0,50})', text, re.IGNORECASE)
        if m:
            d = _parse_date(m.group(1))
            if d:
                return d
    return None


# ---------------------------------------------------------------------------
# Amount helpers
# ---------------------------------------------------------------------------

# Matches: 1.234,56 | 1,234.56 | 1234.56 | 1234,56 | 1 234.56
_RAW_AMOUNT = re.compile(r'\b(\d{1,3}(?:[., ]\d{3})*(?:[.,]\d{1,2})?|\d+[.,]\d{1,2}|\d{4,})\b')


def _parse_amount(text: str) -> Optional[float]:
    text = re.sub(r'[^\d.,\s]', '', text).strip()
    if not text:
        return None
    # 1.234,56 -> 1234.56
    if re.match(r'^\d{1,3}(\.\d{3})+(,\d{1,2})?$', text):
        text = text.replace('.', '').replace(',', '.')
    # 1,234.56 -> 1234.56
    elif re.match(r'^\d{1,3}(,\d{3})+(\. \d{1,2})?$', text):
        text = text.replace(',', '')
    # 1 234,56 (Romanian space thousand sep)
    elif re.match(r'^\d{1,3}( \d{3})+(,\d{1,2})?$', text):
        text = text.replace(' ', '').replace(',', '.')
    # 1234,56 or 1234.56
    else:
        text = text.replace(',', '.').replace(' ', '')
    try:
        return float(text)
    except ValueError:
        return None


def _extract_amount_after_keyword(text: str, keywords: List[str],
                                   allow_large: bool = False) -> Optional[float]:
    """Find the first reasonable amount appearing after any of the keywords."""
    for kw in keywords:
        pat = re.compile(
            r'(?<![A-Za-z\-])'        # prevent matching mid-compound (e.g. "Sous-total:" should not fire "Total:")
            + re.escape(kw)
            # separator: punctuation/space, optionally a currency token or symbol, more space
            + r'[\s:.\-|]*(?:\d{1,3}\s*%\s*[:\|]?\s*)?(?:(?:RON|LEI|EUR|USD|GBP)\b|[\u20ac\xa3\$\xa5])?[\s:.\-|]*'
            + r'([0-9][0-9 .,]{0,20})',
            re.IGNORECASE,
        )
        for m in pat.finditer(text):
            if _context_is_excluded(text, m.start(1)):
                continue
            val = _parse_amount(m.group(1))
            if val is not None and val > 0:
                if allow_large or _is_reasonable(val):
                    return val
    return None


def _find_all_candidate_amounts(text: str) -> List[Tuple[float, int]]:
    """Return (value, position) for all amounts NOT in excluded contexts."""
    results = []
    for m in _RAW_AMOUNT.finditer(text):
        if _context_is_excluded(text, m.start()):
            continue
        val = _parse_amount(m.group(1))
        if val is not None and _is_reasonable(val):
            results.append((val, m.start()))
    return results


# ---------------------------------------------------------------------------
# Smart total resolver
# ---------------------------------------------------------------------------

_TOTAL_KEYWORDS = [
    # Romanian
    "Total de plata", "Total de plătit", "Total de achitat",
    "Suma de plata", "Suma de plătit", "Suma totala de plata",
    "Valoare totala de plata", "Valoare de plata",
    "Total factura", "Total factură", "Total facturii",
    "Total general", "DE ACHITAT", "De achitat",
    "TOTAL DE PLATA", "TOTAL DE PLĂTIT",
    "Total:", "TOTAL:",
    # English
    "Total amount due", "Amount due", "Total due", "Invoice total",
    "Grand total", "Total payable", "Balance due",
    # French
    "Total TTC", "TOTAL TTC", "Total à payer", "Montant TTC",
    "Net à payer", "NET A PAYER",
    # Italian
    "Totale fattura", "Totale documento", "Totale da pagare", "Importo totale",
    "Totale dovuto", "Totale:",
    # German
    "Gesamtbetrag", "Rechnungsbetrag", "Zu zahlen", "Gesamtsumme",
    "Brutto", "BRUTTO", "Bruttopreis", "Bruttobetrag",
    # Utility-bill specific
    "Valoarea totala a facturii",
    "Valoare totala factura",
    "Contravaloare totala",
    "Total de plata (inclusiv TVA)",
]

_SUBTOTAL_KEYWORDS = [
    # Romanian
    "Subtotal", "Baza impozabila", "Baza impozabilă",
    "Valoare fara TVA", "Valoare fără TVA",
    "Net amount", "Valoare neta", "Valoare netă",
    "Total fara TVA", "Total fără TVA",
    "Valoare servicii",
    # French
    "HT", "Total HT", "Montant HT", "Sous-total HT", "Base HT",
    # Italian
    "Imponibile", "Totale imponibile", "Base imponibile",
    # German
    "Netto", "Nettobetrag", "Zwischensumme",
]

# Most specific patterns first to avoid capturing the rate number (e.g. "TVA 20%"
# → "20") instead of the actual monetary amount.
_VAT_KEYWORDS = [
    # Explicit "amount" labeling — most reliable
    "Valoare TVA", "Valoare T.V.A.", "VAT amount", "Tax amount",
    # French
    "Montant TVA", "Montant de la TVA", "Montant T.V.A.",
    # Italian
    "Importo IVA", "Totale IVA", "Ammontare IVA",
    # German
    "MwSt-Betrag", "MwSt. Betrag", "Mehrwertsteuer",
    # Rate-specific (amount follows the rate label)
    "TVA 22%", "TVA 21%", "TVA 20%", "TVA 19%", "TVA 9%", "TVA 5%",
    "IVA 22%", "IVA 21%", "IVA 20%", "IVA 10%", "IVA 5%",
    # Generic fallbacks — may capture rate integer, handled in post-processing
    "T.V.A.", "IVA", "MwSt.", "TVA",
]


def _find_total(text: str,
                subtotal: Optional[float],
                vat: Optional[float]) -> Tuple[Optional[float], bool]:
    """
    Multi-strategy total resolution.
    Returns (total, is_reliable).
    """
    # Strategy 1: keyword match with context check
    total = _extract_amount_after_keyword(text, _TOTAL_KEYWORDS)
    if total and _is_reasonable(total):
        return total, True

    # Strategy 2: search in last 40% of text (totals are at the bottom)
    lines = text.splitlines()
    last_part = "\n".join(lines[max(0, int(len(lines) * 0.6)):])
    total = _extract_amount_after_keyword(last_part, ["Total", "TOTAL", "Suma", "SUMA"])
    if total and _is_reasonable(total):
        return total, True

    # Strategy 3: cross-validate using subtotal + vat
    if subtotal and vat and subtotal > 0 and vat > 0:
        expected = round(subtotal + vat, 2)
        if _is_reasonable(expected):
            # Look for an amount close to expected (within 2%)
            for val, pos in _find_all_candidate_amounts(text):
                if abs(val - expected) / expected < 0.02:
                    return val, True
            # If nothing found, compute it
            return expected, False  # derived, mark as less reliable

    # Strategy 4: last resort — only if we have NO subtotal or vat clues at all
    # Use the LAST reasonable amount in the document (NOT the largest)
    candidates = _find_all_candidate_amounts(text)
    if candidates:
        # Sort by position descending; take the latest amount
        latest = sorted(candidates, key=lambda x: -x[1])[0]
        if _is_reasonable(latest[0]) and latest[0] > 1.0:
            return latest[0], False  # unreliable

    return None, False


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------

def _extract_supplier_name(text: str) -> str:
    # Only look in the first 40% of the document (header area)
    lines = text.splitlines()
    header = "\n".join(lines[:max(4, int(len(lines) * 0.4))])

    patterns = [
        r'(?:Furnizor|Emitent|Vânzător|Prestator|Prestator\s+de\s+servicii|Seller)\s*[:\-]?\s*([^\n\r]{4,60})',
        r'(S\.C\.\s*[A-Z][^\n\r]{3,50}(?:S\.R\.L\.|S\.A\.|R\.A\.|SRL|SA))',
        r'([A-Z][A-Z\s\-&]{2,40}(?:SRL|SA|S\.R\.L\.|S\.A\.|RA|SNC))',
    ]
    for pat in patterns:
        m = re.search(pat, header, re.IGNORECASE)
        if m:
            val = m.group(1).strip().rstrip(',;.:')
            # Reject if it contains suspicious financial terms
            if re.search(r'capital|registr|fiscal|cont\s|iban|cif|cui', val, re.IGNORECASE):
                continue
            if len(val) >= 3:
                return val
    return ""


def _extract_cui(text: str) -> str:
    m = re.search(
        r'(?:CUI|CIF|C\.U\.I\.|C\.I\.F\.)\s*[:\-]?\s*(RO\s*)?(\d{6,10})',
        text, re.IGNORECASE,
    )
    if m:
        prefix = "RO" if m.group(1) else ""
        return prefix + m.group(2).replace(" ", "")
    return ""


def _extract_iban(text: str) -> str:
    m = re.search(r'\b(RO\d{2}[A-Z0-9]{18,22})\b', text, re.IGNORECASE)
    return m.group(1).upper().replace(" ", "") if m else ""


def _extract_invoice_number(text: str) -> str:
    patterns = [
        r'(?:Factura\s+(?:fiscala\s+)?nr\.?|Nr\.?\s+factur[aă]|Invoice\s+No\.?|Nr\.?\s+invoice|Seria\s+\w+\s+Nr\.?)\s*[:\-]?\s*([A-Z0-9\-/]{2,20})',
        r'(?:Factura|Invoice)\s*[:\-]?\s*([A-Z]{0,4}[-\s]?\d{4,10})',
        r'\b((?:FCT|FAC|INV|FC|FF)[A-Z0-9\-]{2,15})\b',
        r'\b([A-Z]{2,4}[-\s]?\d{4,8})\b',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if val:
                return val
    return ""


def _extract_currency(text: str) -> str:
    # Try spelled-out currency code first
    m = re.search(r'\b(RON|EUR|USD|GBP|lei)\b', text, re.IGNORECASE)
    if m:
        raw = m.group(1).upper()
        return "RON" if raw == "LEI" else raw
    # Fall back to currency symbols
    if '\u20ac' in text:   # €
        return 'EUR'
    if '\xa3' in text:     # £
        return 'GBP'
    if '\u0024' in text and '\u20ac' not in text:  # $ but not €
        return 'USD'
    return 'RON'  # last-resort default


def _extract_vat_rate(text: str) -> float:
    m = re.search(r'(?:TVA|VAT)\s*[:\-]?\s*(\d{1,2})\s*%', text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 19.0


# ---------------------------------------------------------------------------
# Line items
# ---------------------------------------------------------------------------

# Header keywords used to map table columns to fields (multi-language).
_COL_PATTERNS = {
    "description": [r'denumire', r'descriere', r'produs', r'serviciu',
                    r'specifica', r'articol', r'description', r'désignation',
                    r'designation', r'descrizione'],
    "quantity":   [r'cantitate', r'\bcant\b', r'\bbuc\b', r'\bqty\b',
                   r'quantity', r'quantité', r'quantita', r'\bu\.?m\.?\b'],
    "unit_price": [r'pre[tţț]\s*unitar', r'unit\s*price', r'prix\s*unitaire',
                   r'prezzo\s*unit', r'\bp\.?u\.?\b', r'pre[tţț]'],
    "total":      [r'valoare', r'\btotal\b', r'amount', r'montant',
                   r'importo', r'sum[aă]'],
}


def _map_table_columns(header: List) -> Dict[str, int]:
    """Map field name -> column index using header text. Empty if no header match."""
    mapping: Dict[str, int] = {}
    cells = [str(c or "").lower() for c in header]
    for key, pats in _COL_PATTERNS.items():
        for idx, cell in enumerate(cells):
            if any(re.search(p, cell) for p in pats):
                mapping[key] = idx  # for "total", last match wins (rightmost value col)
                if key != "total":
                    break
    return mapping


def _cell_amount(row: List, idx: Optional[int]) -> Optional[float]:
    if idx is None or idx < 0 or idx >= len(row) or row[idx] is None:
        return None
    return _parse_amount(str(row[idx]))


def _parse_table_row(row: List, colmap: Optional[Dict[str, int]] = None) -> Optional[Dict[str, Any]]:
    if not row or len(row) < 3:
        return None

    # Preferred path: header-driven column mapping
    if colmap and "description" in colmap and "total" in colmap:
        try:
            desc = str(row[colmap["description"]] or "").strip()
            total = _cell_amount(row, colmap["total"])
            qty = _cell_amount(row, colmap.get("quantity"))
            unit_price = _cell_amount(row, colmap.get("unit_price"))
            if desc and total is not None and _is_reasonable(total) and total > 0:
                return {"description": desc,
                        "quantity": qty if qty and qty > 0 else 1.0,
                        "unit_price": unit_price if unit_price and unit_price > 0 else 0.0,
                        "total": total}
        except Exception:
            pass  # fall through to positional heuristic

    # Fallback: rightmost numeric is total, next is unit price, next is qty
    try:
        numeric_vals = []
        for cell in reversed(row):
            if cell is None:
                continue
            v = _parse_amount(str(cell))
            if v is not None and _is_reasonable(v):
                numeric_vals.append(v)
            if len(numeric_vals) == 3:
                break
        if len(numeric_vals) >= 2:
            total = numeric_vals[0]
            unit_price = numeric_vals[1]
            qty = numeric_vals[2] if len(numeric_vals) >= 3 else 1.0
            desc = str(row[0] or "").strip()
            if desc and total > 0:
                return {"description": desc, "quantity": qty,
                        "unit_price": unit_price, "total": total}
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_fields(raw_text: str, tables: Optional[List] = None) -> Dict[str, Any]:
    errors: List[str] = []

    def _track(val, name: str):
        if not val:
            errors.append(f"Could not extract: {name}")
        return val

    supplier_name  = _track(_extract_supplier_name(raw_text), "supplier_name")
    supplier_cui   = _track(_extract_cui(raw_text), "supplier_cui")
    supplier_iban  = _extract_iban(raw_text)

    invoice_number = _track(_extract_invoice_number(raw_text), "invoice_number")
    currency       = _extract_currency(raw_text)
    vat_rate       = _extract_vat_rate(raw_text)

    issue_date = _track(
        _extract_date_near_keywords(raw_text, [
            # Romanian
            "Data:", "Data emiterii:", "Emisa la:", "Issue date:",
            "Data facturii:", "Data emitere:", "Emis la:", "Data emis",
            "Data factura", "Emisa in data de",
            # French
            "Date:", "Date de facture:", "Date de facturation:", "Date d'émission:",
            "Émis le:", "Emis le:", "Date d'émission",
            # Italian
            "Data fattura:", "Data emissione:", "Del:",
            # German
            "Datum:", "Rechnungsdatum:", "Ausstellungsdatum:", "Belegdatum:",
            # English (generic)
            "Invoice date:", "Issued:", "Issue date:",
        ]),
        "issue_date",
    )

    due_date = _extract_date_near_keywords(raw_text, [
        # Romanian
        "Scadenta:", "Termen plata:", "Termen de plata:", "Due date:",
        "Data scadentei:", "Scadent la:", "Data scadenta:", "Termen scadenta",
        # French
        "Date d'échéance:", "Date limite de paiement:", "Échéance:",
        # Italian
        "Data scadenza:", "Scadenza:", "Pagamento entro:",
        # German
        "Fälligkeitsdatum:", "Zahlungsziel:", "Fällig am:",
    ])

    subtotal = _extract_amount_after_keyword(raw_text, _SUBTOTAL_KEYWORDS)
    vat_amount = _extract_amount_after_keyword(raw_text, _VAT_KEYWORDS)

    # If extracted vat_amount looks like a VAT rate (a small integer 1–30),
    # it's the percentage, not the monetary amount — discard and let arithmetic derive it.
    if vat_amount is not None and 1 <= vat_amount <= 30 and vat_amount == int(vat_amount):
        logger.debug("Discarding likely VAT rate captured as amount: %.0f", vat_amount)
        vat_amount = None

    # Restrict VAT amount: if it's unreasonably large vs expected, discard
    if vat_amount and subtotal and vat_amount > subtotal * 0.5:
        logger.warning("Discarding implausible VAT amount: %.2f (subtotal: %.2f)", vat_amount, subtotal)
        vat_amount = None

    total, total_reliable = _find_total(raw_text, subtotal, vat_amount)

    if not total_reliable and total:
        errors.append("total: extracted via fallback — verify manually")

    if not total:
        errors.append("Could not extract: total")

    # Derive missing values arithmetically
    if total and subtotal and not vat_amount:
        derived = round(total - subtotal, 2)
        if derived > 0:
            vat_amount = derived
    if total and vat_amount and not subtotal:
        subtotal = round(total - vat_amount, 2)
    if subtotal and vat_rate and not total:
        total = round(subtotal * (1 + vat_rate / 100), 2)

    # Sanity check: if total is wildly inconsistent with subtotal+vat, flag it
    if total and subtotal and vat_amount:
        expected = subtotal + vat_amount
        if abs(total - expected) / max(expected, 1) > 0.10:
            errors.append(
                f"total inconsistency: total={total:.2f} but subtotal+vat={expected:.2f}"
            )

    # Line items from tables
    line_items = []
    if tables:
        for table in tables:
            if not table:
                continue
            colmap = _map_table_columns(table[0])
            for row in table[1:]:
                item = _parse_table_row(row, colmap)
                if item:
                    line_items.append(item)

    # Confidence = fraction of core fields actually extracted.
    # iban and due_date are legitimately absent on many invoices, so they
    # are excluded from the score to avoid penalising valid documents.
    core_fields = [supplier_name, supplier_cui, invoice_number,
                   issue_date, subtotal, vat_amount, total]
    fields_extracted = sum(1 for f in core_fields if f)
    confidence = round(fields_extracted / len(core_fields), 2)

    return {
        "supplier_name":  supplier_name or "",
        "supplier_cui":   supplier_cui or "",
        "supplier_iban":  supplier_iban or "",
        "invoice_number": invoice_number or "",
        "issue_date":     issue_date,
        "due_date":       due_date,
        "subtotal":       subtotal or 0.0,
        "vat_amount":     vat_amount or 0.0,
        "vat_rate":       vat_rate,
        "total":          total or 0.0,
        "currency":       currency,
        "line_items":     line_items,
        "confidence_score": confidence,
        "parse_errors":   errors,
    }
