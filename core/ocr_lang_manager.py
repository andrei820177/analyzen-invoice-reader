"""
Manages Tesseract language pack (.traineddata) files at runtime.

Fast packs are downloaded from tesseract-ocr/tessdata_fast on GitHub.
They are ~5-10 MB each — much smaller than the full accuracy packs.
"""

import json
import logging
import os
import sys
import urllib.request
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

_TESSDATA_FAST_BASE = (
    "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{lang}.traineddata"
)

# Maps UI language code -> Tesseract pack name(s) needed
_LANG_PACKS: dict[str, List[str]] = {
    "ro": ["ron", "eng"],
    "en": ["eng"],
    "de": ["deu", "eng"],
    "fr": ["fra", "eng"],
    "it": ["ita", "eng"],
    "es": ["spa", "eng"],
    "pt": ["por", "eng"],
    "pl": ["pol", "eng"],
    "ru": ["rus", "eng"],
    "nl": ["nld", "eng"],
    "da": ["dan", "eng"],
}


def _get_tessdata_dir() -> str:
    """Return the tessdata directory to use — bundled path takes priority."""
    # 1. Bundled alongside the exe (PyInstaller / installed app)
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.join(os.path.dirname(__file__), "..")

    bundled = os.path.join(base, "tesseract", "tessdata")
    if os.path.isdir(bundled):
        return bundled

    # 2. Tesseract installed in common Windows paths
    for candidate in [
        r"C:\Program Files\Tesseract-OCR\tessdata",
        r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
    ]:
        if os.path.isdir(candidate):
            return candidate

    # 3. TESSDATA_PREFIX env variable
    env = os.environ.get("TESSDATA_PREFIX", "")
    if env and os.path.isdir(env):
        return env

    return bundled  # will be created on first download


def get_missing_packs(ui_lang: str) -> List[str]:
    """Return list of .traineddata pack names not yet present for a given UI language."""
    tessdata_dir = _get_tessdata_dir()
    needed = _LANG_PACKS.get(ui_lang, ["eng"])
    return [p for p in needed if not os.path.isfile(os.path.join(tessdata_dir, f"{p}.traineddata"))]


def is_lang_ready(ui_lang: str) -> bool:
    return len(get_missing_packs(ui_lang)) == 0


def download_pack(
    pack_name: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """Download a single .traineddata file. Returns True on success."""
    tessdata_dir = _get_tessdata_dir()
    os.makedirs(tessdata_dir, exist_ok=True)

    dest = os.path.join(tessdata_dir, f"{pack_name}.traineddata")
    url = _TESSDATA_FAST_BASE.format(lang=pack_name)

    logger.info("Downloading OCR pack: %s from %s", pack_name, url)

    try:
        def _reporthook(block_num: int, block_size: int, total_size: int) -> None:
            if progress_callback and total_size > 0:
                downloaded = min(block_num * block_size, total_size)
                progress_callback(downloaded, total_size)

        urllib.request.urlretrieve(url, dest, reporthook=_reporthook)
        logger.info("Downloaded: %s", dest)
        return True
    except Exception as e:
        logger.error("Failed to download %s: %s", pack_name, e)
        if os.path.isfile(dest):
            os.remove(dest)
        return False


def download_for_lang(
    ui_lang: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> Tuple[int, int]:
    """Download all missing packs for a UI language.

    progress_callback(pack_name, downloaded_bytes, total_bytes)

    Returns (success_count, total_needed).
    """
    missing = get_missing_packs(ui_lang)
    if not missing:
        return 0, 0

    success = 0
    for pack in missing:
        def _cb(dl: int, total: int, _pack=pack) -> None:
            if progress_callback:
                progress_callback(_pack, dl, total)

        if download_pack(pack, progress_callback=_cb):
            success += 1

    return success, len(missing)
