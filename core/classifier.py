import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data.models import Invoice


def _norm(s: str) -> str:
    """Lowercase and strip accents so 'Inglés'/'Telefónica' match ASCII brands."""
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()

# Generic, multilingual keywords matched against the whole document text
# (supplier name + line items + raw text). Diacritic and common-mojibake
# variants are kept on purpose so mis-decoded PDFs still match.
_KEYWORDS = {
    "Utilities": [
        "curent", "gaz", "apa", "apă", "energie", "electric", "electrica", "electrică",
        "termoficare", "canal", "salubritate", "internet", "telefon", "telefonie",
        "abonament telefon", "mobil", "fibra", "fibră", "broadband", "roaming",
        "strom", "wasser", "energia", "elettricità", "électricité", "eau",
        "telecom", "utilities", "utilitati", "utilităţi",
    ],
    "Software": [
        "license", "licence", "licenta", "licenţă", "lizenz", "licencia", "licença",
        "subscription", "abonament", "abonnement", "abbonamento", "saas", "software",
        "logiciel", "cloud", "hosting", "server", "domain", "domeniu", "api",
        "platform", "platforma", "platformă", "app", "aplicatie", "aplicaţie",
        "office 365", "google workspace", "antivirus", "it services", "servicii it",
    ],
    "Services": [
        "consultanta", "consultanţă", "consulting", "beratung", "consulenza",
        "consultoria", "conseil", "servicii", "service", "services", "serviciu",
        "prestation", "servizio", "servicio", "dienstleistung", "prestari", "prestări",
        "contabilitate", "accounting", "buchhaltung", "audit", "juridic", "legal",
        "avocat", "notariat", "mentenanta", "mentenanţă", "reparatie", "reparaţie",
        "intretinere", "întreţinere", "asigurare", "insurance", "medical", "clinica",
        "clinică", "spital", "abonament medical",
    ],
    "Products": [
        "produse", "products", "produkte", "produits", "prodotti", "productos",
        "marfuri", "mărfuri", "goods", "waren", "bunuri", "echipament", "equipment",
        "hardware", "materiale", "materie prima", "materie primă", "componente",
        "piese", "spare parts", "merchandise", "textil", "tessile", "alimente",
        "bauturi", "băuturi",
    ],
    "Transport": [
        "transport", "transporte", "trasporto", "curierat", "courier", "kurier",
        "livrare", "delivery", "livraison", "lieferung", "versand", "shipping",
        "expeditie", "expediţie", "spedizione", "frachtkosten", "freight",
        "posta romana", "poşta română",
    ],
    "Marketing": [
        "publicitate", "publicité", "pubblicità", "publicidad", "werbung", "reclama",
        "reclamă", "marketing", "advertising", "ads", "campanie", "campaign",
        "promovare", "promotion", "seo", "sem", "social media", "design grafic",
        "branding",
    ],
    "Office": [
        "birotica", "birotică", "papetarie", "papetărie", "papier", "papelería",
        "cancelleria", "stationery", "büromaterial", "consumabile", "rechizite",
        "mobilier", "furniture", "birou", "cartus", "cartuş", "cartridge", "toner",
        "hartie", "hârtie", "plic", "imprimanta", "imprimantă", "printer",
    ],
}

# Well-known vendor brands matched against the SUPPLIER NAME only (high weight).
# Most invoices carry no product/service text, so the supplier is the real signal.
_VENDORS = {
    "Software": [
        "microsoft", "adobe", "atlassian", "github", "gitlab", "figma", "slack",
        "notion", "vercel", "twilio", "zendesk", "hubspot", "salesforce", "sap",
        "oracle", "ibm", "datev", "lexware", "personio", "cegid", "teamsystem",
        "dassault", "bitdefender", "kaspersky", "norton", "mcafee", "eset", "avast",
        "intuit", "quickbooks", "sage", "shopify", "cloudflare", "stripe",
        "amazon web services", "aws", "ovhcloud", "ovh", "hetzner", "digitalocean",
        "vmware", "autodesk", "jetbrains", "dropbox", "zoom", "asana", "jira",
        "confluence", "openai", "anthropic", "doctolib", "haufe", "google cloud",
    ],
    "Utilities": [
        "deutsche telekom", "telekom", "telefonica", "orange",
        "vodafone", "digi communications", "digi", "rcs", "rds", "electrica",
        "enel", "romgaz", "e.on", "eon", "engie", "distrigaz", "delgaz",
        "hidroelectrica", "cez", "edf", "endesa", "iberdrola", "telecom italia",
        "movistar", "t-mobile", "verizon", "at&t",
    ],
    "Transport": [
        "fan courier", "fancourier", "cargus", "dhl", "dpd", "gls", "ups", "fedex",
        "tnt", "posta romana", "sameday", "blablacar", "uber", "bolt",
    ],
    "Products": [
        "rewe", "kaufland", "mega image", "dedeman", "decathlon", "el corte ingles",
        "carrefour", "lidl", "auchan", "ikea", "leroy merlin", "emag", "altex",
        "flanco", "siemens", "bosch", "samsung", "dell", "lenovo", "aqua carpatica",
        "coca cola", "pepsi", "manifattura", "industrial", "profi", "penny", "metro",
    ],
    "Office": [
        "xerox", "olivetti", "staples", "canon", "brother", "epson", "ricoh",
        "konica", "office depot", "faber castell",
    ],
    "Services": [
        "provident", "medlife", "regina maria", "sanador", "kpmg", "deloitte",
        "pwc", "mazars", "allianz", "generali", "raiffeisen", "revolut",
    ],
    "Marketing": [
        "mailchimp", "canva", "semrush", "ahrefs", "hootsuite", "sendgrid",
        "klaviyo", "google ads", "meta platforms",
    ],
}


def _compile(groups: dict) -> dict:
    out = {}
    for cat, terms in groups.items():
        # normalize terms (accent-fold) and put longest first so multi-word
        # brands win the alternation
        parts = sorted((re.escape(_norm(t)) for t in terms), key=len, reverse=True)
        out[cat] = re.compile(r"\b(?:" + "|".join(parts) + r")\b")
    return out


_KEYWORD_RE = _compile(_KEYWORDS)
_VENDOR_RE = _compile(_VENDORS)

_VENDOR_WEIGHT = 50


def classify_invoice(invoice: "Invoice", raw_text: str = "") -> str:
    """Return the best-matching category for an invoice.

    A known vendor brand in the supplier name dominates (weight 10); otherwise
    generic keywords found anywhere in the supplier, line items or raw text
    decide. Falls back to "Other" when nothing matches.
    """
    supplier = _norm(invoice.supplier_name)
    haystack = " ".join([
        supplier,
        " ".join(_norm(li.description) for li in invoice.line_items),
        _norm(raw_text),
    ])

    scores: dict[str, int] = {}
    for cat, rx in _VENDOR_RE.items():
        hits = len(rx.findall(supplier))
        if hits:
            scores[cat] = scores.get(cat, 0) + hits * _VENDOR_WEIGHT
    for cat, rx in _KEYWORD_RE.items():
        hits = len(rx.findall(haystack))
        if hits:
            scores[cat] = scores.get(cat, 0) + hits

    if scores:
        return max(scores, key=lambda c: scores[c])
    return "Other"
