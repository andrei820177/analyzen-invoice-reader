"""
Regression tests for the five PDF parsing bugs fixed in the pipeline.

Run with:  python -m pytest tests/test_pdf_parsing.py -v
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from core.parser import (
    _extract_amount_after_keyword,
    _extract_iban,
    parse_fields,
)


# ---------------------------------------------------------------------------
# Bug 1 — extractor: false-positive ValueError for scanned PDFs
# The old guard raised ValueError when page 0 returned None from extract_text().
# That blocked the OCR path for every scanned invoice.
# ---------------------------------------------------------------------------

def test_extractor_no_false_encryption_guard():
    src = (pathlib.Path(__file__).parent.parent / "core" / "extractor.py").read_text()
    # The bad pattern was: extract_text() is None  →  raise ValueError
    assert 'extract_text() is None' not in src, (
        "False encryption guard must be removed from extractor.py"
    )


# ---------------------------------------------------------------------------
# Bug 2 — ocr: MedianFilter(size=1) was a no-op
# ---------------------------------------------------------------------------

def test_ocr_median_filter_size():
    src = (pathlib.Path(__file__).parent.parent / "core" / "ocr.py").read_text()
    assert "MedianFilter(size=3)" in src, "MedianFilter must use size=3"
    assert "MedianFilter(size=1)" not in src, "MedianFilter(size=1) no-op must be removed"


# ---------------------------------------------------------------------------
# Bug 3 — parser: keyword 'Total' matched inside 'Subtotal'
# Without \b the regex hit 'Total' at position 3 of 'Subtotal'.
# ---------------------------------------------------------------------------

def test_total_keyword_not_matched_inside_subtotal():
    # Only 'Subtotal:' present — should return None, not 800
    val = _extract_amount_after_keyword("Subtotal: 800.00", ["Total"])
    assert val is None, f"'Total' must not match inside 'Subtotal': got {val}"


def test_total_keyword_matches_standalone_total():
    val = _extract_amount_after_keyword("Subtotal: 800.00\nTotal: 952.00", ["Total"])
    assert val == 952.0, f"Expected 952.0, got {val}"


# ---------------------------------------------------------------------------
# Bug 4 — parser: confidence score capped at 0.56
# total_fields=9 was declared but only 5 fields were counted, so max was 5/9.
# After the fix all 9 fields are tracked and the score reflects reality.
# ---------------------------------------------------------------------------

# Use a text long enough that amounts are > 150 chars from the CUI/IBAN
# (the context-exclusion window) so subtotal and vat are not suppressed.
_FULL_INVOICE = (
    "Furnizor: ACME SRL\n"
    "CUI: RO12345678\n"
    "IBAN: RO49AAAA1B31007593840000\n"
    "Factura nr.: INV-2024-001\n"
    "Data emiterii: 01.02.2024\n"
    "Scadenta: 01.03.2024\n"
    "\n" * 5                      # padding to push amounts past the exclusion window
    + "Descriere servicii contabile si consultanta fiscala\n" * 4
    + "Subtotal: 800.00\n"
    "Valoare TVA: 152.00\n"
    "Total de plata: 952.00\n"
    "RON\n"
)


def test_confidence_exceeds_old_cap():
    fields = parse_fields(_FULL_INVOICE)
    assert fields["confidence_score"] > 0.56, (
        f"Confidence {fields['confidence_score']} still at old cap — tracking not fixed"
    )


def test_due_date_counted_in_confidence():
    # Invoice with due_date but without subtotal/vat: due_date should contribute.
    fields = parse_fields(
        "Factura nr.: INV-001\nData: 01.02.2024\nScadenta: 01.03.2024\nTotal: 100.00\n"
    )
    due_not_extracted = any("due_date" in e for e in fields["parse_errors"])
    assert not due_not_extracted, "due_date must be tracked in confidence score"


def test_supplier_iban_counted_in_confidence():
    fields = parse_fields(
        "Furnizor: ACME SRL\nIBAN: RO49AAAA1B31007593840000\n"
        "Factura nr.: INV-001\nData: 01.02.2024\nTotal: 100.00\n"
    )
    iban_not_extracted = any("supplier_iban" in e for e in fields["parse_errors"])
    assert not iban_not_extracted, "supplier_iban must be tracked in confidence score"


# ---------------------------------------------------------------------------
# Bug 5 — parser: IBAN regex accepted 22–26 chars instead of exactly 24
# ---------------------------------------------------------------------------

def test_iban_exact_24_chars_accepted():
    # RO(2) + 2 digits + 20 BBAN chars = 24 total
    result = _extract_iban("IBAN: RO49AAAA1B31007593840000")
    assert result == "RO49AAAA1B31007593840000", f"Valid IBAN not extracted: {result!r}"


def test_iban_23_chars_rejected():
    result = _extract_iban("IBAN: RO49AAAA1B3100759384000")  # 23 chars
    assert result == "", f"23-char IBAN must be rejected, got {result!r}"


def test_iban_25_chars_rejected():
    result = _extract_iban("IBAN: RO49AAAA1B310075938400001")  # 25 chars
    assert result == "", f"25-char IBAN must be rejected, got {result!r}"
