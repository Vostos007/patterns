import fitz
from pathlib import Path

from pdf_pipeline.extractor import PDFBlock
from pdf_pipeline.html_renderer import render_html


def test_render_html_creates_structured_page(tmp_path):
    pdf_path = tmp_path / "source.pdf"
    doc = fitz.open()
    doc.new_page(width=200, height=300)
    doc.save(pdf_path)
    doc.close()

    block = PDFBlock.from_text(
        page_number=0,
        block_id=0,
        bbox=(10, 20, 110, 60),
        text="Header line",
    )
    block.metadata["role"] = "header"

    html_path = tmp_path / "output.html"

    render_html(
        pdf_path,
        html_path,
        [block],
        ["Header line"],
        language="en",
    )

    html_text = html_path.read_text(encoding="utf-8")
    assert "<section class=\"page\"" in html_text
    assert "data-role=\"header\"" in html_text
    assert "Header line" in html_text
