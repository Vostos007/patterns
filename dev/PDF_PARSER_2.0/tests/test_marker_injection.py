"""
Tests for marker injection functionality.

Validates that [[asset_id]] markers are correctly injected into ContentBlocks
based on anchored assets, with proper positioning per block type.
"""

import pytest
from pathlib import Path

from kps.anchoring.markers import (
    MarkerInjectionError,
    count_markers,
    extract_existing_markers,
    find_injection_position,
    format_marker,
    inject_markers,
    inject_markers_into_block,
    validate_marker,
)
from kps.core.assets import Asset, AssetLedger, AssetType
from kps.core.bbox import BBox
from kps.core.document import (
    BlockType,
    ContentBlock,
    DocumentMetadata,
    KPSDocument,
    Section,
    SectionType,
)


class TestMarkerFormatting:
    """Test marker formatting and validation."""

    def test_format_marker(self):
        """Test basic marker formatting."""
        asset_id = "img-abc123-p3-occ1"
        marker = format_marker(asset_id)
        assert marker == "[[img-abc123-p3-occ1]]\n"

    def test_validate_marker_valid(self):
        """Test validation of valid markers."""
        valid_markers = [
            "[[img-abc123-p3-occ1]]",
            "[[vec-xyz789-p1-occ2]]",
            "[[tbl-snap-def456-p5-occ1]]",
            "[[table_live-ghi789-p2-occ1]]",
        ]
        for marker in valid_markers:
            assert validate_marker(marker), f"Should be valid: {marker}"

    def test_validate_marker_invalid(self):
        """Test validation rejects invalid markers."""
        invalid_markers = [
            "[img-abc123]",  # Single brackets
            "[[img abc123]]",  # Spaces
            "[[IMG-ABC123]]",  # Uppercase
            "[[img-abc123",  # Missing closing
            "img-abc123]]",  # Missing opening
            "",  # Empty
        ]
        for marker in invalid_markers:
            assert not validate_marker(marker), f"Should be invalid: {marker}"


class TestInjectionPosition:
    """Test finding correct injection positions for different block types."""

    def test_paragraph_injection_at_start(self):
        """PARAGRAPH blocks: inject at start."""
        block = ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="This is a paragraph about materials.",
        )
        pos = find_injection_position(block)
        assert pos == 0

    def test_heading_injection_after_text(self):
        """HEADING blocks: inject after heading text."""
        block = ContentBlock(
            block_id="h2.techniques.001",
            block_type=BlockType.HEADING,
            content="Knitting Techniques",
        )
        pos = find_injection_position(block)
        # Should be after content + newline
        assert pos == len(block.content.rstrip()) + 1

    def test_table_injection_at_start(self):
        """TABLE blocks: inject at start."""
        block = ContentBlock(
            block_id="tbl.sizes.001",
            block_type=BlockType.TABLE,
            content="Size | Chest | Length\nS | 90cm | 60cm",
        )
        pos = find_injection_position(block)
        assert pos == 0

    def test_list_injection_at_start(self):
        """LIST blocks: inject at start."""
        block = ContentBlock(
            block_id="list.materials.001",
            block_type=BlockType.LIST,
            content="- Yarn A\n- Yarn B\n- Needles",
        )
        pos = find_injection_position(block)
        assert pos == 0

    def test_figure_injection_replaces_content(self):
        """FIGURE blocks: marker replaces content."""
        block = ContentBlock(
            block_id="fig.instructions.001",
            block_type=BlockType.FIGURE,
            content="",
        )
        pos = find_injection_position(block)
        assert pos == 0


class TestExtractExistingMarkers:
    """Test extraction of existing markers from content."""

    def test_extract_no_markers(self):
        """Content with no markers returns empty set."""
        content = "This is plain text without any markers."
        markers = extract_existing_markers(content)
        assert markers == set()

    def test_extract_single_marker(self):
        """Extract single marker from content."""
        content = "[[img-abc123-p3-occ1]]\nThis is text with a marker."
        markers = extract_existing_markers(content)
        assert markers == {"img-abc123-p3-occ1"}

    def test_extract_multiple_markers(self):
        """Extract multiple markers from content."""
        content = """[[img-abc123-p3-occ1]]
[[vec-xyz789-p3-occ1]]
Text between markers.
[[tbl-snap-def456-p5-occ1]]
More text."""
        markers = extract_existing_markers(content)
        assert markers == {
            "img-abc123-p3-occ1",
            "vec-xyz789-p3-occ1",
            "tbl-snap-def456-p5-occ1",
        }


class TestInjectMarkersIntoBlock:
    """Test injecting markers into individual blocks."""

    def test_inject_single_asset_paragraph(self):
        """Inject single asset marker at start of paragraph."""
        block = ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="This is a paragraph.",
            bbox=BBox(50, 100, 550, 150),
            page_number=0,
        )

        asset = Asset(
            asset_id="img-abc123-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256="a" * 64,
            page_number=0,
            bbox=BBox(50, 50, 550, 90),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="p.materials.001",
            image_width=500,
            image_height=300,
        )

        modified = inject_markers_into_block(block, [asset])

        assert modified.content.startswith("[[img-abc123-p0-occ1]]\n")
        assert "This is a paragraph." in modified.content

    def test_inject_multiple_assets_ordered_by_y(self):
        """Multiple assets are ordered by y-coordinate (top to bottom)."""
        block = ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="This is a paragraph.",
            bbox=BBox(50, 100, 550, 200),
            page_number=0,
        )

        # Asset 1: Lower on page (higher y0)
        asset1 = Asset(
            asset_id="img-lower-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256="b" * 64,
            page_number=0,
            bbox=BBox(50, 150, 550, 180),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test2.png"),
            occurrence=1,
            anchor_to="p.materials.001",
            image_width=500,
            image_height=100,
        )

        # Asset 2: Higher on page (lower y0)
        asset2 = Asset(
            asset_id="img-higher-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256="c" * 64,
            page_number=0,
            bbox=BBox(50, 50, 550, 80),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test1.png"),
            occurrence=1,
            anchor_to="p.materials.001",
            image_width=500,
            image_height=100,
        )

        # Pass assets in wrong order
        modified = inject_markers_into_block(block, [asset1, asset2])

        # Should be ordered by y0 (lower y0 = higher on page = first)
        lines = modified.content.split("\n")
        assert "[[img-higher-p0-occ1]]" in lines[0]
        assert "[[img-lower-p0-occ1]]" in lines[1]

    def test_inject_heading_after_text(self):
        """Inject marker after heading text."""
        block = ContentBlock(
            block_id="h2.techniques.001",
            block_type=BlockType.HEADING,
            content="Materials",
        )

        asset = Asset(
            asset_id="img-xyz-p1-occ1",
            asset_type=AssetType.IMAGE,
            sha256="d" * 64,
            page_number=1,
            bbox=BBox(50, 50, 550, 90),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="h2.techniques.001",
            image_width=500,
            image_height=100,
        )

        modified = inject_markers_into_block(block, [asset])

        # Marker should be after heading
        assert modified.content == "Materials\n[[img-xyz-p1-occ1]]\n"

    def test_inject_skips_existing_markers(self):
        """Don't re-inject markers that already exist."""
        block = ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="[[img-abc123-p0-occ1]]\nThis paragraph already has a marker.",
        )

        asset = Asset(
            asset_id="img-abc123-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256="e" * 64,
            page_number=0,
            bbox=BBox(50, 50, 550, 90),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="p.materials.001",
            image_width=500,
            image_height=100,
        )

        modified = inject_markers_into_block(block, [asset])

        # Should not duplicate marker
        marker_count = modified.content.count("[[img-abc123-p0-occ1]]")
        assert marker_count == 1


class TestInjectMarkersFullDocument:
    """Test marker injection across entire document."""

    def test_inject_markers_full_document(self):
        """Test complete marker injection workflow."""
        # Create document
        metadata = DocumentMetadata(title="Test Pattern", language="ru")

        block1 = ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="You will need 200g of yarn.",
            bbox=BBox(50, 100, 550, 150),
            page_number=0,
        )

        block2 = ContentBlock(
            block_id="p.materials.002",
            block_type=BlockType.PARAGRAPH,
            content="Cast on 80 stitches.",
            bbox=BBox(50, 200, 550, 250),
            page_number=0,
        )

        section = Section(
            section_type=SectionType.MATERIALS,
            title="Materials",
            blocks=[block1, block2],
        )

        document = KPSDocument(slug="test-pattern", metadata=metadata, sections=[section])

        # Create assets
        asset1 = Asset(
            asset_id="img-yarn-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256="f" * 64,
            page_number=0,
            bbox=BBox(50, 50, 550, 90),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/yarn.png"),
            occurrence=1,
            anchor_to="p.materials.001",
            image_width=500,
            image_height=100,
        )

        asset2 = Asset(
            asset_id="img-needles-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256="1" * 64,
            page_number=0,
            bbox=BBox(50, 160, 550, 190),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/needles.png"),
            occurrence=1,
            anchor_to="p.materials.002",
            image_width=500,
            image_height=100,
        )

        ledger = AssetLedger(
            assets=[asset1, asset2], source_pdf=Path("/tmp/test.pdf"), total_pages=1
        )

        # Inject markers
        modified_doc = inject_markers(document, ledger)

        # Validate results
        block1_modified = modified_doc.sections[0].blocks[0]
        block2_modified = modified_doc.sections[0].blocks[1]

        assert block1_modified.content.startswith("[[img-yarn-p0-occ1]]\n")
        assert block2_modified.content.startswith("[[img-needles-p0-occ1]]\n")

    def test_inject_markers_validation_missing_marker(self):
        """Fail if an anchored asset doesn't get a marker."""
        metadata = DocumentMetadata(title="Test Pattern", language="ru")

        # Block exists but has empty content (edge case)
        block1 = ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="",
            bbox=BBox(50, 100, 550, 150),
            page_number=0,
        )

        section = Section(
            section_type=SectionType.MATERIALS, title="Materials", blocks=[block1]
        )

        document = KPSDocument(slug="test-pattern", metadata=metadata, sections=[section])

        # Asset anchored to non-existent block
        asset1 = Asset(
            asset_id="img-orphan-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256="2" * 64,
            page_number=0,
            bbox=BBox(50, 50, 550, 90),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="p.materials.999",  # Non-existent block
            image_width=500,
            image_height=100,
        )

        ledger = AssetLedger(
            assets=[asset1], source_pdf=Path("/tmp/test.pdf"), total_pages=1
        )

        # Should raise error: asset has no marker
        with pytest.raises(MarkerInjectionError, match="Assets missing markers"):
            inject_markers(document, ledger)

    def test_inject_markers_validation_duplicate_markers(self):
        """Fail if duplicate markers are found."""
        metadata = DocumentMetadata(title="Test Pattern", language="ru")

        # Both blocks have same marker (manually injected)
        block1 = ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="[[img-dupe-p0-occ1]]\nBlock 1",
            bbox=BBox(50, 100, 550, 150),
            page_number=0,
        )

        block2 = ContentBlock(
            block_id="p.materials.002",
            block_type=BlockType.PARAGRAPH,
            content="[[img-dupe-p0-occ1]]\nBlock 2",
            bbox=BBox(50, 200, 550, 250),
            page_number=0,
        )

        section = Section(
            section_type=SectionType.MATERIALS,
            title="Materials",
            blocks=[block1, block2],
        )

        document = KPSDocument(slug="test-pattern", metadata=metadata, sections=[section])

        asset1 = Asset(
            asset_id="img-dupe-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256="3" * 64,
            page_number=0,
            bbox=BBox(50, 50, 550, 90),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="p.materials.001",
            image_width=500,
            image_height=100,
        )

        ledger = AssetLedger(
            assets=[asset1], source_pdf=Path("/tmp/test.pdf"), total_pages=1
        )

        # Should raise error: duplicate markers
        with pytest.raises(MarkerInjectionError, match="Duplicate markers"):
            inject_markers(document, ledger)


class TestCountMarkers:
    """Test marker counting utility."""

    def test_count_markers_empty_document(self):
        """Count markers in document with no markers."""
        metadata = DocumentMetadata(title="Test Pattern", language="ru")

        block1 = ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="No markers here.",
        )

        section = Section(
            section_type=SectionType.MATERIALS, title="Materials", blocks=[block1]
        )

        document = KPSDocument(slug="test-pattern", metadata=metadata, sections=[section])

        stats = count_markers(document)

        assert stats["total_markers"] == 0
        assert stats["markers_by_block"] == {}
        assert stats["markers_by_section"] == {}

    def test_count_markers_with_data(self):
        """Count markers in document with multiple markers."""
        metadata = DocumentMetadata(title="Test Pattern", language="ru")

        block1 = ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="[[img-abc-p0-occ1]]\n[[img-xyz-p0-occ1]]\nTwo markers.",
        )

        block2 = ContentBlock(
            block_id="p.instructions.001",
            block_type=BlockType.PARAGRAPH,
            content="[[vec-def-p1-occ1]]\nOne marker.",
        )

        section1 = Section(
            section_type=SectionType.MATERIALS, title="Materials", blocks=[block1]
        )

        section2 = Section(
            section_type=SectionType.INSTRUCTIONS, title="Instructions", blocks=[block2]
        )

        document = KPSDocument(
            slug="test-pattern", metadata=metadata, sections=[section1, section2]
        )

        stats = count_markers(document)

        assert stats["total_markers"] == 3
        assert stats["markers_by_block"] == {
            "p.materials.001": ["img-abc-p0-occ1", "img-xyz-p0-occ1"],
            "p.instructions.001": ["vec-def-p1-occ1"],
        }
        assert stats["markers_by_section"] == {"materials": 2, "instructions": 1}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
