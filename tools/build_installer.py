"""
Build orchestrator: PyInstaller → Tesseract bundle → Inno Setup

Usage:
    python tools/build_installer.py [--skip-pyinstaller] [--skip-inno]

Steps:
  1. Run PyInstaller with build.spec
  2. Download + extract Tesseract portable binaries to tools/tesseract/
  3. Compile installer.iss with Inno Setup (ISCC.exe)
"""

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(ROOT, "tools")
TESS_DIR = os.path.join(TOOLS_DIR, "tesseract")
DIST_DIR = os.path.join(ROOT, "dist", "AnalyzenInvoiceReader")
OUTPUT_DIR = os.path.join(ROOT, "installer_output")

# UB-Mannheim Tesseract portable build (64-bit, v5)
# Update this URL to the latest stable release when needed.
TESS_ZIP_URL = (
    "https://github.com/UB-Mannheim/tesseract/releases/download/"
    "v5.3.3.20231005/tesseract-ocr-w64-setup-5.3.3.20231005.exe"
)

# Minimal tessdata packs bundled in installer (ron + eng)
TESSDATA_FAST_BASE = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{}.traineddata"
BUNDLED_LANGS = ["ron", "eng"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list, cwd: str = ROOT) -> None:
    print(f"\n>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"ERROR: command exited with code {result.returncode}")
        sys.exit(result.returncode)


def _download(url: str, dest: str, label: str = "") -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    label = label or os.path.basename(dest)

    def _progress(count, block, total):
        if total > 0:
            pct = min(count * block / total * 100, 100)
            print(f"\r  {label}: {pct:.0f}%", end="", flush=True)

    print(f"  Downloading {label}...")
    urllib.request.urlretrieve(url, dest, reporthook=_progress)
    print()


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_pyinstaller() -> None:
    print("\n=== Step 1: PyInstaller ===")
    spec = os.path.join(ROOT, "build.spec")
    _run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", spec])
    if not os.path.isdir(DIST_DIR):
        print(f"ERROR: Expected dist dir not found: {DIST_DIR}")
        sys.exit(1)
    print(f"  Output: {DIST_DIR}")


def step_tesseract() -> None:
    print("\n=== Step 2: Tesseract OCR bundle ===")

    tessdata_dest = os.path.join(TESS_DIR, "tessdata")
    os.makedirs(tessdata_dest, exist_ok=True)

    # Check if we can grab binaries from a local Tesseract install
    local_tess = None
    for candidate in [
        r"C:\Program Files\Tesseract-OCR",
        r"C:\Program Files (x86)\Tesseract-OCR",
    ]:
        if os.path.isfile(os.path.join(candidate, "tesseract.exe")):
            local_tess = candidate
            break

    if local_tess:
        print(f"  Found local Tesseract at: {local_tess}")
        print("  Copying binaries...")
        # Copy tesseract.exe and required DLLs
        for item in os.listdir(local_tess):
            src = os.path.join(local_tess, item)
            if item.lower().endswith((".exe", ".dll")) and os.path.isfile(src):
                shutil.copy2(src, TESS_DIR)
        print("  Copied tesseract.exe and DLLs.")
    else:
        print("  Tesseract not found locally.")
        print(f"  Please install Tesseract from:")
        print(f"    https://github.com/UB-Mannheim/tesseract/wiki")
        print(f"  Then re-run this script. Skipping binary copy.")

    # Download minimal tessdata packs
    for lang in BUNDLED_LANGS:
        dest = os.path.join(tessdata_dest, f"{lang}.traineddata")
        if os.path.isfile(dest):
            print(f"  Already present: {lang}.traineddata")
            continue
        url = TESSDATA_FAST_BASE.format(lang)
        _download(url, dest, label=f"{lang}.traineddata")

    print(f"  Tessdata dir: {tessdata_dest}")
    print(f"  Bundled packs: {BUNDLED_LANGS}")


def step_inno() -> None:
    print("\n=== Step 3: Inno Setup ===")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Find ISCC.exe
    iscc_candidates = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        "ISCC.exe",  # in PATH
    ]
    iscc = None
    for c in iscc_candidates:
        if os.path.isfile(c) or shutil.which(c):
            iscc = c
            break

    if not iscc:
        print("  WARNING: Inno Setup (ISCC.exe) not found.")
        print("  Install from: https://jrsoftware.org/isinfo.php")
        print("  Then re-run: ISCC.exe installer.iss")
        return

    iss = os.path.join(ROOT, "installer.iss")
    _run([iscc, iss])

    exes = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".exe")]
    if exes:
        print(f"\n  Installer ready: {os.path.join(OUTPUT_DIR, exes[-1])}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build Analyzen installer")
    parser.add_argument("--skip-pyinstaller", action="store_true")
    parser.add_argument("--skip-tesseract",   action="store_true")
    parser.add_argument("--skip-inno",        action="store_true")
    args = parser.parse_args()

    os.chdir(ROOT)

    if not args.skip_pyinstaller:
        step_pyinstaller()

    if not args.skip_tesseract:
        step_tesseract()

    if not args.skip_inno:
        step_inno()

    print("\n=== Build complete ===")


if __name__ == "__main__":
    main()
