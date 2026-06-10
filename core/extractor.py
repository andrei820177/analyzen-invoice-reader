import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Callable, List, Optional

import pdfplumber

from core.classifier import classify_invoice
from core.parser import parse_fields
from data.models import Invoice, LineItem

logger = logging.getLogger(__name__)


def _is_text_pdf(pages) -> bool:
    """Return True if the PDF has extractable text on at least one page."""
    for page in pages:
        text = page.extract_text() or ""
        if len(text.strip()) > 50:
            return True
    return False


def extract_invoice(file_path: str) -> Invoice:
    """Extract a single invoice from a PDF file."""
    file_name = os.path.basename(file_path)
    inv = Invoice(file_path=file_path, file_name=file_name, processed_at=datetime.now())

    try:
        with pdfplumber.open(file_path) as pdf:
            is_text = _is_text_pdf(pdf.pages)

            if is_text:
                raw_text = "\n".join(
                    (page.extract_text() or "") for page in pdf.pages
                )
                tables = []
                for page in pdf.pages:
                    t = page.extract_tables()
                    if t:
                        tables.extend(t)
            else:
                inv.is_scanned = True
                from core.ocr import ocr_pdf
                raw_text = ocr_pdf(file_path)
                tables = []

    except Exception as e:
        logger.error("Failed to open %s: %s", file_path, e)
        inv.parse_errors.append(str(e))
        return inv

    if not raw_text.strip():
        inv.parse_errors.append("No text could be extracted")
        return inv

    fields = parse_fields(raw_text, tables)

    inv.supplier_name = fields["supplier_name"]
    inv.supplier_cui = fields["supplier_cui"]
    inv.supplier_iban = fields["supplier_iban"]
    inv.invoice_number = fields["invoice_number"]
    inv.issue_date = fields["issue_date"]
    inv.due_date = fields["due_date"]
    inv.subtotal = fields["subtotal"]
    inv.vat_amount = fields["vat_amount"]
    inv.vat_rate = fields["vat_rate"]
    inv.total = fields["total"]
    inv.currency = fields["currency"]
    inv.confidence_score = fields["confidence_score"]
    inv.parse_errors = fields["parse_errors"]

    inv.line_items = [
        LineItem(
            description=li["description"],
            quantity=li["quantity"],
            unit_price=li["unit_price"],
            total=li["total"],
        )
        for li in fields["line_items"]
    ]

    inv.category = classify_invoice(inv)
    return inv


def extract_batch(
    file_paths: List[str],
    progress_callback: Optional[Callable[[int, int, Invoice], None]] = None,
    max_workers: Optional[int] = None,
) -> List[Invoice]:
    """Process multiple PDFs in parallel using ThreadPoolExecutor."""
    if max_workers is None or max_workers <= 0:
        import multiprocessing
        max_workers = max(1, multiprocessing.cpu_count() - 1)

    invoices: List[Invoice] = [None] * len(file_paths)  # type: ignore
    total = len(file_paths)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(extract_invoice, fp): i
            for i, fp in enumerate(file_paths)
        }
        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                inv = future.result()
            except Exception as e:
                fp = file_paths[idx]
                logger.error("Unhandled error for %s: %s", fp, e)
                inv = Invoice(
                    file_path=fp,
                    file_name=os.path.basename(fp),
                    parse_errors=[str(e)],
                    processed_at=datetime.now(),
                )
            invoices[idx] = inv
            completed += 1
            if progress_callback:
                progress_callback(completed, total, inv)

    return invoices
