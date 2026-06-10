"""
Invoice field parser.

Line-oriented, scoring-based extraction:
  1. The document is split into lines; every monetary keyword match produces
     a scored candidate (keyword specificity + position in document).
  2. Candidates are cross-validated arithmetically (total = subtotal + VAT)
     and the consistent set wins over any single keyword match.
  3. Amounts attached to percentages, dates, years and excluded contexts
     (capital social, IBAN, CUI, meter readings...) are never candidates.

Supported invoice languages: RO, EN, FR, DE, IT, ES, PL, PT, NL.
"""

import re
import logging
from datetime import date
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sanity bounds
# ---------------------------------------------------------------------------

_MAX_INVOICE_AMOUNT = 2_000_000.0
_MIN_INVOICE_AMOUNT = 0.01


def _is_reasonable(val: Optional[float]) -> bool:
    return val is not None and _MIN_INVOICE_AMOUNT <= val <= _MAX_INVOICE_AMOUNT


# ---------------------------------------------------------------------------
# Context exclusion — lines matching these never yield amount candidates
# ---------------------------------------------------------------------------

_EXCLUSION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in [
    r'capital\s+social', r'capital\s+subscris', r'capitalul\s+social',
    r'capital\s+varsat', r'share\s+capital', r'stammkapital',
    r'nr\.?\s*(?:inmatriculare|înregistrare|ordine|ord\.?)',
    r'registrul?\s+comer', r'handelsregister', r'\bRCS\b', r'\bSIRET\b',
    r'cod\s+(?:fiscal|unic)', r'c\.?u\.?i\.?\s*:', r'c\.?i\.?f\.?\s*:',
    r'\bUSt-?IdNr\b', r'\bP\.?\s*IVA\b', r'\bNIP\b',
    r'sold\s+(?:precedent|anterior|initial|vechi|curent)',
    r'(?:index|contor)\s+(?:vechi|precedent|anterior|nou)',
    r'nr\.?\s+contract', r'cont\s+(?:bancar|curent)', r'\biban\b', r'\bswift\b',
    r'bilan', r'actionar', r'fond\s+de\s+rezerv',
    r'profit\s+(?:net|brut)', r'cifr[aă]\s+de\s+afaceri',
    r'telefon|telephone|\btel\b|\bfax\b|\bphone\b',
    r'cod\s+po[sș]tal|postal\s+code|\bzip\b|\bPLZ\b',
]]


def _line_excluded(line: str) -> bool:
    return any(p.search(line) for p in _EXCLUSION_PATTERNS)


# ---------------------------------------------------------------------------
# Amount tokenizer
# ---------------------------------------------------------------------------

# 1.234,56 | 1,234.56 | 1 234,56 | 1234.56 | 1234,56 | 1234
_AMOUNT_TOKEN = re.compile(
    r'(?<![\d.,/-])('
    r'\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?'     # 1.234.567,89
    r'|\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?'    # 1,234,567.89
    r'|\d{1,3}(?: \d{3})+(?:[.,]\d{1,2})?'  # 1 234 567,89
    r'|\d+[.,]\d{1,2}'                       # 1234,56
    r'|\d+'                                  # 1234
    r')(?![\d.,/-]|\s*%)'                    # not part of a longer number, date or percentage
)


def _parse_amount(token: str) -> Optional[float]:
    t = token.strip()
    if re.match(r'^\d{1,3}(\.\d{3})+(,\d{1,2})?$', t):
        t = t.replace('.', '').replace(',', '.')
    elif re.match(r'^\d{1,3}(,\d{3})+(\.\d{1,2})?$', t):
        t = t.replace(',', '')
    elif re.match(r'^\d{1,3}( \d{3})+([.,]\d{1,2})?$', t):
        t = t.replace(' ', '').replace(',', '.')
    else:
        t = t.replace(',', '.')
    try:
        return float(t)
    except ValueError:
        return None


def _looks_like_year(token: str, val: float) -> bool:
    return '.' not in token and ',' not in token and 1990 <= val <= 2099


def _amounts_in(line: str, start: int = 0) -> List[Tuple[float, str]]:
    """All plausible monetary values in line[start:], left to right."""
    out: List[Tuple[float, str]] = []
    for m in _AMOUNT_TOKEN.finditer(line[start:]):
        token = m.group(1)
        val = _parse_amount(token)
        if val is None or not _is_reasonable(val):
            continue
        if _looks_like_year(token, val):
            continue
        out.append((val, token))
    return out


# ---------------------------------------------------------------------------
# Monetary keyword specs: (regex, weight) — higher weight = more specific
# ---------------------------------------------------------------------------

def _kw(parts: List[str]) -> str:
    return r'(?<![\w-])(?:' + '|'.join(parts) + r')'


_TOTAL_SPECS = [
    # weight 5: unambiguous "amount payable"
    (re.compile(_kw([
        r'total\s+de\s+plat[aă]', r'total\s+de\s+pl[aă]tit', r'total\s+de\s+achitat',
        r'suma\s+de\s+plat[aă]', r'suma\s+de\s+pl[aă]tit', r'de\s+achitat',
        r'valoare\s+total[aă]\s+de\s+plat[aă]', r'rest\s+de\s+plat[aă]',
        r'total\s+amount\s+due', r'amount\s+due', r'balance\s+due', r'total\s+payable',
        r'net\s+[aà]\s+payer', r'total\s+[aà]\s+payer',
        r'totale\s+da\s+pagare', r'totale\s+dovuto',
        r'zu\s+zahlen(?:der\s+betrag)?', r'zahlbetrag',
        r'total\s+a\s+pagar', r'importe\s+a\s+pagar',
        r'do\s+zap[lł]aty', r'razem\s+do\s+zap[lł]aty',
        r'te\s+betalen',
    ]), re.IGNORECASE), 5),
    # weight 4: "invoice total" / gross total
    (re.compile(_kw([
        r'total\s+factur[aăi]+', r'valoarea?\s+total[aă]\s+a?\s*facturii?',
        r'total\s+general', r'contravaloare\s+total[aă]',
        r'invoice\s+total', r'grand\s+total',
        r'total\s+TTC', r'montant\s+TTC',
        r'totale\s+fattura', r'totale\s+documento', r'importo\s+totale',
        r'gesamtbetrag', r'rechnungsbetrag', r'gesamtsumme', r'bruttobetrag',
        r'total\s+factura', r'importe\s+total',
        r'warto[sś][cć]\s+brutto', r'suma\s+brutto',
        r'totaal\s+incl', r'totaalbedrag',
    ]), re.IGNORECASE), 4),
    # weight 2: generic total / brutto
    (re.compile(_kw([
        r'total', r'totale', r'totaal', r'razem', r'gesamt', r'brutto', r'suma',
    ]), re.IGNORECASE), 2),
]

_SUBTOTAL_SPECS = [
    (re.compile(_kw([
        r'baza\s+impozabil[aă]', r'valoare\s+f[aă]r[aă]\s+TVA', r'total\s+f[aă]r[aă]\s+TVA',
        r'valoare\s+net[aă]', r'subtotal', r'sub-total', r'net\s+amount',
        r'total\s+HT', r'montant\s+HT', r'sous-total', r'base\s+HT',
        r'(?:totale\s+)?imponibile', r'base\s+imponibile',
        r'nettobetrag', r'zwischensumme', r'summe\s+netto', r'netto(?:summe)?',
        r'base\s+imponible', r'warto[sś][cć]\s+netto', r'suma\s+netto',
        r'totaal\s+excl', r'subtotaal',
    ]), re.IGNORECASE), 4),
    (re.compile(_kw([r'\bHT\b', r'valoare\s+servicii']), re.IGNORECASE), 2),
]

_VAT_SPECS = [
    (re.compile(_kw([
        r'valoare\s+T\.?V\.?A\.?', r'total\s+T\.?V\.?A\.?',
        r'VAT\s+amount', r'tax\s+amount', r'total\s+VAT', r'sales\s+tax',
        r'montant\s+(?:de\s+la\s+)?T\.?V\.?A\.?', r'total\s+TVA',
        r'importo\s+IVA', r'totale\s+IVA', r'ammontare\s+IVA',
        r'MwSt\.?-?\s?Betrag', r'Umsatzsteuer(?:betrag)?', r'Mehrwertsteuer',
        r'importe\s+IVA', r'cuota\s+IVA',
        r'kwota\s+VAT', r'podatek\s+VAT',
        r'BTW\s+bedrag',
    ]), re.IGNORECASE), 5),
    # rate-labeled VAT lines: "TVA 19%", "IVA 22%", "MwSt. 19%", "VAT @ 20%"
    (re.compile(
        r'(?<![\w-])(?:T\.?V\.?A\.?|VAT|IVA|MwSt\.?|USt\.?|BTW)\s*@?\s*\(?\d{1,2}(?:[.,]\d{1,2})?\s*%',
        re.IGNORECASE), 4),
    (re.compile(_kw([r'T\.?V\.?A\.?', r'\bVAT\b', r'\bIVA\b', r'MwSt\.?', r'\bBTW\b']),
                re.IGNORECASE), 2),
]


# ---------------------------------------------------------------------------
# Candidate collection and resolution
# ---------------------------------------------------------------------------

class _Candidate:
    __slots__ = ("value", "weight", "line_idx", "has_decimals")

    def __init__(self, value: float, weight: int, line_idx: int,
                 has_decimals: bool = False):
        self.value = value
        self.weight = weight
        self.line_idx = line_idx
        self.has_decimals = has_decimals

    def __repr__(self):
        return f"Cand({self.value}, w={self.weight}, ln={self.line_idx})"


def _collect(lines: List[str], specs) -> List[_Candidate]:
    """Scan lines for keyword matches; the amount is the rightmost value
    after the keyword on the same line, else the first value on the next line."""
    found: List[_Candidate] = []
    for i, line in enumerate(lines):
        if _line_excluded(line):
            continue
        for pat, weight in specs:
            m = pat.search(line)
            if not m:
                continue
            amounts = _amounts_in(line, m.end())
            if not amounts and i + 1 < len(lines) and not _line_excluded(lines[i + 1]):
                nxt = _amounts_in(lines[i + 1])
                amounts = nxt[:1]
            if amounts:
                value, token = amounts[-1]
                found.append(_Candidate(value, weight, i,
                                        has_decimals=bool(re.search(r'[.,]\d{1,2}$', token))))
            break   # only the most specific spec per line
    return found


def _dedupe_best(cands: List[_Candidate]) -> List[_Candidate]:
    best: Dict[float, _Candidate] = {}
    for c in cands:
        k = round(c.value, 2)
        if k not in best or c.weight > best[k].weight:
            best[k] = c
    return list(best.values())


def _resolve_amounts(lines: List[str]) -> Tuple[Optional[float], Optional[float],
                                                 Optional[float], bool]:
    """Return (subtotal, vat, total, total_reliable)."""
    n = max(len(lines), 1)
    totals    = _dedupe_best(_collect(lines, _TOTAL_SPECS))
    subtotals = _dedupe_best(_collect(lines, _SUBTOTAL_SPECS))
    vats      = _dedupe_best(_collect(lines, _VAT_SPECS))

    # Drop VAT candidates that are actually the rate: small round integers
    # written without decimals ("TVA 19" — a real amount prints as "19,00")
    vats = [c for c in vats
            if not (not c.has_decimals and c.value == int(c.value)
                    and 1 <= c.value <= 30 and c.weight < 5)]

    # 1) Arithmetic cross-validation: find s + v ≈ t (within 2% or 0.05)
    best_triple = None
    for t in totals:
        for s in subtotals:
            if s.value > t.value:
                continue
            for v in vats:
                if v.value >= s.value:
                    continue
                expected = s.value + v.value
                tol = max(0.05, t.value * 0.002)
                if abs(t.value - expected) <= tol:
                    score = t.weight + s.weight + v.weight
                    if best_triple is None or score > best_triple[0]:
                        best_triple = (score, s.value, v.value, t.value)
    if best_triple:
        _, s, v, t = best_triple
        return s, v, t, True

    # 2) Multi-rate VAT: several VAT lines whose sum fits subtotal + sum = total
    if totals and subtotals and len(vats) >= 2:
        vat_sum = round(sum(c.value for c in vats), 2)
        for t in totals:
            for s in subtotals:
                tol = max(0.05, t.value * 0.002)
                if abs(t.value - (s.value + vat_sum)) <= tol:
                    return s.value, vat_sum, t.value, True

    # 3) No consistent triple — pick best individual candidates
    def _pick(cands: List[_Candidate]) -> Optional[_Candidate]:
        if not cands:
            return None
        # specificity first, then position (totals live at the bottom), then size
        return max(cands, key=lambda c: (c.weight, c.line_idx / n, c.value))

    t_c = _pick(totals)
    s_c = _pick(subtotals)
    v_c = _pick(vats)

    total    = t_c.value if t_c else None
    subtotal = s_c.value if s_c else None
    vat      = v_c.value if v_c else None

    # A subtotal larger than the chosen total means a mismatch — distrust subtotal
    if total and subtotal and subtotal > total:
        if s_c and t_c and s_c.weight > t_c.weight:
            total = None
        else:
            subtotal = None
    if vat and subtotal and vat > subtotal * 0.6:
        vat = None
    if vat and total and vat > total * 0.5:
        vat = None

    reliable = bool(t_c and t_c.weight >= 4)
    return subtotal, vat, total, reliable


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

_MONTHS = {
    # ro
    'ianuarie': 1, 'ian': 1, 'februarie': 2, 'martie': 3, 'aprilie': 4,
    'iunie': 6, 'iun': 6, 'iulie': 7, 'iul': 7, 'septembrie': 9,
    'octombrie': 10, 'noiembrie': 11, 'noi': 11, 'decembrie': 12,
    # en
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
    'april': 4, 'apr': 4, 'may': 5, 'mai': 5, 'june': 6, 'jun': 6,
    'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12,
    # fr
    'janvier': 1, 'fevrier': 2, 'février': 2, 'mars': 3, 'avril': 4,
    'juin': 6, 'juillet': 7, 'aout': 8, 'août': 8, 'septembre': 9,
    'octobre': 10, 'novembre': 11, 'decembre': 12, 'décembre': 12,
    # de
    'januar': 1, 'februar': 2, 'marz': 3, 'märz': 3, 'juni': 6, 'juli': 7,
    'oktober': 10, 'dezember': 12,
    # it
    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5,
    'giugno': 6, 'luglio': 7, 'agosto': 8, 'settembre': 9,
    'ottobre': 10, 'novembre_it': 11, 'dicembre': 12,
    # es
    'enero': 1, 'febrero': 2, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}
_MONTH_NAMES = '|'.join(sorted(
    (k for k in _MONTHS if not k.endswith('_it')), key=len, reverse=True))

_DATE_YMD  = re.compile(r'\b(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})\b')
_DATE_DMY  = re.compile(r'\b(\d{1,2})[./\-](\d{1,2})[./\-](20\d{2})\b')
_DATE_DMY2 = re.compile(r'\b(\d{1,2})[./](\d{1,2})[./](\d{2})\b(?![./\-]\d)')
_DATE_TEXT = re.compile(
    r'\b(\d{1,2})\.?\s+(' + _MONTH_NAMES + r')\.?\s+(\d{4})\b', re.IGNORECASE)
_DATE_TEXT_EN = re.compile(
    r'\b(' + _MONTH_NAMES + r')\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b',
    re.IGNORECASE)


def _mk_date(y: int, m: int, d: int) -> Optional[date]:
    try:
        if 2000 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
            return date(y, m, d)
    except ValueError:
        pass
    return None


def _parse_date(text: str) -> Optional[date]:
    m = _DATE_YMD.search(text)
    if m:
        d = _mk_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            return d
    m = _DATE_DMY.search(text)
    if m:
        d = _mk_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if d:
            return d
    m = _DATE_TEXT.search(text)
    if m:
        month = _MONTHS.get(m.group(2).lower())
        if month:
            d = _mk_date(int(m.group(3)), month, int(m.group(1)))
            if d:
                return d
    m = _DATE_TEXT_EN.search(text)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month:
            d = _mk_date(int(m.group(3)), month, int(m.group(2)))
            if d:
                return d
    m = _DATE_DMY2.search(text)
    if m:
        d = _mk_date(2000 + int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if d:
            return d
    return None


# NOTE: [aăn] in Romanian keywords — some PDF text layers render "ă" as "n"
_ISSUE_DATE_KW = re.compile(_kw([
    r'dat[aăn]\s+emiterii', r'dat[aăn]\s+emitere', r'emis[aă]?\s+(?:la|in\s+data\s+de)',
    r'dat[aăn]\s+facturii', r'dat[aăn]\s+factur[aăn]', r'dat[aăn]\b',
    r'invoice\s+date', r'issue\s+date', r'date\s+of\s+issue', r'issued(?:\s+on)?', r'\bdate\b',
    r"date\s+de\s+facture", r"date\s+de\s+facturation", r"date\s+d.[ée]mission", r"[ée]mis\s+le",
    r'data\s+fattura', r'data\s+emissione', r'\bdel\b',
    r'rechnungsdatum', r'ausstellungsdatum', r'belegdatum', r'\bdatum\b',
    r'fecha\s+de?\s*factura', r'fecha\s+de\s+emisi[oó]n', r'\bfecha\b',
    r'data\s+wystawienia', r'data\s+faktury',
    r'factuurdatum',
    r'billing\s+period', r'perioada\s+de\s+facturare',
]), re.IGNORECASE)

_DUE_DATE_KW = re.compile(_kw([
    r'scaden\w*', r'dat[aăn]\s+scaden\w*',
    r'termen\s+(?:de\s+)?plat[aăn]*', r'\btermen\b', r'scadent\s+la',
    r'due\s+date', r'payment\s+due', r'pay\s+by', r'due\s+by',
    r"date\s+d.[ée]ch[ée]ance", r'[ée]ch[ée]ance', r'date\s+limite\s+de\s+paiement',
    r'data\s+scadenza', r'scadenza', r'pagamento\s+entro',
    r'f[aä]lligkeitsdatum', r'f[aä]llig\s+am', r'zahlungsziel', r'zahlbar\s+bis',
    r'fecha\s+de\s+vencimiento', r'vencimiento',
    r'termin\s+p[lł]atno[sś]ci',
    r'vervaldatum',
]), re.IGNORECASE)


def _extract_date(lines: List[str], kw: re.Pattern,
                  skip_kw: Optional[re.Pattern] = None) -> Optional[date]:
    for i, line in enumerate(lines):
        if skip_kw is not None and skip_kw.search(line):
            continue   # e.g. "Due Date" also contains the generic "date"
        m = kw.search(line)
        if not m:
            continue
        d = _parse_date(line[m.end():m.end() + 60])
        if d:
            return d
        # value sometimes sits on the following line (column layouts)
        if i + 1 < len(lines):
            d = _parse_date(lines[i + 1][:60])
            if d:
                return d
    return None


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

_CURRENCY_CODES = r'RON|LEI|EUR|USD|GBP|CHF|PLN|CZK|HUF|SEK|NOK|DKK|CAD|JPY|RUB'
_CURRENCY_TOKEN = re.compile(r'(?<![A-Z])(' + _CURRENCY_CODES + r')(?![A-Z])', re.IGNORECASE)
_SYMBOLS = {'€': 'EUR', '\xa3': 'GBP', '$': 'USD', '¥': 'JPY', 'zł': 'PLN'}


def _normalize_currency(raw: str) -> str:
    raw = raw.upper()
    return 'RON' if raw == 'LEI' else raw


def _extract_currency(lines: List[str], total_line_idx: Optional[int]) -> str:
    # 1) currency mentioned on/near the total line wins
    if total_line_idx is not None:
        for j in (total_line_idx, total_line_idx + 1, total_line_idx - 1):
            if 0 <= j < len(lines):
                m = _CURRENCY_TOKEN.search(lines[j])
                if m:
                    return _normalize_currency(m.group(1))
                for sym, code in _SYMBOLS.items():
                    if sym in lines[j]:
                        return code
    # 2) most frequent code in the document
    counts: Dict[str, int] = {}
    for line in lines:
        if _line_excluded(line):
            continue
        for m in _CURRENCY_TOKEN.finditer(line):
            code = _normalize_currency(m.group(1))
            counts[code] = counts.get(code, 0) + 1
    if counts:
        return max(counts.items(), key=lambda kv: kv[1])[0]
    # 3) symbols anywhere, then default
    text = "\n".join(lines)
    for sym, code in _SYMBOLS.items():
        if sym in text:
            return code
    return 'RON'


# ---------------------------------------------------------------------------
# Other fields
# ---------------------------------------------------------------------------

def _extract_supplier_name(lines: List[str]) -> str:
    header = lines[:max(6, int(len(lines) * 0.4))]
    text = "\n".join(header)

    patterns = [
        r'(?:Furnizor|Emitent|V[aâ]nz[aă]tor|Prestator(?:\s+de\s+servicii)?|Seller|Supplier'
        r'|Fournisseur|Fornitore|Lieferant|Proveedor|Sprzedawca)\s*[:\-]?\s*([^\n\r]{4,60})',
        r'(S\.C\.\s*[A-Z][^\n\r]{3,50}(?:S\.R\.L\.|S\.A\.|R\.A\.|SRL|SA))',
        r'([A-Z][\w\s.&\-]{2,50}\b(?:SRL|S\.R\.L\.|SA|S\.A\.|GmbH|AG|Ltd\.?|LLC|Inc\.?'
        r'|S\.p\.A\.|S\.r\.l\.|SAS|SARL|B\.V\.|Sp\.\s*z\s*o\.o\.))(?:\s|$|,)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE if pat is patterns[0] else 0)
        if m:
            val = m.group(1).strip().rstrip(',;.:')
            if re.search(r'capital|registr|fiscal|cont\s|iban|cif|cui|client|cump[aă]r[aă]tor|buyer',
                         val, re.IGNORECASE):
                continue
            if len(val) >= 3:
                return val

    # fallback: first header line that looks like a name, not a doc title
    for line in header:
        s = line.strip()
        if (3 <= len(s) <= 60 and re.search(r'[A-Za-z]{3}', s)
                and not re.match(r'(?:factur[aă]|invoice|facture|fattura|rechnung|faktura)',
                                 s, re.IGNORECASE)
                and not _line_excluded(s)
                and not re.search(r'\d{4}', s)):
            return s.rstrip(',;.:')
    return ""


def _extract_cui(text: str) -> str:
    m = re.search(
        r'(?:CUI|CIF|C\.U\.I\.|C\.I\.F\.)\s*[:\-]?\s*(RO\s*)?(\d{6,10})',
        text, re.IGNORECASE,
    )
    if m:
        prefix = "RO" if m.group(1) else ""
        return prefix + m.group(2).replace(" ", "")
    m = re.search(r'\b(RO\d{6,10})\b(?!\d)', text)
    if m and not re.search(r'\bRO\d{2}[A-Z]{4}', m.group(1)):
        return m.group(1)
    return ""


def _extract_iban(text: str) -> str:
    m = re.search(r'\b([A-Z]{2}\d{2}[A-Z0-9]{12,28})\b', text)
    return m.group(1).upper() if m else ""


_INVNO_KW = re.compile(
    r'(?:Factur[aă]\s+(?:fiscal[aă]\s+)?(?:nr|num[aă]r)\.?|Nr\.?\s+factur[aă]'
    r'|Seri[ae]\s+\w{1,6}\s*,?\s*(?:nr|num[aă]r)\.?'
    r'|Invoice\s*(?:no|number|#)\.?|Facture\s+(?:n[o°]|num[ée]ro)\.?'
    r'|Fattura\s+(?:n|nr|numero)\.?[°o]?|Rechnung(?:s-?\s?(?:nr|nummer))?\.?'
    r'|Factura\s+(?:n[o°]|n[uú]m)\.?|Faktura\s+(?:nr|VAT)\.?'
    r'|Factuurnummer)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/ ]{1,24})',
    re.IGNORECASE,
)


def _extract_invoice_number(lines: List[str]) -> str:
    text = "\n".join(lines)
    m = _INVNO_KW.search(text)
    if m:
        val = m.group(1).strip().rstrip('-/ ')
        # cut anything that drifts into the next label
        val = re.split(r'\s{2,}', val)[0].strip()
        if val and not _parse_date(val):
            return val
    # generic fallbacks, skipping dates, CUI and IBAN-looking strings
    for pat in [
        r'\b((?:FCT|FAC|INV|FF|FV)[A-Z0-9\-]{2,15})\b',
        r'\b([A-Z]{2,4}[-/]?\d{3,8})\b',
    ]:
        for m in re.finditer(pat, text):
            val = m.group(1)
            line_start = text.rfind("\n", 0, m.start()) + 1
            context = text[line_start:m.start()]
            if re.search(r'cui|cif|iban|swift|cont|cod', context, re.IGNORECASE):
                continue
            if _parse_date(val) or re.match(r'^RO\d+$', val):
                continue
            return val
    return ""


_VAT_RATE_RE = re.compile(
    r'(?:cot[aă]\s+TVA|T\.?V\.?A\.?|VAT|IVA|MwSt\.?|USt\.?|BTW|tax\s+rate)'
    r'\s*@?\s*\(?\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*%', re.IGNORECASE)


def _extract_vat_rate(text: str) -> float:
    m = _VAT_RATE_RE.search(text)
    if m:
        try:
            rate = float(m.group(1).replace(',', '.'))
            if 0 < rate <= 30:
                return rate
        except ValueError:
            pass
    return 19.0


# ---------------------------------------------------------------------------
# Line items (table-driven)
# ---------------------------------------------------------------------------

_COL_PATTERNS = {
    "description": [r'denumire', r'descriere', r'produs', r'serviciu',
                    r'specifica', r'articol', r'description', r'désignation',
                    r'designation', r'descrizione', r'bezeichnung', r'nazwa'],
    "quantity":   [r'cantitate', r'\bcant\b', r'\bbuc\b', r'\bqty\b',
                   r'quantity', r'quantité', r'quantita', r'menge', r'ilo[sś][cć]',
                   r'\bu\.?m\.?\b'],
    "unit_price": [r'pre[tţț]\s*unitar', r'unit\s*price', r'prix\s*unitaire',
                   r'prezzo\s*unit', r'einzelpreis', r'cena', r'\bp\.?u\.?\b', r'pre[tţț]'],
    "total":      [r'valoare', r'\btotal\b', r'amount', r'montant',
                   r'importo', r'betrag', r'warto[sś][cć]', r'sum[aă]'],
}


def _map_table_columns(header: List) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    cells = [str(c or "").lower() for c in header]
    for key, pats in _COL_PATTERNS.items():
        for idx, cell in enumerate(cells):
            if any(re.search(p, cell) for p in pats):
                mapping[key] = idx  # for "total", last match wins (rightmost col)
                if key != "total":
                    break
    return mapping


def _cell_amount(row: List, idx: Optional[int]) -> Optional[float]:
    if idx is None or idx < 0 or idx >= len(row) or row[idx] is None:
        return None
    cleaned = re.sub(r'[^\d.,\s]', '', str(row[idx])).strip()
    return _parse_amount(cleaned) if cleaned else None


def _parse_table_row(row: List, colmap: Optional[Dict[str, int]] = None) -> Optional[Dict[str, Any]]:
    if not row or len(row) < 3:
        return None

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
            pass

    try:
        numeric_vals = []
        for cell in reversed(row):
            if cell is None:
                continue
            v = _cell_amount([cell], 0)
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
    lines = [ln.strip() for ln in raw_text.splitlines()]

    def _track(val, name: str):
        if not val:
            errors.append(f"Could not extract: {name}")
        return val

    supplier_name  = _track(_extract_supplier_name(lines), "supplier_name")
    supplier_cui   = _track(_extract_cui(raw_text), "supplier_cui")
    supplier_iban  = _extract_iban(raw_text)
    invoice_number = _track(_extract_invoice_number(lines), "invoice_number")
    vat_rate       = _extract_vat_rate(raw_text)

    issue_date = _track(_extract_date(lines, _ISSUE_DATE_KW, skip_kw=_DUE_DATE_KW),
                        "issue_date")
    due_date   = _extract_date(lines, _DUE_DATE_KW)

    subtotal, vat_amount, total, total_reliable = _resolve_amounts(lines)

    # Currency: prefer the total's line context
    total_line_idx = None
    if total is not None:
        for i, line in enumerate(lines):
            if any(abs(v - total) < 0.005 for v, _ in _amounts_in(line)):
                total_line_idx = i
    currency = _extract_currency(lines, total_line_idx)

    if total and not total_reliable:
        errors.append("total: low-confidence match — verify manually")
    if not total:
        errors.append("Could not extract: total")

    # Derive missing values arithmetically
    if total and subtotal and not vat_amount:
        derived = round(total - subtotal, 2)
        if 0 < derived <= subtotal * 0.6:
            vat_amount = derived
    if total and vat_amount and not subtotal:
        subtotal = round(total - vat_amount, 2)
    if subtotal and vat_rate and not total:
        total = round(subtotal * (1 + vat_rate / 100), 2)
        if vat_amount is None:
            vat_amount = round(total - subtotal, 2)

    # Final consistency flag
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

    # Confidence: fraction of core fields extracted (iban/due_date excluded —
    # legitimately absent on many invoices), small penalty for fallback totals.
    core_fields = [supplier_name, supplier_cui, invoice_number,
                   issue_date, subtotal, vat_amount, total]
    fields_extracted = sum(1 for f in core_fields if f)
    confidence = fields_extracted / len(core_fields)
    if total and not total_reliable:
        confidence -= 0.1
    confidence = round(max(confidence, 0.0), 2)

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
