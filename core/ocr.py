import io
import json
import logging
import os
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def _get_tesseract_path() -> str:
    # 1. User-configured path in settings
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "settings.json"
    )
    try:
        with open(config_path, encoding="utf-8") as f:
            settings = json.load(f)
        custom = settings.get("tesseract_path", "").strip()
        if custom and os.path.isfile(custom):
            return custom
    except Exception:
        pass

    # 2. Bundled tesseract alongside the exe (installer layout)
    if getattr(sys, "frozen", False):
        bundled = os.path.join(os.path.dirname(sys.executable), "tesseract", "tesseract.exe")
    else:
        bundled = os.path.join(os.path.dirname(__file__), "..", "tesseract", "tesseract.exe")
    bundled = os.path.normpath(bundled)
    if os.path.isfile(bundled):
        return bundled

    # 3. Common Windows install locations
    for candidate in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]:
        if os.path.isfile(candidate):
            return candidate

    return "tesseract"  # fall back to PATH


def _get_tessdata_dir() -> Optional[str]:
    """Return TESSDATA_PREFIX to pass to pytesseract, or None to use default."""
    from core.ocr_lang_manager import _get_tessdata_dir as _mgr_dir
    d = _mgr_dir()
    return d if os.path.isdir(d) else None


def _preprocess_image(img):
    """Grayscale + contrast boost for better OCR accuracy."""
    from PIL import ImageFilter, ImageOps, ImageEnhance

    img = img.convert("L")  # grayscale
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    return img


# Tesseract language codes per UI language code
_LANG_TO_TESS = {
    "ro": "ron+eng",
    "en": "eng",
    "de": "deu+eng",
    "fr": "fra+eng",
    "it": "ita+eng",
    "es": "spa+eng",
    "pt": "por+eng",
    "pl": "pol+eng",
    "ru": "rus+eng",
    "nl": "nld+eng",
    "da": "dan+eng",
}


def _get_ui_language() -> str:
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "settings.json"
    )
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f).get("language", "ro")
    except Exception:
        return "ro"


def ocr_pdf(file_path: str, lang_override: Optional[str] = None) -> str:
    """Convert a scanned PDF to text via pytesseract.

    lang_override: Tesseract language string (e.g. 'deu+eng'). If None,
    auto-selects based on settings.json language.
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as e:
        logger.error("OCR dependencies missing: %s", e)
        return ""

    try:
        pytesseract.pytesseract.tesseract_cmd = _get_tesseract_path()
    except Exception:
        pass

    tessdata_dir = _get_tessdata_dir()
    if tessdata_dir:
        os.environ["TESSDATA_PREFIX"] = tessdata_dir

    if lang_override:
        tess_lang = lang_override
    else:
        ui_lang = _get_ui_language()
        tess_lang = _LANG_TO_TESS.get(ui_lang, "ron+eng")

    try:
        pages = convert_from_path(file_path, dpi=200)
    except Exception as e:
        logger.error("pdf2image failed for %s: %s", file_path, e)
        return ""

    texts = []
    for i, page_img in enumerate(pages):
        try:
            processed = _preprocess_image(page_img)
            text = pytesseract.image_to_string(processed, lang=tess_lang, config="--psm 6")
            texts.append(text)
        except Exception as e:
            logger.warning("OCR failed on page %d of %s: %s", i + 1, file_path, e)

    return "\n".join(texts)
