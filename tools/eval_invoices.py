"""
Evaluation harness for the invoice parser.

Runs the existing extract_invoice() pipeline on a folder of test PDFs and
compares against a manifest file. Prints per-field accuracy and a per-file
report so we can see which invoices the parser gets wrong and why.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

# allow running from repo root without installing the package
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from core.extractor import extract_invoice  # noqa: E402


MANIFEST_PATH = Path(r"C:\Users\ianac\Downloads\analyzen_debug_invoices\invoices_debug\_MANIFEST.txt")
INVOICE_DIR   = MANIFEST_PATH.parent


def parse_manifest(path: Path) -> dict[str, dict]:
    """Map filename -> {lang, currency, total, issue_date}."""
    expected: dict[str, dict] = {}
    line_re = re.compile(
        r"^(?P<name>\S+\.pdf)\s*\|\s*(?P<lang>\S+)\s*\|\s*"
        r"(?P<cur>[A-Z]{3})\s+(?P<amount>[\d,]+(?:\.\d+)?)\s*\|\s*"
        r"(?P<date>\d{4}-\d{2}-\d{2})"
    )
    for line in path.read_text(encoding="utf-8").splitlines():
        m = line_re.match(line)
        if not m:
            continue
        expected[m.group("name")] = {
            "lang":   m.group("lang"),
            "currency": m.group("cur"),
            "total":  float(m.group("amount").replace(",", "")),
            "issue_date": date.fromisoformat(m.group("date")),
        }
    return expected


def amounts_close(a: Optional[float], b: Optional[float], rel: float = 0.01, abs_tol: float = 0.05) -> bool:
    if a is None or b is None:
        return a is b
    return abs(a - b) <= max(abs_tol, abs(b) * rel)


def fmt(v) -> str:
    if v is None or v == "":
        return "<empty>"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v)


def evaluate(expected: dict, file_paths: list[Path]) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    stats = {
        "files":        0,
        "total_ok":     0,
        "currency_ok":  0,
        "date_ok":      0,
        "subtotal_ok":  0,
        "vat_ok":       0,
        "supplier_ok":  0,
        "invno_ok":     0,
        "no_errors":    0,
    }

    for fp in sorted(file_paths):
        name = fp.name
        exp = expected.get(name)
        if not exp:
            continue
        inv = extract_invoice(str(fp))
        stats["files"] += 1

        # 1. total
        tot_ok = amounts_close(inv.total, exp["total"])
        if tot_ok:
            stats["total_ok"] += 1

        # 2. currency
        cur_ok = (inv.currency or "").upper() == exp["currency"]
        if cur_ok:
            stats["currency_ok"] += 1

        # 3. issue date
        d_ok = inv.issue_date == exp["issue_date"]
        if d_ok:
            stats["date_ok"] += 1

        # 4. subtotal + vat are not in manifest, but we can sanity-check arithmetic
        s_ok = inv.subtotal is not None and 0 < inv.subtotal < inv.total * 1.5 if inv.total else False
        v_ok = inv.vat_amount is not None and 0 <= inv.vat_amount <= inv.total if inv.total else False
        if s_ok:
            stats["subtotal_ok"] += 1
        if v_ok:
            stats["vat_ok"] += 1

        # 5. supplier / invoice number (we just check non-empty)
        sup_ok = bool(inv.supplier_name)
        ino_ok = bool(inv.invoice_number)
        if sup_ok:
            stats["supplier_ok"] += 1
        if ino_ok:
            stats["invno_ok"] += 1

        err_free = not inv.parse_errors
        if err_free:
            stats["no_errors"] += 1

        rows.append({
            "name":     name,
            "lang":     exp["lang"],
            "exp_total": exp["total"],
            "got_total": inv.total,
            "tot_ok":   tot_ok,
            "exp_cur":  exp["currency"],
            "got_cur":  inv.currency,
            "cur_ok":   cur_ok,
            "exp_date": exp["issue_date"],
            "got_date": inv.issue_date,
            "date_ok":  d_ok,
            "subtotal": inv.subtotal,
            "vat":      inv.vat_amount,
            "vat_rate": inv.vat_rate,
            "supplier": inv.supplier_name,
            "inv_no":   inv.invoice_number,
            "conf":     inv.confidence_score,
            "errors":   inv.parse_errors,
        })

    return rows, stats


def main() -> int:
    expected = parse_manifest(MANIFEST_PATH)
    files = sorted(p for p in INVOICE_DIR.glob("*.pdf"))
    print(f"Manifest: {len(expected)} invoices, folder: {len(files)} PDFs\n")

    rows, stats = evaluate(expected, files)
    n = stats["files"] or 1

    print("=" * 100)
    print(f"ACCURACY  (n={stats['files']})")
    print("=" * 100)
    print(f"  total correct      : {stats['total_ok']:>3} / {stats['files']}  ({100*stats['total_ok']/n:.0f}%)")
    print(f"  currency correct   : {stats['currency_ok']:>3} / {stats['files']}  ({100*stats['currency_ok']/n:.0f}%)")
    print(f"  issue date correct : {stats['date_ok']:>3} / {stats['files']}  ({100*stats['date_ok']/n:.0f}%)")
    print(f"  subtotal > 0       : {stats['subtotal_ok']:>3} / {stats['files']}  ({100*stats['subtotal_ok']/n:.0f}%)")
    print(f"  vat_amount > 0     : {stats['vat_ok']:>3} / {stats['files']}  ({100*stats['vat_ok']/n:.0f}%)")
    print(f"  supplier non-empty : {stats['supplier_ok']:>3} / {stats['files']}  ({100*stats['supplier_ok']/n:.0f}%)")
    print(f"  invoice# non-empty : {stats['invno_ok']:>3} / {stats['files']}  ({100*stats['invno_ok']/n:.0f}%)")
    print(f"  no parse errors    : {stats['no_errors']:>3} / {stats['files']}  ({100*stats['no_errors']/n:.0f}%)")

    # Per-language breakdown
    print()
    print("=" * 100)
    print("PER-LANGUAGE TOTAL ACCURACY")
    print("=" * 100)
    by_lang: dict[str, list[dict]] = {}
    for r in rows:
        by_lang.setdefault(r["lang"], []).append(r)
    for lang, items in sorted(by_lang.items()):
        tot_ok = sum(1 for r in items if r["tot_ok"])
        cur_ok = sum(1 for r in items if r["cur_ok"])
        d_ok   = sum(1 for r in items if r["date_ok"])
        n_lang = len(items)
        print(f"  {lang}  total: {tot_ok}/{n_lang}   currency: {cur_ok}/{n_lang}   date: {d_ok}/{n_lang}")

    # Failures detail
    print()
    print("=" * 100)
    print("FAILURES (total mismatch)")
    print("=" * 100)
    for r in rows:
        if r["tot_ok"]:
            continue
        print(f"  {r['name']}  [{r['lang']}]")
        print(f"     exp total: {fmt(r['exp_total'])} {r['exp_cur']}    got: {fmt(r['got_total'])} {r['got_cur']}")
        print(f"     subtotal={fmt(r['subtotal'])}  vat={fmt(r['vat'])} (rate {fmt(r['vat_rate'])})  conf={r['conf']:.2f}")
        if r["errors"]:
            print(f"     errors: {' | '.join(r['errors'])}")

    print()
    print("=" * 100)
    print("FAILURES (currency mismatch but total OK)")
    print("=" * 100)
    for r in rows:
        if not r["tot_ok"] or r["cur_ok"]:
            continue
        print(f"  {r['name']}  exp {r['exp_cur']}  got {r['got_cur']}  total={fmt(r['got_total'])}")

    print()
    print("=" * 100)
    print("FAILURES (date mismatch but total+cur OK)")
    print("=" * 100)
    for r in rows:
        if not r["tot_ok"] or not r["cur_ok"] or r["date_ok"]:
            continue
        print(f"  {r['name']}  exp {r['exp_date']}  got {r['got_date']}  total={fmt(r['got_total'])} {r['got_cur']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
