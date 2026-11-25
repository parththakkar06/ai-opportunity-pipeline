"""HTML -> PDF, trying in order: Playwright (system Chrome, then its own Chromium), WeasyPrint,
then system Chrome headless on the command line. Raises PDFUnavailable if none work."""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from pypdf import PdfReader

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]
FOOTER = ('<div style="font-size:8px;width:100%;text-align:center;color:#666">'
          '<span class="pageNumber"></span> / <span class="totalPages"></span></div>')


class PDFUnavailable(RuntimeError):
    pass


def page_count(pdf: bytes) -> int:
    return len(PdfReader(io.BytesIO(pdf)).pages)


def _playwright(html: str, page_numbers: bool) -> bytes:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = None
        for kwargs in ({"channel": "chrome"}, {}):
            try:
                browser = p.chromium.launch(**kwargs)
                break
            except Exception:  # noqa: BLE001 - try the next browser
                continue
        if browser is None:
            raise PDFUnavailable("Playwright found no browser")
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            opts = {"format": "A4", "print_background": True, "prefer_css_page_size": True}
            if page_numbers:
                opts.update(display_header_footer=True, header_template="<div></div>", footer_template=FOOTER)
            return page.pdf(**opts)
        finally:
            browser.close()


def _weasyprint(html: str) -> bytes:
    from weasyprint import HTML  # optional dependency

    return HTML(string=html).write_pdf()


def _chrome_cli(html: str) -> bytes:
    chrome = next((c for c in CHROME_PATHS if Path(c).exists() or shutil.which(c)), None)
    if not chrome:
        raise PDFUnavailable("no Chrome or Chromium found")
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "in.html", Path(tmp) / "out.pdf"
        src.write_text(html, encoding="utf-8")
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", src.as_uri()], check=True, capture_output=True, timeout=60)
        return out.read_bytes()


def html_to_pdf(html: str, page_numbers: bool = False) -> tuple[bytes, str]:
    """Returns (pdf bytes, engine used)."""
    errors = []
    for name, fn in (("playwright", lambda: _playwright(html, page_numbers)), ("weasyprint", lambda: _weasyprint(html)),
                     ("chrome-cli", lambda: _chrome_cli(html))):
        try:
            return fn(), name
        except Exception as exc:  # noqa: BLE001 - fall through to the next engine
            errors.append(f"{name}: {exc.__class__.__name__}")
    raise PDFUnavailable("No PDF engine worked (" + "; ".join(errors) + "). Install one with "
                         "`pip install playwright && playwright install chromium`.")
