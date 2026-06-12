"""Open a new Outlook message with a report attached.

Tries the Outlook COM automation first (so the recipient, subject and body can
be pre-filled), and falls back to launching ``OUTLOOK.EXE /a <file>`` resolved
from the Windows "App Paths" registry entry. Returns True if Outlook was
opened, False otherwise (e.g. Outlook not installed).
"""

import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


def find_outlook_exe() -> str | None:
    if sys.platform != "win32":
        return None
    import winreg

    sub = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, sub) as key:
                path, _ = winreg.QueryValueEx(key, None)
                if path and os.path.isfile(path):
                    return path
        except OSError:
            continue
    return None


def is_available() -> bool:
    """True if we have any way to open Outlook on this machine."""
    if sys.platform != "win32":
        return False
    if find_outlook_exe():
        return True
    try:
        import win32com.client  # noqa: F401
        return True
    except Exception:
        return False


def open_with_attachment(attachment: str, to: str = "",
                         subject: str = "", body: str = "") -> bool:
    attachment = os.path.abspath(attachment)

    # 1) COM automation -- lets us pre-fill recipient / subject / body
    try:
        import win32com.client as win32

        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)          # 0 = olMailItem
        if to:
            mail.To = to
        if subject:
            mail.Subject = subject
        if body:
            mail.Body = body
        mail.Attachments.Add(attachment)
        mail.Display(False)                   # open compose window, non-modal
        return True
    except Exception as e:
        logger.info("Outlook COM unavailable (%s); trying outlook.exe /a", e)

    # 2) Fallback: launch outlook.exe with the file attached
    exe = find_outlook_exe()
    if exe:
        try:
            subprocess.Popen([exe, "/a", attachment])
            return True
        except Exception as e:
            logger.error("Failed to launch Outlook: %s", e)
    return False
