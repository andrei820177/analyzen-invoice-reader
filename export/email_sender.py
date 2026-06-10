from __future__ import annotations

import json
import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from data.processor import InvoiceDataFrame

logger = logging.getLogger(__name__)


def _load_settings() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def send_report(
    idf: "InvoiceDataFrame",
    attachment_paths: List[str],
    subject: str = "Analyzen — Raport Facturi",
) -> None:
    """Send a report email with file attachments via SMTP."""
    settings = _load_settings()

    host = settings.get("smtp_host", "").strip()
    port = int(settings.get("smtp_port", 587))
    user = settings.get("smtp_user", "").strip()
    password = settings.get("smtp_password", "").strip()
    from_addr = settings.get("smtp_from", "").strip() or user
    to_addrs: List[str] = settings.get("smtp_to", [])

    if not host or not user or not to_addrs:
        raise ValueError("Email settings incomplete. Configure SMTP in Settings.")

    summary = idf.get_summary()
    body_html = f"""
<html><body style="font-family:sans-serif;color:#1a2332;">
<h2 style="color:#2f8f6b;">Analyzen — Raport Facturi</h2>
<table border="0" cellpadding="8" style="border-collapse:collapse;">
  <tr><td><b>Total facturi:</b></td><td>{summary['total_invoices']}</td></tr>
  <tr><td><b>Valoare totala:</b></td><td>{summary['total_value']:,.2f} RON</td></tr>
  <tr><td><b>TVA total:</b></td><td>{summary['total_vat']:,.2f} RON</td></tr>
  <tr><td><b>Semnalizate:</b></td><td>{summary['flagged_count']}</td></tr>
</table>
<p style="color:#6b7c8a;font-size:12px;">Raport generat de Analyzen Invoice Reader</p>
</body></html>
"""

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)

    msg.attach(MIMEText(body_html, "html", "utf-8"))

    for path in attachment_paths:
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(path))
        part["Content-Disposition"] = f'attachment; filename="{os.path.basename(path)}"'
        msg.attach(part)

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            if port != 465:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(user, password)
            smtp.sendmail(from_addr, to_addrs, msg.as_string())
        logger.info("Email sent to: %s", to_addrs)
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        raise
