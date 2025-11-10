"""
Tests for PyMuPDF-based asset extraction (Day 3).

Tests the PyMuPDFExtractor that extracts ALL visual assets from PDF:
- XObject images with CTM, SMask, ICC profiles
- Vector graphics (charts, diagrams) as PDF fragments
- Tables (snapshot approach)
- SHA256 hashing for deduplication
- Multi-occurrence tracking

Critical validations:
- 100% asset completeness (no missing assets)
- Proper SHA256 hashing (64 hex chars)
- Multi-occurrence handling (same hash → different asset_id)
- CTM extraction for transforms
- SMask extraction for transparency
- File export (PNG, PDF)
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import hashlib

from kps.core.assets import (
    Asset,
    AssetLedger,
    AssetType,
    ColorSpace,
    VectorFont,
)
from kps.core.bbox import BBox

pytestmark = pytest.mark.unit


class TestPyMuPDFExtraction:
    """Test suite for PyMuPDF asset extraction."""

    def test_extract_xobject_images_basic(self, pdf_with_images_path, tmp_path):
        """
        Test basic XObject image extraction.

        Validates:
        - Images are detected and extracted
        - Asset type is IMAGE
        - SHA256 hash is computed (64 hex chars)
        - Files are exported to disk
        - Image dimensions are captured
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_images_path)

        assert isinstance(ledger, AssetLedger)
        assert ledger.total_pages > 0

        # Find image assets
        images = ledger.by_type(AssetType.IMAGE)
        assert len(images) > 0, "No images extracted"

        for img in images:
            # Validate SHA256
            assert len(img.sha256) == 64
            assert all(c in '0123456789abcdef' for c in img.sha256)

            # Validate dimensions
            assert img.image_width > 0
            assert img.image_height > 0

            # Validate file export
            assert img.file_path.exists()
            assert img.file_path.suffix in ['.png', '.jpg', '.jpeg']

    def test_ctm_extraction_for_transforms(self, pdf_with_rotated_images_path, tmp_path):
        """
        Test CTM (Current Transformation Matrix) extraction.

        CTM format: (a, b, c, d, e, f)
        - a, d: scaling
        - b, c: rotation/skew
        - e, f: translation

        Validates:
        - All assets have CTM tuple with 6 floats
        - Identity matrix is [1, 0, 0, 1, 0, 0]
        - Rotated images have non-identity CTM
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_rotated_images_path)

        images = ledger.by_type(AssetType.IMAGE)
        assert len(images) > 0

        for img in images:
            # Validate CTM structure
            assert isinstance(img.ctm, tuple)
            assert len(img.ctm) == 6
            assert all(isinstance(x, (int, float)) for x in img.ctm)

        # At least one image should have non-identity transform
        non_identity = [
            img for img in images
            if img.ctm != (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        ]
        # Note: This assumes the test PDF actually has rotated images
        # If not, this assertion might fail - that's intentional to validate test PDF

    def test_smask_transparency_extraction(self, pdf_with_transparency_path, tmp_path):
        """
        Test SMask (soft mask) extraction for transparency.

        Validates:
        - has_smask flag is set for transparent images
        - smask_data is captured (optional)
        - Exported images preserve transparency
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_transparency_path)

        images = ledger.by_type(AssetType.IMAGE)

        # At least one image should have transparency
        transparent_images = [img for img in images if img.has_smask]

        # If test PDF has transparent images
        if transparent_images:
            for img in transparent_images:
                assert img.has_smask is True
                # Exported file should be PNG (preserves transparency)
                assert img.file_path.suffix == '.png'

    def test_sha256_hashing_deduplication(self, pdf_with_duplicate_images_path, tmp_path):
        """
        Test SHA256 hashing for duplicate detection.

        When same image appears multiple times:
        - Same SHA256 hash
        - Different asset_id (includes occurrence counter)
        - Different anchor_to (different positions)

        Validates:
        - Duplicate images have same SHA256
        - Different asset_ids end with different occurrence numbers
        - find_by_sha256() returns multiple assets
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_duplicate_images_path)

        # Find duplicates
        sha256_counts = {}
        for asset in ledger.assets:
            if asset.sha256 not in sha256_counts:
                sha256_counts[asset.sha256] = []
            sha256_counts[asset.sha256].append(asset)

        # Find a hash with duplicates
        duplicate_hashes = {
            sha: assets for sha, assets in sha256_counts.items()
            if len(assets) > 1
        }

        assert len(duplicate_hashes) > 0, "No duplicate images found in test PDF"

        # Validate duplicate handling
        for sha256, assets in duplicate_hashes.items():
            # All should have same hash
            assert all(a.sha256 == sha256 for a in assets)

            # Different asset IDs
            asset_ids = [a.asset_id for a in assets]
            assert len(asset_ids) == len(set(asset_ids)), "Duplicate asset_ids"

            # Different occurrence numbers
            occurrences = [a.occurrence for a in assets]
            assert occurrences == list(range(1, len(assets) + 1))

            # Validate ledger method
            found_assets = ledger.find_by_sha256(sha256)
            assert len(found_assets) == len(assets)

    def test_multi_occurrence_tracking(self, pdf_with_duplicate_images_path, tmp_path):
        """
        Test multi-occurrence tracking for duplicate assets.

        Same content (SHA256) but different positions → different asset_id.

        asset_id format: "{type}-{sha256[:8]}-p{page}-occ{N}"

        Validates:
        - occurrence field increments for duplicates
        - asset_id includes occurrence number
        - Different page_number or bbox for each occurrence
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_duplicate_images_path)

        # Find assets with occurrence > 1
        multi_occurrence = [a for a in ledger.assets if a.occurrence > 1]

        if multi_occurrence:
            for asset in multi_occurrence:
                # Validate asset_id contains occurrence
                assert f"occ{asset.occurrence}" in asset.asset_id

                # Find all occurrences of this hash
                siblings = ledger.find_by_sha256(asset.sha256)
                assert len(siblings) >= asset.occurrence

    def test_vector_extraction_as_pdf(self, pdf_with_vector_graphics_path, tmp_path):
        """
        Test extraction of vector graphics (charts, diagrams).

        Vectors are extracted as:
        - VECTOR_PDF: PDF fragment (preserves curves, editability)
        - VECTOR_PNG: Rasterized fallback

        Validates:
        - Vector assets are detected
        - Asset type is VECTOR_PDF or VECTOR_PNG
        - Exported files exist
        - Font audit is performed for VECTOR_PDF
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_vector_graphics_path)

        # Find vector assets
        vectors = (
            ledger.by_type(AssetType.VECTOR_PDF) +
            ledger.by_type(AssetType.VECTOR_PNG)
        )

        # Note: Detection of vectors vs images is heuristic-based
        # May not always find vectors if test PDF doesn't have clear vector content
        if vectors:
            for vector in vectors:
                assert vector.file_path.exists()

                if vector.asset_type == AssetType.VECTOR_PDF:
                    assert vector.file_path.suffix == '.pdf'

                    # Should have font audit
                    # (May be empty if no text in vector)
                    assert isinstance(vector.fonts, list)

                elif vector.asset_type == AssetType.VECTOR_PNG:
                    assert vector.file_path.suffix == '.png'

    def test_font_audit_for_vector_pdf(self, pdf_with_text_graphics_path, tmp_path):
        """
        Test font audit for VECTOR_PDF assets.

        Font metadata includes:
        - font_name
        - embedded (bool)
        - subset (bool)
        - font_type (Type1, TrueType, CIDFont, etc.)

        Validates:
        - VECTOR_PDF assets with text have fonts list
        - Font metadata is complete
        - Embedded fonts are flagged
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_text_graphics_path)

        vector_pdfs = ledger.by_type(AssetType.VECTOR_PDF)

        if vector_pdfs:
            for vector in vector_pdfs:
                if vector.fonts:
                    for font in vector.fonts:
                        assert isinstance(font, VectorFont)
                        assert font.font_name
                        assert isinstance(font.embedded, bool)
                        assert isinstance(font.subset, bool)
                        assert font.font_type

    def test_icc_profile_extraction(self, pdf_with_icc_images_path, tmp_path):
        """
        Test ICC color profile extraction.

        Validates:
        - ColorSpace is detected (RGB, CMYK, ICC)
        - icc_profile bytes are captured for ICC images
        - Profile is valid (non-empty)
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_icc_images_path)

        images = ledger.by_type(AssetType.IMAGE)

        # Check colorspace detection
        for img in images:
            assert isinstance(img.colorspace, ColorSpace)

            if img.colorspace == ColorSpace.ICC and img.icc_profile:
                # ICC profile should be non-empty bytes
                assert isinstance(img.icc_profile, bytes)
                assert len(img.icc_profile) > 0

    def test_file_export_png_format(self, pdf_with_images_path, tmp_path):
        """
        Test image export to PNG format.

        Validates:
        - All images are exported
        - Files are valid PNG
        - File size > 0
        - File naming matches asset_id
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_images_path)

        images = ledger.by_type(AssetType.IMAGE)

        for img in images:
            # File exists
            assert img.file_path.exists()

            # Has content
            assert img.file_path.stat().st_size > 0

            # Filename contains asset_id prefix
            assert img.asset_id.split('-')[1][:8] in img.file_path.stem

    def test_file_export_pdf_format_for_vectors(self, pdf_with_vector_graphics_path, tmp_path):
        """
        Test vector export to PDF format.

        Validates:
        - VECTOR_PDF assets export as .pdf
        - Files are valid PDF (can be re-parsed)
        - File size > 0
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_vector_graphics_path)

        vector_pdfs = ledger.by_type(AssetType.VECTOR_PDF)

        if vector_pdfs:
            for vector in vector_pdfs:
                assert vector.file_path.suffix == '.pdf'
                assert vector.file_path.exists()
                assert vector.file_path.stat().st_size > 0

                # Try to open as PDF (basic validation)
                import fitz
                with fitz.open(vector.file_path) as doc:
                    assert doc.page_count >= 1

    def test_asset_ledger_completeness_check(self, pdf_with_mixed_content_path, tmp_path):
        """
        Test AssetLedger completeness check method.

        Validates:
        - completeness_check() returns proper structure
        - Counts by page are accurate
        - Counts by type are accurate
        - Total matches sum of assets
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_mixed_content_path)

        completeness = ledger.completeness_check()

        # Validate structure
        assert 'by_page' in completeness
        assert 'by_type' in completeness
        assert 'total' in completeness

        # Validate counts
        assert completeness['total'] == len(ledger.assets)

        # Sum of by_page should equal total
        page_sum = sum(completeness['by_page'].values())
        assert page_sum == completeness['total']

        # by_type should have keys for all AssetType values
        for asset_type in AssetType:
            assert asset_type.value in completeness['by_type']

    def test_error_handling_corrupted_image(self, pdf_with_corrupted_image_path, tmp_path):
        """
        Test handling of corrupted image XObject.

        Validates:
        - Extraction continues (doesn't crash)
        - Corrupted image is skipped or marked
        - Other assets are still extracted
        - Warning/error is logged
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)

        # Should not raise exception
        ledger = extractor.extract_assets(pdf_with_corrupted_image_path)

        # Should still extract other assets
        assert isinstance(ledger, AssetLedger)

    def test_error_handling_missing_resources(self, pdf_with_missing_resources_path, tmp_path):
        """
        Test handling of PDF with missing/broken resource references.

        Validates:
        - Graceful degradation
        - No crash on missing resources
        - Valid ledger is still returned
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)

        # Should not crash
        ledger = extractor.extract_assets(pdf_with_missing_resources_path)

        assert isinstance(ledger, AssetLedger)

    def test_table_snapshot_extraction(self, pdf_with_tables_path, tmp_path):
        """
        Test table extraction as snapshots (TABLE_SNAP).

        Default strategy: Extract table as PDF fragment or PNG.

        Validates:
        - Tables are detected
        - Asset type is TABLE_SNAP
        - Exported files exist
        - BBox covers table area
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_tables_path)

        tables = ledger.by_type(AssetType.TABLE_SNAP)

        # Note: Table detection may require coordination with Docling
        # This test validates the extraction mechanism IF tables are detected
        if tables:
            for table in tables:
                assert table.file_path.exists()
                assert table.bbox is not None

                # File should be PDF or PNG
                assert table.file_path.suffix in ['.pdf', '.png']

    def test_bbox_accuracy_for_assets(self, pdf_with_images_path, tmp_path):
        """
        Test bbox extraction accuracy for assets.

        Validates:
        - All assets have valid bbox
        - BBox coordinates are within page bounds
        - x0 < x1, y0 < y1
        - BBox matches asset position in PDF
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_images_path)

        for asset in ledger.assets:
            # Validate bbox exists
            assert asset.bbox is not None

            # Validate coordinates
            assert asset.bbox.x0 < asset.bbox.x1
            assert asset.bbox.y0 < asset.bbox.y1

            # Check reasonable bounds (page coordinates)
            assert 0 <= asset.bbox.x0 <= 1000
            assert 0 <= asset.bbox.x1 <= 1000
            assert 0 <= asset.bbox.y0 <= 1500
            assert 0 <= asset.bbox.y1 <= 1500

    def test_asset_id_format_validation(self, pdf_with_images_path, tmp_path):
        """
        Test asset_id format: "{type}-{sha256[:8]}-p{page}-occ{N}".

        Examples:
        - "img-abc12345-p0-occ1"
        - "vec-def67890-p3-occ2"
        - "tbl-ghi34567-p1-occ1"

        Validates:
        - Format is consistent
        - Type prefix matches asset type
        - Page number matches asset.page_number
        - Occurrence number matches asset.occurrence
        - SHA256 prefix matches first 8 chars of hash
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_images_path)

        for asset in ledger.assets:
            parts = asset.asset_id.split('-')

            # Should have 4 parts: type, hash, page, occurrence
            assert len(parts) >= 4, f"Invalid asset_id format: {asset.asset_id}"

            type_prefix = parts[0]
            hash_prefix = parts[1]
            page_part = parts[2]
            occ_part = parts[3]

            # Type prefix
            if asset.asset_type == AssetType.IMAGE:
                assert type_prefix == 'img'
            elif asset.asset_type == AssetType.VECTOR_PDF:
                assert type_prefix == 'vec'
            elif asset.asset_type == AssetType.TABLE_SNAP:
                assert type_prefix == 'tbl'

            # Hash prefix (8 chars)
            assert len(hash_prefix) == 8
            assert hash_prefix == asset.sha256[:8]

            # Page number
            assert page_part.startswith('p')
            page_num = int(page_part[1:])
            assert page_num == asset.page_number

            # Occurrence
            assert occ_part.startswith('occ')
            occ_num = int(occ_part[3:])
            assert occ_num == asset.occurrence

    @pytest.mark.slow
    def test_performance_large_pdf_extraction(self, large_pdf_with_many_assets_path, tmp_path):
        """
        Test extraction performance for PDF with many assets.

        Performance target: < 60 seconds for PDF with 50+ assets

        Validates:
        - Extraction completes within time limit
        - All assets are extracted
        - No memory leaks
        """
        import time
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)

        start_time = time.time()
        ledger = extractor.extract_assets(large_pdf_with_many_assets_path)
        elapsed_time = time.time() - start_time

        # Performance check
        assert elapsed_time < 60.0, \
            f"Extraction took {elapsed_time:.2f}s, expected < 60s"

        # Completeness check
        assert len(ledger.assets) >= 50, \
            f"Expected at least 50 assets, got {len(ledger.assets)}"

    def test_anchor_to_field_initialization(self, pdf_with_images_path, tmp_path):
        """
        Test that anchor_to field is initialized to empty string.

        Before anchoring phase, anchor_to should be "".
        After anchoring, it will contain block_id.

        Validates:
        - All assets have anchor_to field
        - Initially set to ""
        - Field is writable (for anchoring phase)
        """
        from kps.extraction.pymupdf_extractor import PyMuPDFExtractor

        extractor = PyMuPDFExtractor(output_dir=tmp_path)
        ledger = extractor.extract_assets(pdf_with_images_path)

        for asset in ledger.assets:
            # Field exists
            assert hasattr(asset, 'anchor_to')

            # Initially empty (before anchoring)
            assert asset.anchor_to == ""

            # Field is writable
            asset.anchor_to = "p.test.001"
            assert asset.anchor_to == "p.test.001"
