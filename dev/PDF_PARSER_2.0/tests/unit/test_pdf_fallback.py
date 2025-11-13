from pathlib import Path
from unittest.mock import patch

from kps.core import UnifiedPipeline
from kps.core.document import (
    BlockType,
    ContentBlock,
    DocumentMetadata,
    KPSDocument,
    Section,
    SectionType,
)


def _make_simple_document() -> KPSDocument:
    metadata = DocumentMetadata(title="test", language="ru")
    block = ContentBlock(
        block_id="p.cover.001",
        block_type=BlockType.PARAGRAPH,
        content="Test content",
    )
    section = Section(section_type=SectionType.COVER, title="Cover", blocks=[block])
    return KPSDocument(slug="test", metadata=metadata, sections=[section])


def test_pdf_fallback_builder_uses_browser(tmp_path: Path):
    pipeline = UnifiedPipeline()
    translated_doc = _make_simple_document()
    output_file = tmp_path / "out.pdf"

    builder = pipeline._build_pdf_fallback_builder(translated_doc, output_file)

    with patch("kps.core.unified_pipeline.render_html", return_value="<html></html>"):
        with patch("kps.core.unified_pipeline.render_pdf", side_effect=RuntimeError("Weasy unavailable")):
            with patch("kps.core.unified_pipeline.export_pdf_browser") as mock_browser:
                result_path, label = builder()

    assert result_path == output_file
    assert label == "pdf-browser"
    mock_browser.assert_called_once_with("<html></html>", output_file)
