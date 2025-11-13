"""PDF fallback rendered via headless browser when WeasyPrint is unavailable."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def export_pdf_browser(
    html_content: str,
    output_path: Path,
    *,
    wait_until: str = "networkidle",
    print_background: bool = True,
) -> Path:
    """Render HTML into PDF using a headless Chromium browser (Playwright)."""

    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Playwright is not installed. Install it via `pip install playwright` "
            "and run `playwright install chromium`."
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.set_content(html_content, wait_until=wait_until)
                page.pdf(path=str(output_path), print_background=print_background)
            finally:
                browser.close()
    except PlaywrightError as exc:
        logger.error("Playwright PDF export failed: %s", exc)
        raise RuntimeError("Playwright PDF export failed") from exc

    return output_path
