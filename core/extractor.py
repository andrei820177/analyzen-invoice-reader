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


def extract_invoice(file_path: str) -> Invoice:
    """Extract a single invoice from a PDF file."""
    file_name = os.path.basename(file_path)
    inv = Invoice(file_path=file_path, file_name=file_name, processed_at=datetime.now())

    try:
        with pdfplumber.open(file_path) as pdf:
            if not pdf.pages:
                raise ValueError("PDF has no pages")

            # extract each page's text exactly once and reuse it
            raw_pages = [page.extract_text() for page in pdf.pages]
            if raw_pages[0] is None:
                raise ValueError("PDF appears to be encrypted or corrupted")
            page_texts = [t or "" for t in raw_pages]
            is_text = any(len(t.strip()) > 50 for t in page_texts)

            if is_text:
                raw_text = "\n".join(page_texts)
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

    inv.category = classify_invoice(inv, raw_text)
    return inv


# PDF parsing is CPU-bound and holds the GIL, so threads give no speedup; a
# process pool runs across cores. Process startup costs a bit, so only use it
# once a batch is large enough to pay off.
_PROCESS_POOL_MIN = 24


def _make_executor(max_workers: int, n_files: int):
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    if n_files >= _PROCESS_POOL_MIN and max_workers > 1:
        try:
            ctx = multiprocessing.get_context("spawn")
            return ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx), "process"
        except Exception as e:
            logger.warning("Process pool unavailable (%s); using threads", e)
    return ThreadPoolExecutor(max_workers=max_workers), "thread"


def extract_batch(
    file_paths: List[str],
    progress_callback: Optional[Callable[[int, int, Invoice], None]] = None,
    max_workers: Optional[int] = None,
) -> List[Invoice]:
    """Process multiple PDFs in parallel (process pool for large batches)."""
    if max_workers is None or max_workers <= 0:
        import multiprocessing
        max_workers = max(1, multiprocessing.cpu_count() - 1)

    invoices: List[Invoice] = [None] * len(file_paths)  # type: ignore
    total = len(file_paths)

    executor, kind = _make_executor(max_workers, total)
    logger.info("Extracting %d PDFs with %d %s workers", total, max_workers, kind)
    try:
        with executor:
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
    except Exception as e:
        # a broken process pool (rare) -> fall back to a single-process thread run
        logger.error("Batch executor failed (%s); retrying single-threaded", e)
        return _extract_batch_threaded(file_paths, progress_callback)

    return invoices


def _extract_batch_threaded(file_paths, progress_callback) -> List[Invoice]:
    invoices: List[Invoice] = [None] * len(file_paths)  # type: ignore
    total = len(file_paths)
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_idx = {executor.submit(extract_invoice, fp): i
                         for i, fp in enumerate(file_paths)}
        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                inv = future.result()
            except Exception as e:
                fp = file_paths[idx]
                inv = Invoice(file_path=fp, file_name=os.path.basename(fp),
                              parse_errors=[str(e)], processed_at=datetime.now())
            invoices[idx] = inv
            completed += 1
            if progress_callback:
                progress_callback(completed, total, inv)
    return invoices
