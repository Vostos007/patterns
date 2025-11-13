"""Unit tests for Docling text extractor."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from kps.extraction.docling_extractor import DoclingExtractor, DoclingExtractionError
from kps.core.document import (
    BlockType,
    ContentBlock,
    DocumentMetadata,
    KPSDocument,
    Section,
    SectionType,
)
from kps.core.bbox import BBox


class TestDoclingExtractor:
    """Test suite for DoclingExtractor."""

    def test_init_default_config(self):
        """Test extractor initialization with default configuration."""
        extractor = DoclingExtractor()

        assert extractor.languages == ["ru", "en", "fr"]
        assert extractor.ocr_enabled is True
        assert extractor.page_range is None
        assert extractor.converter is not None

    def test_init_custom_config(self):
        """Test extractor initialization with custom configuration."""
        extractor = DoclingExtractor(
            languages=["en"],
            ocr_enabled=False,
            page_range=(0, 10),
        )

        assert extractor.languages == ["en"]
        assert extractor.ocr_enabled is False
        assert extractor.page_range == (0, 10)

    def test_detect_section_type_materials(self):
        """Test section type detection for materials section."""
        extractor = DoclingExtractor()

        # Russian
        assert (
            extractor._detect_section_type("Материалы") == SectionType.MATERIALS
        )
        assert (
            extractor._detect_section_type("МАТЕРИАЛЫ И ИНСТРУМЕНТЫ")
            == SectionType.MATERIALS
        )
        assert extractor._detect_section_type("Пряжа") == SectionType.MATERIALS

        # English
        assert extractor._detect_section_type("Materials") == SectionType.MATERIALS

    def test_detect_section_type_gauge(self):
        """Test section type detection for gauge section."""
        extractor = DoclingExtractor()

        assert extractor._detect_section_type("Плотность вязания") == SectionType.GAUGE
        assert extractor._detect_section_type("Образец") == SectionType.GAUGE
        assert extractor._detect_section_type("Gauge") == SectionType.GAUGE
        assert extractor._detect_section_type("Density") == SectionType.GAUGE

    def test_detect_section_type_sizes(self):
        """Test section type detection for sizes section."""
        extractor = DoclingExtractor()

        assert extractor._detect_section_type("Размеры") == SectionType.SIZES
        assert extractor._detect_section_type("Sizes") == SectionType.SIZES
        assert extractor._detect_section_type("Обхват груди") == SectionType.SIZES

    def test_detect_section_type_techniques(self):
        """Test section type detection for techniques section."""
        extractor = DoclingExtractor()

        assert (
            extractor._detect_section_type("Техники вязания") == SectionType.TECHNIQUES
        )
        assert extractor._detect_section_type("Приёмы") == SectionType.TECHNIQUES
        assert extractor._detect_section_type("Techniques") == SectionType.TECHNIQUES

    def test_detect_section_type_instructions(self):
        """Test section type detection for instructions section."""
        extractor = DoclingExtractor()

        assert (
            extractor._detect_section_type("Инструкция") == SectionType.INSTRUCTIONS
        )
        assert (
            extractor._detect_section_type("Описание работы")
            == SectionType.INSTRUCTIONS
        )
        assert (
            extractor._detect_section_type("Instructions") == SectionType.INSTRUCTIONS
        )

    def test_detect_section_type_finishing(self):
        """Test section type detection for finishing section."""
        extractor = DoclingExtractor()

        assert extractor._detect_section_type("Сборка") == SectionType.FINISHING
        assert extractor._detect_section_type("Отделка") == SectionType.FINISHING
        assert extractor._detect_section_type("Finishing") == SectionType.FINISHING

    def test_detect_section_type_abbreviations(self):
        """Test section type detection for abbreviations section."""
        extractor = DoclingExtractor()

        assert (
            extractor._detect_section_type("Сокращения") == SectionType.ABBREVIATIONS
        )
        assert (
            extractor._detect_section_type("Условные обозначения")
            == SectionType.ABBREVIATIONS
        )
        assert (
            extractor._detect_section_type("Abbreviations")
            == SectionType.ABBREVIATIONS
        )

    def test_detect_section_type_default(self):
        """Test section type detection for unknown sections."""
        extractor = DoclingExtractor()

        # Unknown sections default to INSTRUCTIONS
        assert (
            extractor._detect_section_type("Unknown Section")
            == SectionType.INSTRUCTIONS
        )
        assert (
            extractor._detect_section_type("Random Text") == SectionType.INSTRUCTIONS
        )

    def test_map_docling_type_paragraph(self):
        """Test mapping Docling types to paragraph."""
        extractor = DoclingExtractor()

        assert extractor._map_docling_type("paragraph") == BlockType.PARAGRAPH
        assert extractor._map_docling_type("text") == BlockType.PARAGRAPH
        assert extractor._map_docling_type(None) == BlockType.PARAGRAPH

    def test_map_docling_type_heading(self):
        """Test mapping Docling types to heading."""
        extractor = DoclingExtractor()

        assert extractor._map_docling_type("heading") == BlockType.HEADING
        assert extractor._map_docling_type("heading_1") == BlockType.HEADING
        assert extractor._map_docling_type("HEADING") == BlockType.HEADING

    def test_map_docling_type_list(self):
        """Test mapping Docling types to list."""
        extractor = DoclingExtractor()

        assert extractor._map_docling_type("list") == BlockType.LIST
        assert extractor._map_docling_type("list_item") == BlockType.LIST
        assert extractor._map_docling_type("LIST") == BlockType.LIST

    def test_map_docling_type_table(self):
        """Test mapping Docling types to table."""
        extractor = DoclingExtractor()

        assert extractor._map_docling_type("table") == BlockType.TABLE
        assert extractor._map_docling_type("TABLE") == BlockType.TABLE

    def test_map_docling_type_figure(self):
        """Test mapping Docling types to figure."""
        extractor = DoclingExtractor()

        assert extractor._map_docling_type("figure") == BlockType.FIGURE
        assert extractor._map_docling_type("image") == BlockType.FIGURE
        assert extractor._map_docling_type("FIGURE") == BlockType.FIGURE

    def test_map_docling_type_label_fallback(self):
        """Docling items without obj_type should fall back to label metadata."""

        extractor = DoclingExtractor()

        class _TableItem:
            label = "table"

        class _FigureItem:
            class _Label:
                value = "picture"

            label = _Label()

        assert extractor._map_docling_type(None, _TableItem()) == BlockType.TABLE
        assert extractor._map_docling_type(None, _FigureItem()) == BlockType.FIGURE

    def test_generate_block_id_paragraph(self):
        """Test block ID generation for paragraphs."""
        extractor = DoclingExtractor()

        block_id = extractor._generate_block_id(
            BlockType.PARAGRAPH, SectionType.MATERIALS
        )
        assert block_id == "p.materials.001"

        block_id = extractor._generate_block_id(
            BlockType.PARAGRAPH, SectionType.MATERIALS
        )
        assert block_id == "p.materials.002"

    def test_generate_block_id_heading(self):
        """Test block ID generation for headings."""
        extractor = DoclingExtractor()

        block_id = extractor._generate_block_id(
            BlockType.HEADING, SectionType.TECHNIQUES
        )
        assert block_id == "h.techniques.001"

        block_id = extractor._generate_block_id(
            BlockType.HEADING, SectionType.TECHNIQUES
        )
        assert block_id == "h.techniques.002"

    def test_generate_block_id_table(self):
        """Test block ID generation for tables."""
        extractor = DoclingExtractor()

        block_id = extractor._generate_block_id(BlockType.TABLE, SectionType.SIZES)
        assert block_id == "tbl.sizes.001"

    def test_generate_block_id_list(self):
        """Test block ID generation for lists."""
        extractor = DoclingExtractor()

        block_id = extractor._generate_block_id(
            BlockType.LIST, SectionType.INSTRUCTIONS
        )
        assert block_id == "lst.instructions.001"

    def test_generate_block_id_figure(self):
        """Test block ID generation for figures."""
        extractor = DoclingExtractor()

        block_id = extractor._generate_block_id(
            BlockType.FIGURE, SectionType.INSTRUCTIONS
        )
        assert block_id == "fig.instructions.001"

    def test_generate_block_id_counter_per_section(self):
        """Test that block counters are maintained per section type."""
        extractor = DoclingExtractor()

        # Materials section
        id1 = extractor._generate_block_id(BlockType.PARAGRAPH, SectionType.MATERIALS)
        id2 = extractor._generate_block_id(BlockType.PARAGRAPH, SectionType.MATERIALS)

        # Different section
        id3 = extractor._generate_block_id(BlockType.PARAGRAPH, SectionType.GAUGE)

        # Back to materials
        id4 = extractor._generate_block_id(BlockType.PARAGRAPH, SectionType.MATERIALS)

        assert id1 == "p.materials.001"
        assert id2 == "p.materials.002"
        assert id3 == "p.gauge.001"  # Starts at 1 for new section
        assert id4 == "p.materials.003"  # Continues from materials counter

    def test_extract_bbox_valid(self):
        """Test bbox extraction from Docling item."""
        extractor = DoclingExtractor()

        # Mock Docling item with bbox
        mock_item = Mock()
        mock_item.bbox = [100.0, 200.0, 300.0, 400.0]

        bbox = extractor._extract_bbox(mock_item)

        assert bbox is not None
        assert bbox.x0 == 100.0
        assert bbox.y0 == 200.0
        assert bbox.x1 == 300.0
        assert bbox.y1 == 400.0

    def test_extract_bbox_tuple(self):
        """Test bbox extraction with tuple format."""
        extractor = DoclingExtractor()

        mock_item = Mock()
        mock_item.bbox = (50.0, 60.0, 150.0, 160.0)

        bbox = extractor._extract_bbox(mock_item)

        assert bbox is not None
        assert bbox.x0 == 50.0
        assert bbox.y0 == 60.0

    def test_extract_bbox_missing(self):
        """Test bbox extraction when bbox is missing."""
        extractor = DoclingExtractor()

        mock_item = Mock(spec=[])  # No bbox attribute

        bbox = extractor._extract_bbox(mock_item)

        assert bbox is None

    def test_extract_bbox_invalid_format(self):
        """Test bbox extraction with invalid format."""
        extractor = DoclingExtractor()

        mock_item = Mock()
        mock_item.bbox = [100.0, 200.0]  # Only 2 values

        bbox = extractor._extract_bbox(mock_item)

        assert bbox is None

    def test_detect_primary_language_russian(self):
        """Test language detection for Russian text."""
        extractor = DoclingExtractor()

        mock_doc = Mock()
        mock_doc.body = Mock()
        mock_doc.body.text = "Это русский текст с кириллицей"

        language = extractor._detect_primary_language(mock_doc)

        assert language == "ru"

    def test_detect_primary_language_english(self):
        """Test language detection for English text."""
        extractor = DoclingExtractor()

        mock_doc = Mock()
        mock_doc.body = Mock()
        mock_doc.body.text = "This is English text without Cyrillic"

        language = extractor._detect_primary_language(mock_doc)

        # Should default to first language in config
        assert language in ["ru", "en", "fr"]

    def test_detect_primary_language_default(self):
        """Test language detection with empty text."""
        extractor = DoclingExtractor(languages=["en"])

        mock_doc = Mock()
        mock_doc.body = None

        language = extractor._detect_primary_language(mock_doc)

        assert language == "en"

    def test_extract_document_file_not_found(self):
        """Test extraction with non-existent file."""
        extractor = DoclingExtractor()

        with pytest.raises(FileNotFoundError):
            extractor.extract_document(Path("/nonexistent/file.pdf"), "test-slug")

    @patch("kps.extraction.docling_extractor.DocumentConverter")
    def test_extract_document_empty_result(self, mock_converter_class):
        """Test extraction with empty Docling result."""
        # Create a temporary file
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)

        try:
            # Mock converter to return empty result
            mock_converter = Mock()
            mock_converter.convert.return_value = None
            mock_converter_class.return_value = mock_converter

            extractor = DoclingExtractor()
            extractor.converter = mock_converter

            with pytest.raises(DoclingExtractionError):
                extractor.extract_document(pdf_path, "test-slug")
        finally:
            pdf_path.unlink()

    @patch("kps.extraction.docling_extractor.DocumentConverter")
    def test_extract_document_empty_body(self, mock_converter_class):
        """Test extraction with empty document body."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = Path(f.name)

        try:
            # Mock converter
            mock_result = Mock()
            mock_doc = Mock()
            mock_doc.body = []  # Empty body
            mock_doc.metadata = None
            mock_result.document = mock_doc

            mock_converter = Mock()
            mock_converter.convert.return_value = mock_result
            mock_converter_class.return_value = mock_converter

            extractor = DoclingExtractor()
            extractor.converter = mock_converter

            with pytest.raises(DoclingExtractionError, match="no extractable content"):
                extractor.extract_document(pdf_path, "test-slug")
        finally:
            pdf_path.unlink()

    def test_create_content_block(self):
        """Test ContentBlock creation from Docling item."""
        extractor = DoclingExtractor()

        # Mock Docling item
        mock_item = Mock()
        mock_item.bbox = [100.0, 200.0, 300.0, 400.0]
        mock_item.page_number = 2
        mock_item.reading_order = 5

        block = extractor._create_content_block(
            mock_item,
            "Sample text content",
            BlockType.PARAGRAPH,
            SectionType.MATERIALS,
        )

        assert block.block_id == "p.materials.001"
        assert block.block_type == BlockType.PARAGRAPH
        assert block.content == "Sample text content"
        assert block.bbox is not None
        assert block.bbox.x0 == 100.0
        assert block.page_number == 2
        assert block.reading_order == 5

    def test_section_patterns_comprehensive(self):
        """Test that all section types have patterns defined."""
        # Verify all section types (except COVER) have patterns
        expected_types = [
            SectionType.MATERIALS,
            SectionType.GAUGE,
            SectionType.SIZES,
            SectionType.TECHNIQUES,
            SectionType.INSTRUCTIONS,
            SectionType.FINISHING,
            SectionType.ABBREVIATIONS,
            SectionType.GLOSSARY,
            SectionType.CONSTRUCTION,
        ]

        for section_type in expected_types:
            assert (
                section_type.value in DoclingExtractor.SECTION_PATTERNS
            ), f"Missing patterns for {section_type.value}"
            patterns = DoclingExtractor.SECTION_PATTERNS[section_type.value]
            assert len(patterns) > 0, f"Empty patterns for {section_type.value}"

    def test_block_type_prefixes_complete(self):
        """Test that all block types have ID prefixes defined."""
        for block_type in BlockType:
            assert (
                block_type in DoclingExtractor.BLOCK_TYPE_PREFIXES
            ), f"Missing prefix for {block_type.value}"


class TestDoclingExtractorIntegration:
    """Integration tests requiring Docling setup."""

    @pytest.mark.skip(reason="Requires real PDF file and Docling installation")
    def test_extract_real_pdf(self):
        """Test extraction with real PDF file."""
        # This would require a test PDF file
        extractor = DoclingExtractor()
        pdf_path = Path("tests/fixtures/pdfs/sample_pattern.pdf")

        document = extractor.extract_document(pdf_path, "sample-pattern")

        assert document is not None
        assert document.slug == "sample-pattern"
        assert len(document.sections) > 0
        assert document.metadata.title is not None
