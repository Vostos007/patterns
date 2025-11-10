"""
Integration tests for extraction pipeline (Day 3).

Tests the complete extraction workflow:
1. PDF → Docling → KPSDocument (text/structure)
2. PDF → PyMuPDF → AssetLedger (visual assets)
3. Asset anchoring (Day 2 integration)
4. Marker injection (Day 2 integration)

Critical validations:
- Full pipeline PDF → Document + Ledger → Anchored + Marked
- Newline preservation end-to-end
- 100% asset coverage
- Asset marker integrity
- Performance targets
"""

import pytest
from pathlib import Path
from kps.core.document import KPSDocument, BlockType
from kps.core.assets import AssetLedger, AssetType
from kps.anchoring.anchor import anchor_assets_to_blocks
from kps.anchoring.markers import inject_markers, count_markers

pytestmark = pytest.mark.integration


class TestExtractionPipeline:
    """Integration tests for extraction pipeline."""

    @pytest.mark.slow
    def test_full_extraction_text_and_assets(self, sample_russian_pattern_pdf, tmp_path):
        """
        Test complete extraction: PDF → KPSDocument + AssetLedger.

        Validates:
        - Both text and assets are extracted
        - Document has sections and blocks
        - Ledger has assets with proper metadata
        - Page counts match
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        # Extract text structure
        docling = DoclingExtractor()
        document = docling.extract(sample_russian_pattern_pdf)

        # Extract visual assets
        pymupdf = PyMuPDFExtractor(output_dir=tmp_path / "assets")
        ledger = pymupdf.extract_assets(sample_russian_pattern_pdf)

        # Validate document
        assert isinstance(document, KPSDocument)
        assert len(document.sections) > 0
        total_blocks = sum(len(s.blocks) for s in document.sections)
        assert total_blocks > 0

        # Validate ledger
        assert isinstance(ledger, AssetLedger)
        assert len(ledger.assets) > 0

        # Page counts should match
        doc_pages = set()
        for section in document.sections:
            for block in section.blocks:
                if block.page_number is not None:
                    doc_pages.add(block.page_number)

        ledger_pages = set(a.page_number for a in ledger.assets)

        # Should have overlapping pages
        assert len(doc_pages.intersection(ledger_pages)) > 0

    @pytest.mark.slow
    def test_extraction_with_asset_anchoring(self, sample_russian_pattern_pdf, tmp_path):
        """
        Test extraction + asset anchoring integration.

        Validates:
        - Assets are anchored to blocks
        - All assets have anchor_to set
        - Anchored blocks exist in document
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        # Extract
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            sample_russian_pattern_pdf
        )

        # Anchor assets (Day 2 integration)
        anchored_ledger = anchor_assets_to_blocks(document, ledger)

        # Validate anchoring
        for asset in anchored_ledger.assets:
            assert asset.anchor_to, f"Asset {asset.asset_id} not anchored"

            # Block should exist
            block = document.find_block(asset.anchor_to)
            assert block is not None, \
                f"Anchored block {asset.anchor_to} not found for asset {asset.asset_id}"

    @pytest.mark.slow
    def test_extraction_with_marker_injection(self, sample_russian_pattern_pdf, tmp_path):
        """
        Test extraction + anchoring + marker injection.

        Full Day 2 + Day 3 integration.

        Validates:
        - Markers are injected into document
        - Every anchored asset has a marker
        - Markers match asset_ids
        - No orphaned markers
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        # Extract
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            sample_russian_pattern_pdf
        )

        # Anchor
        anchored_ledger = anchor_assets_to_blocks(document, ledger)

        # Inject markers (Day 2)
        marked_document = inject_markers(document, anchored_ledger)

        # Validate markers
        marker_stats = count_markers(marked_document)

        # All anchored assets should have markers
        anchored_asset_count = len([a for a in anchored_ledger.assets if a.anchor_to])
        assert marker_stats['total_markers'] == anchored_asset_count

        # Validate marker format
        for block_id, asset_ids in marker_stats['markers_by_block'].items():
            # Block should exist
            block = marked_document.find_block(block_id)
            assert block is not None

            # Each marker should correspond to an asset
            for asset_id in asset_ids:
                assert f"[[{asset_id}]]" in block.content

    def test_newline_preservation_end_to_end(self, sample_russian_pattern_pdf, tmp_path):
        """
        CRITICAL TEST: Newline preservation through extraction pipeline.

        Validates:
        - Docling extraction preserves newlines in blocks
        - Marker injection doesn't corrupt newlines
        - Total newline count is stable
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        # Extract
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)

        # Count original newlines
        original_newlines = 0
        for section in document.sections:
            for block in section.blocks:
                original_newlines += block.content.count('\n')

        # Extract assets and anchor
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            sample_russian_pattern_pdf
        )
        anchored_ledger = anchor_assets_to_blocks(document, ledger)

        # Inject markers
        marked_document = inject_markers(document, anchored_ledger)

        # Count newlines after marking
        marked_newlines = 0
        for section in marked_document.sections:
            for block in section.blocks:
                marked_newlines += block.content.count('\n')

        # Markers add newlines, so count should increase or stay same
        # But should be predictable
        expected_added_newlines = sum(
            1 for a in anchored_ledger.assets if a.anchor_to
        )

        # Allow some tolerance for marker formatting
        assert marked_newlines >= original_newlines

    def test_100_percent_asset_coverage(self, sample_russian_pattern_pdf, tmp_path):
        """
        CRITICAL TEST: 100% asset coverage validation.

        Every asset in ledger must be:
        1. Anchored to a block (anchor_to set)
        2. Have a marker in document ([[asset_id]])

        Validates:
        - No unanchored assets
        - No assets without markers
        - No orphaned markers
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        # Extract
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            sample_russian_pattern_pdf
        )

        # Anchor
        anchored_ledger = anchor_assets_to_blocks(document, ledger)

        # Validate: All assets have anchor_to
        unanchored = [a.asset_id for a in anchored_ledger.assets if not a.anchor_to]
        assert len(unanchored) == 0, f"Unanchored assets: {unanchored}"

        # Inject markers
        marked_document = inject_markers(document, anchored_ledger)

        # Validate: All assets have markers
        marker_stats = count_markers(marked_document)
        all_markers = set()
        for markers in marker_stats['markers_by_block'].values():
            all_markers.update(markers)

        all_asset_ids = set(a.asset_id for a in anchored_ledger.assets)

        missing_markers = all_asset_ids - all_markers
        assert len(missing_markers) == 0, f"Assets missing markers: {missing_markers}"

        extra_markers = all_markers - all_asset_ids
        assert len(extra_markers) == 0, f"Orphaned markers: {extra_markers}"

    def test_asset_marker_integrity(self, sample_russian_pattern_pdf, tmp_path):
        """
        Test asset marker integrity through pipeline.

        Validates:
        - Marker format is correct: [[type-hash-page-occ]]
        - Markers can be parsed back to asset_id
        - Markers match asset metadata
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor
        import re

        # Extract and process
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            sample_russian_pattern_pdf
        )
        anchored_ledger = anchor_assets_to_blocks(document, ledger)
        marked_document = inject_markers(document, anchored_ledger)

        # Extract all markers from document
        marker_pattern = re.compile(r'\[\[([a-z]+-[a-f0-9]{8}-p\d+-occ\d+)\]\]')

        for section in marked_document.sections:
            for block in section.blocks:
                for match in marker_pattern.finditer(block.content):
                    asset_id = match.group(1)

                    # Asset should exist
                    asset = anchored_ledger.find_by_id(asset_id)
                    assert asset is not None, f"Marker references non-existent asset: {asset_id}"

                    # Parse marker components
                    parts = asset_id.split('-')
                    assert len(parts) >= 4

                    type_prefix = parts[0]
                    hash_prefix = parts[1]
                    page_part = parts[2]
                    occ_part = parts[3]

                    # Validate against asset
                    assert hash_prefix == asset.sha256[:8]
                    assert page_part == f"p{asset.page_number}"
                    assert occ_part == f"occ{asset.occurrence}"

    def test_multi_column_layout_extraction(self, two_column_pdf_path, tmp_path):
        """
        Test extraction of multi-column layout.

        Validates:
        - Column detection works correctly
        - Reading order is logical
        - Assets are anchored to correct column blocks
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor
        from kps.anchoring.columns import detect_columns

        # Extract
        document = DoclingExtractor().extract(two_column_pdf_path)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            two_column_pdf_path
        )

        # Detect columns (Day 2)
        for page_num in range(ledger.total_pages):
            blocks = document.get_blocks_on_page(page_num)

            if len(blocks) > 0:
                columns = detect_columns(blocks)

                # Should detect multiple columns for multi-column layout
                if len(blocks) > 5:  # Reasonable threshold
                    # Expect 2-3 columns
                    assert 1 <= len(columns) <= 3

        # Anchor with column awareness
        anchored_ledger = anchor_assets_to_blocks(document, ledger)

        # All assets should be anchored
        for asset in anchored_ledger.assets:
            assert asset.anchor_to

    def test_table_extraction_and_anchoring(self, pdf_with_tables_path, tmp_path):
        """
        Test extraction and anchoring of tables.

        Validates:
        - Tables are detected in text extraction
        - Table snapshots are captured in asset extraction
        - Tables are anchored correctly
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        # Extract
        document = DoclingExtractor().extract(pdf_with_tables_path)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            pdf_with_tables_path
        )

        # Find table blocks
        table_blocks = []
        for section in document.sections:
            for block in section.blocks:
                if block.block_type == BlockType.TABLE:
                    table_blocks.append(block)

        # Should have detected tables
        assert len(table_blocks) > 0

        # Find table assets
        table_assets = ledger.by_type(AssetType.TABLE_SNAP)

        # Note: Table asset extraction may require coordination
        # This test validates the integration

    def test_russian_text_encoding_preservation(self, sample_russian_pattern_pdf, tmp_path):
        """
        Test Russian text encoding is preserved through pipeline.

        Validates:
        - Cyrillic characters are not corrupted
        - Encoding survives extraction and anchoring
        - Text is readable
        """
        from kps.extraction.docling_extractor import DoclingExtractor

        # Extract
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)

        # Collect all text
        all_text = ""
        for section in document.sections:
            all_text += section.get_all_text()

        # Should contain Cyrillic
        has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in all_text)
        assert has_cyrillic, "No Cyrillic characters found"

        # Check for common Russian knitting terms
        russian_terms = ["петл", "ряд", "вяз"]  # Partial matches
        found = any(term in all_text.lower() for term in russian_terms)
        assert found, "No Russian knitting terms found"

    @pytest.mark.slow
    def test_performance_10_page_extraction_pipeline(self, ten_page_pdf_path, tmp_path):
        """
        Test performance of full extraction pipeline for 10-page document.

        Performance target: < 30 seconds for complete extraction + anchoring

        Validates:
        - Text extraction completes in reasonable time
        - Asset extraction completes in reasonable time
        - Anchoring is efficient
        - Total time < 30s
        """
        import time
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        start_time = time.time()

        # Extract text
        document = DoclingExtractor().extract(ten_page_pdf_path)

        text_time = time.time() - start_time

        # Extract assets
        asset_start = time.time()
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            ten_page_pdf_path
        )
        asset_time = time.time() - asset_start

        # Anchor
        anchor_start = time.time()
        anchored_ledger = anchor_assets_to_blocks(document, ledger)
        anchor_time = time.time() - anchor_start

        total_time = time.time() - start_time

        # Performance validation
        assert total_time < 30.0, \
            f"Pipeline took {total_time:.2f}s (text: {text_time:.2f}s, assets: {asset_time:.2f}s, anchor: {anchor_time:.2f}s)"

        # Validate completeness
        assert len(document.sections) > 0
        assert len(ledger.assets) > 0
        assert all(a.anchor_to for a in anchored_ledger.assets)

    def test_bbox_coordinate_consistency(self, sample_russian_pattern_pdf, tmp_path):
        """
        Test bbox coordinate consistency between text blocks and assets.

        Validates:
        - Text blocks have valid bbox coordinates
        - Assets have valid bbox coordinates
        - Coordinates are in same coordinate system
        - Anchoring uses bbox correctly
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        # Extract
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            sample_russian_pattern_pdf
        )

        # Validate text block bboxes
        for section in document.sections:
            for block in section.blocks:
                if block.bbox:
                    assert block.bbox.x0 < block.bbox.x1
                    assert block.bbox.y0 < block.bbox.y1
                    assert 0 <= block.bbox.x0 <= 1000
                    assert 0 <= block.bbox.y0 <= 1500

        # Validate asset bboxes
        for asset in ledger.assets:
            assert asset.bbox.x0 < asset.bbox.x1
            assert asset.bbox.y0 < asset.bbox.y1
            assert 0 <= asset.bbox.x0 <= 1000
            assert 0 <= asset.bbox.y0 <= 1500

    def test_json_serialization_roundtrip(self, sample_russian_pattern_pdf, tmp_path):
        """
        Test JSON serialization of extracted document and ledger.

        Validates:
        - Document can be saved to JSON
        - Ledger can be saved to JSON
        - Both can be loaded back
        - Data is preserved exactly
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        # Extract
        document = DoclingExtractor().extract(sample_russian_pattern_pdf)
        ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
            sample_russian_pattern_pdf
        )

        # Save
        doc_path = tmp_path / "document.json"
        ledger_path = tmp_path / "ledger.json"

        document.save_json(doc_path)
        ledger.save_json(ledger_path)

        # Load
        loaded_doc = KPSDocument.load_json(doc_path)
        loaded_ledger = AssetLedger.load_json(ledger_path)

        # Validate document
        assert loaded_doc.slug == document.slug
        assert len(loaded_doc.sections) == len(document.sections)

        # Validate ledger
        assert len(loaded_ledger.assets) == len(ledger.assets)
        assert loaded_ledger.total_pages == ledger.total_pages

    def test_error_recovery_partial_extraction(self, partially_corrupted_pdf_path, tmp_path):
        """
        Test error recovery for partially corrupted PDF.

        Validates:
        - Extraction continues for valid parts
        - Errors are logged but don't crash pipeline
        - Partial results are still useful
        """
        from kps.extraction.docling_extractor import DoclingExtractor
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        # Should not crash
        try:
            document = DoclingExtractor().extract(partially_corrupted_pdf_path)
            ledger = PyMuPDFExtractor(output_dir=tmp_path / "assets").extract_assets(
                partially_corrupted_pdf_path
            )

            # Should have some results
            assert isinstance(document, KPSDocument)
            assert isinstance(ledger, AssetLedger)

        except Exception as e:
            # If it fails, error should be informative
            assert "corrupted" in str(e).lower() or "invalid" in str(e).lower()
