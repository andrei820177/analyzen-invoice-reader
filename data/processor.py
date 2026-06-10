from __future__ import annotations

from datetime import date
from typing import List, Optional

import pandas as pd

from data.models import Invoice


_COLUMNS = [
    "file_path", "file_name", "supplier_name", "supplier_cui", "supplier_iban",
    "invoice_number", "issue_date", "due_date",
    "subtotal", "vat_amount", "vat_rate", "total", "currency",
    "category", "confidence_score",
    "is_scanned", "is_duplicate", "is_outlier", "is_near_due",
    "parse_errors", "processed_at",
]


def _invoice_to_row(inv: Invoice) -> dict:
    return {
        "file_path": inv.file_path,
        "file_name": inv.file_name,
        "supplier_name": inv.supplier_name,
        "supplier_cui": inv.supplier_cui,
        "supplier_iban": inv.supplier_iban,
        "invoice_number": inv.invoice_number,
        "issue_date": inv.issue_date,
        "due_date": inv.due_date,
        "subtotal": inv.subtotal,
        "vat_amount": inv.vat_amount,
        "vat_rate": inv.vat_rate,
        "total": inv.total,
        "currency": inv.currency,
        "category": inv.category,
        "confidence_score": inv.confidence_score,
        "is_scanned": inv.is_scanned,
        "is_duplicate": inv.is_duplicate,
        "is_outlier": inv.is_outlier,
        "is_near_due": inv.is_near_due,
        "parse_errors": "; ".join(inv.parse_errors),
        "processed_at": inv.processed_at,
    }


class InvoiceDataFrame:
    def __init__(self) -> None:
        self._df: pd.DataFrame = pd.DataFrame(columns=_COLUMNS)

    def add_invoice(self, inv: Invoice) -> None:
        row = _invoice_to_row(inv)
        new_row = pd.DataFrame([row])
        self._df = pd.concat([self._df, new_row], ignore_index=True)

    def add_invoices(self, invoices: List[Invoice]) -> None:
        rows = [_invoice_to_row(inv) for inv in invoices]
        new_rows = pd.DataFrame(rows)
        self._df = pd.concat([self._df, new_rows], ignore_index=True)

    def remove_invoice(self, file_path: str) -> None:
        self._df = self._df[self._df["file_path"] != file_path].reset_index(drop=True)

    def clear(self) -> None:
        self._df = pd.DataFrame(columns=_COLUMNS)

    def get_all(self) -> pd.DataFrame:
        return self._df.copy()

    def filter_by_date(self, start: date, end: date) -> pd.DataFrame:
        df = self._df
        mask = df["issue_date"].apply(
            lambda d: d is not None and start <= d <= end
        )
        return df[mask].copy()

    def filter_by_supplier(self, name: str) -> pd.DataFrame:
        mask = self._df["supplier_name"].str.contains(name, case=False, na=False)
        return self._df[mask].copy()

    def filter_by_category(self, category: str) -> pd.DataFrame:
        return self._df[self._df["category"] == category].copy()

    def filter_by_flags(
        self,
        duplicates: bool = False,
        outliers: bool = False,
        near_due: bool = False,
    ) -> pd.DataFrame:
        if not (duplicates or outliers or near_due):
            return self._df.copy()
        mask = pd.Series([False] * len(self._df), index=self._df.index)
        if duplicates:
            mask = mask | self._df["is_duplicate"]
        if outliers:
            mask = mask | self._df["is_outlier"]
        if near_due:
            mask = mask | self._df["is_near_due"]
        return self._df[mask].copy()

    def search(self, query: str) -> pd.DataFrame:
        q = query.lower()
        text_cols = ["file_name", "supplier_name", "supplier_cui", "invoice_number", "category"]
        mask = self._df[text_cols].apply(
            lambda col: col.str.contains(q, case=False, na=False)
        ).any(axis=1)
        return self._df[mask].copy()

    def get_summary(self) -> dict:
        df = self._df
        if df.empty:
            return {
                "total_invoices": 0,
                "total_value": 0.0,
                "total_vat": 0.0,
                "per_supplier": {},
                "per_category": {},
                "per_month": {},
                "flagged_count": 0,
            }

        per_supplier = (
            df.groupby("supplier_name")["total"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .to_dict()
        )

        per_category = df.groupby("category")["total"].sum().to_dict()

        def _month_key(d):
            try:
                if d is None or pd.isna(d):
                    return "N/A"
            except (TypeError, ValueError):
                pass
            try:
                return f"{d.year}-{d.month:02d}"
            except (AttributeError, TypeError, ValueError):
                return "N/A"

        df2 = df.copy()
        df2["month"] = df2["issue_date"].apply(_month_key)
        per_month = df2.groupby("month")["total"].sum().sort_index().to_dict()

        flagged = df["is_duplicate"] | df["is_outlier"] | df["is_near_due"]

        return {
            "total_invoices": len(df),
            "total_value": float(df["total"].sum()),
            "total_vat": float(df["vat_amount"].sum()),
            "per_supplier": per_supplier,
            "per_category": per_category,
            "per_month": per_month,
            "flagged_count": int(flagged.sum()),
        }

    def __len__(self) -> int:
        return len(self._df)
