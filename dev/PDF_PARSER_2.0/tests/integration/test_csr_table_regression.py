from pathlib import Path

from kps.core.document import BlockType
from kps.extraction.docling_extractor import DoclingExtractor


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def test_csr_table_survives_extraction_and_contains_headers():
    pdf_path = _project_root() / "runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf"
    assert pdf_path.exists(), "CSR sample PDF is missing"

    extractor = DoclingExtractor()
    document = extractor.extract_document(pdf_path, slug="csr-regression")

    table_contents = [
        block.content
        for section in document.sections
        for block in section.blocks
        if block.block_type == BlockType.TABLE
    ]

    assert table_contents, "Expected at least one table block"
    assert any("Available beginning" in content for content in table_contents), (
        "CSR balance summary header missing from table content"
    )
