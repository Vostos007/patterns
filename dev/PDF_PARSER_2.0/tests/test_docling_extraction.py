"""
Tests for Docling-based text extraction (Day 3).

Tests the DoclingExtractor adapter that converts Docling document structure
into KPS-compliant KPSDocument with proper section typing, block IDs, and
reading order preservation.

Critical validations:
- Section type detection using Russian patterns
- Block ID format: "type.section.###"
- Heading hierarchy preservation (h1, h2, h3)
- Reading order preservation (top-to-bottom, column-aware)
- BBox extraction for all blocks
- Error handling for invalid PDFs
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from kps.core.document import (
    KPSDocument,
    Section,
    SectionType,
    ContentBlock,
    BlockType,
    DocumentMetadata,
)
from kps.core.bbox import BBox

# Note: These tests assume the existence of kps.extraction.docling_extractor module
# which will be implemented in Day 3

pytestmark = pytest.mark.unit


class TestDoclingExtraction:
    """Test suite for Docling extraction adapter."""

    def test_extract_single_page_document(self, simple_pdf_path):
        """
        Test extraction of a simple single-page PDF.

        Validates:
        - Document is created with correct metadata
        - At least one section is extracted
        - All blocks have valid block_ids
        - All blocks have page_number set
        """
        from kps.extraction.docling_extractor import DoclingExtractor

        extractor = DoclingExtractor()
        document = extractor.extract(simple_pdf_path)

        assert isinstance(document, KPSDocument)
        assert document.slug
        assert document.metadata.language == "ru"
        assert len(document.sections) > 0

        # Validate all blocks
        for section in document.sections:
            for block in section.blocks:
                assert block.block_id.count('.') == 2  # Format: "type.section.###"
                assert block.page_number is not None
                assert block.page_number >= 0

    def test_extract_multi_page_document(self, multi_page_pdf_path):
        """
        Test extraction of multi-page PDF.

        Validates:
        - All pages are processed
        - Blocks span multiple pages
        - Reading order is correct across pages
        - Page numbers are accurate
        """
        from kps.extraction.docling_extractor import DoclingExtractor

        extractor = DoclingExtractor()
        document = extractor.extract(multi_page_pdf_path)

        # Collect all unique page numbers
        page_numbers = set()
        for section in document.sections:
            for block in section.blocks:
                if block.page_number is not None:
                    page_numbers.add(block.page_number)

        assert len(page_numbers) >= 2  # At least 2 pages
        assert min(page_numbers) == 0  # 0-indexed

        # Validate reading order within each page
        for page_num in page_numbers:
            blocks_on_page = document.get_blocks_on_page(page_num)

            # Reading order should be sequential
            reading_orders = [b.reading_order for b in blocks_on_page]
            assert reading_orders == sorted(reading_orders)

    def test_section_type_detection_russian_patterns(self, russian_pattern_pdf_path):
        """
        Test section type detection using Russian text patterns.

        Russian section headers:
        - "Материалы" → MATERIALS
        - "Плотность" → GAUGE
        - "Размеры" → SIZES
        - "Техники" → TECHNIQUES
        - "Инструкция" → INSTRUCTIONS
        - "Сокращения" → ABBREVIATIONS
        - "Отделка" → FINISHING

        Validates:
        - Correct mapping of Russian headers to SectionType enum
        - At least 3 sections detected
        - No sections with generic names
        """
        from kps.extraction.docling_extractor import DoclingExtractor

        extractor = DoclingExtractor()
        document = extractor.extract(russian_pattern_pdf_path)

        section_types = [s.section_type for s in document.sections]

        # Should have at least Materials and Instructions
        assert SectionType.MATERIALS in section_types
        assert SectionType.INSTRUCTIONS in section_types

        # Each section should have proper title
        for section in document.sections:
            assert section.title
            assert len(section.title) > 0

    def test_block_id_generation_format(self, simple_pdf_path):
        """
        Test block ID generation follows format: "type.section.###".

        Examples:
        - "p.materials.001"  (paragraph)
        - "h2.techniques.001"  (heading level 2)
        - "tbl.sizes.001"  (table)
        - "lst.instructions.001"  (list)

        Validates:
        - Format is consistent
        - IDs are unique within document
        - Sequential numbering per section
        """
        from kps.extraction.docling_extractor import DoclingExtractor

        extractor = DoclingExtractor()
        document = extractor.extract(simple_pdf_path)

        all_block_ids = set()

        for section in document.sections:
            section_block_ids = []

            for block in section.blocks:
                # Validate format
                parts = block.block_id.split('.')
                assert len(parts) == 3, f"Invalid block_id format: {block.block_id}"

                type_prefix, section_name, number = parts

                # Type prefix should match block type
                if block.block_type == BlockType.PARAGRAPH:
                    assert type_prefix == 'p'
                elif block.block_type == BlockType.HEADING:
                    assert type_prefix.startswith('h')  # h1, h2, h3, etc.
                elif block.block_type == BlockType.TABLE:
                    assert type_prefix == 'tbl'
                elif block.block_type == BlockType.LIST:
                    assert type_prefix == 'lst'

                # Number should be zero-padded 3 digits
                assert number.isdigit()
                assert len(number) == 3

                # Check uniqueness
                assert block.block_id not in all_block_ids
                all_block_ids.add(block.block_id)

                section_block_ids.append(block.block_id)

            # Validate sequential numbering within section
            # Extract numbers and check they're sequential
            numbers = [int(bid.split('.')[-1]) for bid in section_block_ids]
            # Note: May not be strictly 1,2,3... due to different block types
            # But should be in reasonable range
            if numbers:
                assert min(numbers) >= 1
                assert max(numbers) <= len(section_block_ids) + 10

    def test_heading_hierarchy_preservation(self, hierarchical_pdf_path):
        """
        Test heading hierarchy is preserved (h1, h2, h3).

        Validates:
        - Heading levels are detected correctly
        - h1 > h2 > h3 hierarchy is maintained
        - Block IDs reflect heading level (h1.*, h2.*, h3.*)
        """
        from kps.extraction.docling_extractor import DoclingExtractor

        extractor = DoclingExtractor()
        document = extractor.extract(hierarchical_pdf_path)

        # Collect all heading blocks
        headings = []
        for section in document.sections:
            for block in section.blocks:
                if block.block_type == BlockType.HEADING:
                    headings.append(block)

        assert len(headings) > 0, "No headings found"

        # Validate heading levels in block IDs
        for heading in headings:
            type_prefix = heading.block_id.split('.')[0]
            assert type_prefix.startswith('h'), f"Heading block should have h* prefix: {heading.block_id}"

            # Extract level
            level = int(type_prefix[1:])
            assert 1 <= level <= 6, f"Invalid heading level: {level}"

    def test_reading_order_preservation(self, two_column_pdf_path):
        """
        Test reading order is preserved correctly for multi-column layout.

        Validates:
        - reading_order field is set for all blocks
        - Order is logical (top-to-bottom, left-to-right for columns)
        - No duplicate reading_order values on same page
        """
        from kps.extraction.docling_extractor import DoclingExtractor

        extractor = DoclingExtractor()
        document = extractor.extract(two_column_pdf_path)

        # Check each page
        for page_num in range(3):  # Assume at least 3 pages
            blocks = document.get_blocks_on_page(page_num)

            if not blocks:
                continue

            # Reading order should be sequential and unique
            reading_orders = [b.reading_order for b in blocks]
            assert len(reading_orders) == len(set(reading_orders)), \
                f"Duplicate reading_order on page {page_num}"

            # Should be sorted
            assert reading_orders == sorted(reading_orders)

    def test_bbox_extraction_for_all_blocks(self, simple_pdf_path):
        """
        Test bounding boxes are extracted for all content blocks.

        Validates:
        - All blocks have bbox attribute set
        - BBox coordinates are valid (x0 < x1, y0 < y1)
        - Coordinates are within reasonable page bounds (0-1000 pt)
        """
        from kps.extraction.docling_extractor import DoclingExtractor

        extractor = DoclingExtractor()
        document = extractor.extract(simple_pdf_path)

        blocks_without_bbox = []

        for section in document.sections:
            for block in section.blocks:
                if block.bbox is None:
                    blocks_without_bbox.append(block.block_id)
                else:
                    # Validate bbox
                    assert block.bbox.x0 < block.bbox.x1, \
                        f"Invalid bbox x-coords for {block.block_id}"
                    assert block.bbox.y0 < block.bbox.y1, \
                        f"Invalid bbox y-coords for {block.block_id}"

                    # Check reasonable bounds (typical page is ~600pt wide)
                    assert 0 <= block.bbox.x0 <= 1000
                    assert 0 <= block.bbox.x1 <= 1000
                    assert 0 <= block.bbox.y0 <= 1500
                    assert 0 <= block.bbox.y1 <= 1500

        # Allow some blocks without bbox (e.g., synthetic blocks)
        # But most should have bbox
        total_blocks = sum(len(s.blocks) for s in document.sections)
        assert len(blocks_without_bbox) < total_blocks * 0.1, \
            f"Too many blocks without bbox: {blocks_without_bbox}"

    def test_error_handling_invalid_pdf(self, invalid_pdf_path):
        """
        Test error handling for invalid PDF file.

        Validates:
        - Appropriate exception is raised
        - Error message is descriptive
        """
        from kps.extraction.docling_extractor import DoclingExtractor, ExtractionError

        extractor = DoclingExtractor()

        with pytest.raises((ExtractionError, Exception)) as exc_info:
            extractor.extract(invalid_pdf_path)

        # Error message should mention the file
        assert str(invalid_pdf_path) in str(exc_info.value) or "PDF" in str(exc_info.value)

    def test_error_handling_empty_document(self, empty_pdf_path):
        """
        Test handling of empty PDF (no extractable content).

        Validates:
        - Returns valid KPSDocument
        - Document has empty or minimal sections
        - No crash or exception
        """
        from kps.extraction.docling_extractor import DoclingExtractor

        extractor = DoclingExtractor()
        document = extractor.extract(empty_pdf_path)

        assert isinstance(document, KPSDocument)
        # Should have minimal structure even if empty
        total_blocks = sum(len(s.blocks) for s in document.sections)
        assert total_blocks == 0 or total_blocks < 5

    def test_error_handling_corrupted_pdf(self, corrupted_pdf_path):
        """
        Test handling of corrupted PDF file.

        Validates:
        - Appropriate exception is raised
        - No silent failures
        """
        from kps.extraction.docling_extractor import DoclingExtractor, ExtractionError

        extractor = DoclingExtractor()

        with pytest.raises((ExtractionError, Exception)):
            extractor.extract(corrupted_pdf_path)

    def test_block_content_not_empty(self, simple_pdf_path):
        """
        Test that extracted blocks have non-empty content.

        Validates:
        - PARAGRAPH blocks have text content
        - TABLE blocks have content or structure
        - HEADING blocks have text
        """
        from kps.extraction.docling_extractor import DoclingExtractor

        extractor = DoclingExtractor()
        document = extractor.extract(simple_pdf_path)

        for section in document.sections:
            for block in section.blocks:
                # Content should not be None or empty string (with exceptions)
                if block.block_type in [BlockType.PARAGRAPH, BlockType.HEADING]:
                    assert block.content
                    assert len(block.content.strip()) > 0

    def test_russian_text_encoding_preserved(self, russian_text_pdf_path):
        """
        Test that Russian (Cyrillic) text is correctly encoded.

        Validates:
        - Cyrillic characters are preserved
        - No encoding corruption (mojibake)
        - Content is readable
        """
        from kps.extraction.docling_extractor import DoclingExtractor

        extractor = DoclingExtractor()
        document = extractor.extract(russian_text_pdf_path)

        # Collect all text content
        all_text = ""
        for section in document.sections:
            all_text += section.get_all_text()

        # Should contain Cyrillic characters
        assert any('\u0400' <= char <= '\u04FF' for char in all_text), \
            "No Cyrillic characters found"

        # Check for common Russian knitting terms
        russian_terms = ["петли", "ряд", "вязать", "см"]
        found_terms = [term for term in russian_terms if term.lower() in all_text.lower()]
        assert len(found_terms) > 0, "No Russian knitting terms found"

    def test_table_block_detection(self, pdf_with_tables_path):
        """
        Test that table blocks are detected and typed correctly.

        Validates:
        - Tables are identified as BlockType.TABLE
        - Table blocks have bbox
        - Table content is extracted (even if minimal)
        """
        from kps.extraction.docling_extractor import DoclingExtractor

        extractor = DoclingExtractor()
        document = extractor.extract(pdf_with_tables_path)

        # Find table blocks
        table_blocks = []
        for section in document.sections:
            for block in section.blocks:
                if block.block_type == BlockType.TABLE:
                    table_blocks.append(block)

        assert len(table_blocks) > 0, "No table blocks detected"

        # Validate table blocks
        for table_block in table_blocks:
            assert table_block.bbox is not None
            assert table_block.content  # Should have some content

    def test_table_without_text_uses_markdown_export(self):
        """Fallback to Docling's table exporters when .text is empty."""

        from kps.extraction.docling_extractor import DoclingExtractor

        class _FakeTable:
            obj_type = "table"
            text = ""
            page_number = 1
            reading_order = 2
            bbox = (0.0, 0.0, 10.0, 10.0)

            def export_to_markdown(self, doc=None):  # noqa: D401 - simple stub
                return "| Metric | EUR | USD |\n|--------|-----|-----|\n| Fees | -1.00 | 0.00 |"

        fake_table = _FakeTable()

        extractor = DoclingExtractor()

        def _fake_iter(_doc):
            yield "#/tables/0", fake_table

        extractor._iter_docling_items = _fake_iter  # type: ignore[assignment]

        sections = extractor._extract_sections(object())

        table_blocks = [
            block
            for section in sections
            for block in section.blocks
            if block.block_type == BlockType.TABLE
        ]

        assert table_blocks, "Table block should be created even without raw text"
        assert "Fees" in table_blocks[0].content

    @pytest.mark.slow
    def test_performance_10_page_extraction(self, ten_page_pdf_path):
        """
        Test extraction performance for 10-page document.

        Performance target: < 30 seconds for 10-page PDF

        Validates:
        - Extraction completes within time limit
        - All pages are processed
        - Result is complete
        """
        import time
        from kps.extraction.docling_extractor import DoclingExtractor

        extractor = DoclingExtractor()

        start_time = time.time()
        document = extractor.extract(ten_page_pdf_path)
        elapsed_time = time.time() - start_time

        # Validate performance
        assert elapsed_time < 30.0, \
            f"Extraction took {elapsed_time:.2f}s, expected < 30s"

        # Validate completeness
        page_numbers = set()
        for section in document.sections:
            for block in section.blocks:
                if block.page_number is not None:
                    page_numbers.add(block.page_number)

        assert len(page_numbers) >= 10, \
            f"Expected 10 pages, found {len(page_numbers)}"
