from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data.models import Invoice

_CATEGORIES = {
    "Utilities": [
        "curent", "gaz", "apa", "apă", "energie", "electric", "eon", "e.on",
        "electrica", "electrică", "delgaz", "engie", "distrigaz", "termoficare",
        "canal", "salubritate", "internet", "telefon", "telekom", "orange", "vodafone",
    ],
    "Software": [
        "license", "licenta", "licenţă", "subscription", "abonament", "saas",
        "software", "microsoft", "adobe", "atlassian", "github", "google workspace",
        "office 365", "antivirus",
    ],
    "Services": [
        "consultanta", "consultanţă", "servicii", "prestari", "prestări",
        "contabilitate", "audit", "juridic", "avocat", "notariat", "mentenanta",
        "mentenanţă", "reparatie", "reparaţie", "intretinere", "întreţinere",
    ],
    "Products": [
        "produse", "marfuri", "mărfuri", "bunuri", "echipament", "materiale",
        "materie prima", "materie primă", "componente", "piese",
    ],
    "Transport": [
        "transport", "curierat", "livrare", "expeditie", "expediţie",
        "dhl", "fancourier", "fan courier", "cargus", "urgent cargus",
        "gls", "dpd", "ups", "fedex", "posta romana",
    ],
    "Marketing": [
        "publicitate", "reclama", "reclamă", "marketing", "google ads",
        "meta", "facebook ads", "instagram", "tiktok", "seo", "campanie",
        "promovare", "print", "grafic", "design grafic",
    ],
    "Office": [
        "birotica", "birotică", "papetarie", "papetărie", "consumabile",
        "rechizite", "mobilier", "birou", "cartus", "cartuş", "toner",
        "hartie", "hârtie", "plic",
    ],
}


def classify_invoice(invoice: "Invoice") -> str:
    """Return the best-matching category for an invoice."""
    haystack = " ".join([
        invoice.supplier_name.lower(),
        " ".join(li.description.lower() for li in invoice.line_items),
    ])

    scores: dict[str, int] = {}
    for category, keywords in _CATEGORIES.items():
        count = sum(1 for kw in keywords if kw in haystack)
        if count:
            scores[category] = count

    if scores:
        return max(scores, key=lambda c: scores[c])
    return "Other"
