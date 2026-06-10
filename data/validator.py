import json
import os
from datetime import date, timedelta
from typing import List

from data.models import Invoice


def _load_settings() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_batch(invoices: List[Invoice]) -> List[Invoice]:
    """Run all validation checks on a batch of invoices in-place."""
    settings = _load_settings()
    _check_duplicates(invoices)
    _check_outliers(invoices, settings.get("outlier_std_dev_multiplier", 2.0))
    _check_near_due(invoices, settings.get("due_date_alert_days", 7))
    return invoices


def _check_duplicates(invoices: List[Invoice]) -> None:
    seen: dict = {}
    for inv in invoices:
        key = (inv.invoice_number.strip().lower(), inv.supplier_cui.strip().lower())
        if key[0] and key in seen:
            inv.is_duplicate = True
            seen[key].is_duplicate = True
        else:
            seen[key] = inv


def _check_outliers(invoices: List[Invoice], multiplier: float) -> None:
    totals = [inv.total for inv in invoices if inv.total > 0]
    if len(totals) < 3:
        return
    mean = sum(totals) / len(totals)
    variance = sum((t - mean) ** 2 for t in totals) / len(totals)
    std_dev = variance ** 0.5
    threshold = mean + multiplier * std_dev
    for inv in invoices:
        if inv.total > threshold:
            inv.is_outlier = True


def _check_near_due(invoices: List[Invoice], alert_days: int) -> None:
    today = date.today()
    cutoff = today + timedelta(days=alert_days)
    for inv in invoices:
        if inv.due_date and today <= inv.due_date <= cutoff:
            inv.is_near_due = True
