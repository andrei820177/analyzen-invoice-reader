from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List


@dataclass
class LineItem:
    description: str = ""
    quantity: float = 0.0
    unit_price: float = 0.0
    total: float = 0.0


@dataclass
class Invoice:
    file_path: str = ""
    file_name: str = ""

    supplier_name: str = ""
    supplier_cui: str = ""
    supplier_iban: str = ""

    invoice_number: str = ""
    issue_date: Optional[date] = None
    due_date: Optional[date] = None

    subtotal: float = 0.0
    vat_amount: float = 0.0
    vat_rate: float = 0.0
    total: float = 0.0
    currency: str = "RON"

    category: str = "Other"
    line_items: List[LineItem] = field(default_factory=list)

    confidence_score: float = 0.0
    is_scanned: bool = False
    is_duplicate: bool = False
    is_outlier: bool = False
    is_near_due: bool = False
    parse_errors: List[str] = field(default_factory=list)

    processed_at: datetime = field(default_factory=datetime.now)
