"""Parser regression tests: run with  python -m tests.test_parser"""
from datetime import date

from core.parser import parse_fields

_RO_UTILITY = """\
ELECTRICA FURNIZARE S.A.
Capital social: 18.000.000 EUR
CUI: RO28909028   Nr. inmatriculare J40/8974/2011
IBAN: RO98BRDE450SV09945894500
Factura fiscala nr. EFS-2026-001234
Data emiterii: 15.05.2026
Scadenta: 14.06.2026
Client: POPESCU ION
Index vechi: 45230  Index nou: 45810
Energie electrica consumata     580 kWh
Valoare fara TVA                            290,50 lei
Cota TVA 19%
Valoare TVA                                  55,20 lei
TOTAL DE PLATA                              345,70 lei
"""

_EN_INVOICE = """\
ACME SOFTWARE Ltd
123 Main Street, London
Invoice No: INV-2026-0042
Invoice date: March 3, 2026
Due date: April 2, 2026
Item                    Qty    Unit     Amount
Consulting services      10    120.00   1,200.00
Subtotal                                1,200.00
VAT @ 20%                                 240.00
Total amount due                    GBP 1,440.00
"""

_DE_INVOICE = """\
MUSTERMANN GmbH
Stammkapital: 25.000 EUR
USt-IdNr: DE123456789
Rechnungsnummer: RE-7781
Rechnungsdatum: 12.04.2026
Faelligkeitsdatum: 12.05.2026
Beratungsleistungen           500,00 EUR
Nettobetrag                   500,00 EUR
MwSt. 19%                      95,00 EUR
Gesamtbetrag                  595,00 EUR
"""

_FR_INVOICE = """\
DUPONT SARL
SIRET: 123 456 789 00012
Facture no FA-2026-118
Date: 20/02/2026
Date d'echeance: 22/03/2026
Prestation de conseil          1 000,00
Total HT                       1 000,00 EUR
TVA 20%                          200,00 EUR
Total TTC                      1 200,00 EUR
"""

_IT_INVOICE = """\
ROSSI S.r.l.
P.IVA: IT01234567890
Fattura n. 55/2026
Data fattura: 05.01.2026
Scadenza: 04.02.2026
Imponibile                     2.000,00
IVA 22%                          440,00
Totale fattura            EUR  2.440,00
"""

_NO_DATE = """\
Firma Test SRL
Factura nr. 77
Total de plata 100,00 lei
"""


def _check(name, result, **expected):
    failed = []
    for key, want in expected.items():
        got = result[key]
        if isinstance(want, float):
            ok = abs((got or 0) - want) < 0.01
        else:
            ok = got == want
        if not ok:
            failed.append(f"  {key}: expected {want!r}, got {got!r}")
    status = "OK  " if not failed else "FAIL"
    print(f"{status} {name}")
    for f in failed:
        print(f)
    return not failed


def main():
    ok = True
    r = parse_fields(_RO_UTILITY)
    ok &= _check("RO utility (capital social trap)", r,
                 total=345.70, subtotal=290.50, vat_amount=55.20,
                 vat_rate=19.0, currency="RON",
                 issue_date=date(2026, 5, 15), due_date=date(2026, 6, 14),
                 supplier_cui="RO28909028")

    r = parse_fields(_EN_INVOICE)
    ok &= _check("EN invoice", r,
                 total=1440.00, subtotal=1200.00, vat_amount=240.00,
                 vat_rate=20.0, currency="GBP", invoice_number="INV-2026-0042",
                 issue_date=date(2026, 3, 3), due_date=date(2026, 4, 2))

    r = parse_fields(_DE_INVOICE)
    ok &= _check("DE invoice (Stammkapital trap)", r,
                 total=595.00, subtotal=500.00, vat_amount=95.00,
                 vat_rate=19.0, currency="EUR", invoice_number="RE-7781",
                 issue_date=date(2026, 4, 12))

    r = parse_fields(_FR_INVOICE)
    ok &= _check("FR invoice", r,
                 total=1200.00, subtotal=1000.00, vat_amount=200.00,
                 vat_rate=20.0, currency="EUR",
                 issue_date=date(2026, 2, 20), due_date=date(2026, 3, 22))

    r = parse_fields(_IT_INVOICE)
    ok &= _check("IT invoice", r,
                 total=2440.00, subtotal=2000.00, vat_amount=440.00,
                 vat_rate=22.0, currency="EUR",
                 issue_date=date(2026, 1, 5), due_date=date(2026, 2, 4))

    r = parse_fields(_NO_DATE)
    ok &= _check("Minimal invoice, no dates", r,
                 total=100.00, currency="RON", issue_date=None)

    print("\nALL PASSED" if ok else "\nFAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
