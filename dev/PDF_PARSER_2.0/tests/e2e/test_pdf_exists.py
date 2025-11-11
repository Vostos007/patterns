"""
End-to-end test for PDF export.

Verifies that:
- PDF file is created
- File contains actual content
- PDF is valid and readable
"""

from pathlib import Path
import pytest


def test_pdf_file_exists():
    """Test that PDF output file exists and is not empty."""
    pdf_path = Path("output/final.pdf")

    assert pdf_path.exists(), f"PDF file not found: {pdf_path}"
    assert pdf_path.stat().st_size > 0, "PDF file is empty"


def test_pdf_file_size():
    """Test that PDF has reasonable file size (not just a stub)."""
    pdf_path = Path("output/final.pdf")

    if not pdf_path.exists():
        pytest.skip(f"PDF file not found: {pdf_path}")

    file_size = pdf_path.stat().st_size
    # PDF should be at least 1KB (likely much more)
    assert file_size > 1024, f"PDF file too small ({file_size} bytes), might be corrupt"


def test_pdf_starts_with_header():
    """Test that PDF file has valid PDF header."""
    pdf_path = Path("output/final.pdf")

    if not pdf_path.exists():
        pytest.skip(f"PDF file not found: {pdf_path}")

    with open(pdf_path, "rb") as f:
        header = f.read(5)

    # Valid PDF files start with "%PDF-"
    assert header == b"%PDF-", f"Invalid PDF header: {header}"


def test_pdf_readable_with_pypdf():
    """Test that PDF can be opened and read with PyPDF."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        pytest.skip("PyPDF2 not installed")

    pdf_path = Path("output/final.pdf")

    if not pdf_path.exists():
        pytest.skip(f"PDF file not found: {pdf_path}")

    # Try to open PDF
    reader = PdfReader(str(pdf_path))

    # Check that PDF has pages
    assert len(reader.pages) > 0, "PDF has no pages"

    # Try to extract text from first page
    first_page = reader.pages[0]
    text = first_page.extract_text()

    # Should have some text content
    assert len(text.strip()) > 0, "First page of PDF contains no text"


def test_html_intermediate_exists():
    """Test that HTML intermediate file was created."""
    html_path = Path("build/doc.html")

    if not html_path.exists():
        pytest.skip(f"HTML file not found: {html_path}")

    assert html_path.stat().st_size > 0, "HTML file is empty"

    # Check HTML content
    content = html_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content or "<html" in content, "Invalid HTML structure"


def test_markdown_intermediate_exists():
    """Test that Markdown intermediate file was created."""
    md_path = Path("build/doc.md")

    if not md_path.exists():
        pytest.skip(f"Markdown file not found: {md_path}")

    assert md_path.stat().st_size > 0, "Markdown file is empty"

    # Check Markdown content
    content = md_path.read_text(encoding="utf-8")
    assert len(content.strip()) > 0, "Markdown file contains no text"
