from pathlib import Path

import pytest

from kps.export.pdf_browser import export_pdf_browser


@pytest.mark.slow
def test_export_pdf_browser_produces_pdf(tmp_path: Path):
    html = """<!DOCTYPE html><html><body><h1>Smoke</h1><p>PDF fallback</p></body></html>"""
    output = tmp_path / "fallback.pdf"

    try:
        export_pdf_browser(html, output)
    except RuntimeError as exc:
        if "Playwright" in str(exc):
            pytest.skip(f"Playwright unavailable: {exc}")
        raise

    assert output.exists(), "PDF file not created"
    assert output.stat().st_size > 0, "PDF file is empty"
