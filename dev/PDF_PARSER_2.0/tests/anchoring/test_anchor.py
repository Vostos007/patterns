"""Tests for asset-to-block anchoring algorithm."""

import pytest
from pathlib import Path

from kps.core.assets import Asset, AssetLedger, AssetType, ColorSpace
from kps.core.document import (
    KPSDocument,
    DocumentMetadata,
    Section,
    SectionType,
    ContentBlock,
    BlockType,
)
from kps.core.bbox import BBox, NormalizedBBox
from kps.anchoring.columns import Column
from kps.anchoring.anchor import (
    compute_normalized_bbox,
    find_nearest_block,
    anchor_assets_to_blocks,
    validate_geometry_preservation,
)


class TestComputeNormalizedBBox:
    """Tests for compute_normalized_bbox function."""

    def test_basic_normalization(self):
        """Test basic coordinate normalization."""
        # Asset: (60, 110, 160, 210) - 100x100 box
        # Column: (50, 100, 250, 700) - 200x600 box
        asset = Asset(
            asset_id="test-asset-1",
            asset_type=AssetType.IMAGE,
            sha256="a" * 64,
            page_number=0,
            bbox=BBox(60, 110, 160, 210),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="",
            image_width=100,
            image_height=100,
        )

        column = Column(
            column_id=0,
            x_min=50,
            x_max=250,
            y_min=100,
            y_max=700,
            blocks=[],
        )

        normalized = compute_normalized_bbox(asset, column)

        # Expected values:
        # x = (60 - 50) / (250 - 50) = 10 / 200 = 0.05
        # y = (110 - 100) / (700 - 100) = 10 / 600 = 0.0167
        # w = 100 / 200 = 0.5
        # h = 100 / 600 = 0.1667

        assert abs(normalized.x - 0.05) < 0.001
        assert abs(normalized.y - 0.0167) < 0.001
        assert abs(normalized.w - 0.5) < 0.001
        assert abs(normalized.h - 0.1667) < 0.001

    def test_top_left_corner(self):
        """Test asset at top-left corner of column."""
        asset = Asset(
            asset_id="test-asset-2",
            asset_type=AssetType.IMAGE,
            sha256="b" * 64,
            page_number=0,
            bbox=BBox(50, 100, 100, 150),  # Same as column top-left
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="",
            image_width=50,
            image_height=50,
        )

        column = Column(
            column_id=0,
            x_min=50,
            x_max=250,
            y_min=100,
            y_max=700,
            blocks=[],
        )

        normalized = compute_normalized_bbox(asset, column)

        # Should be at origin (0, 0)
        assert normalized.x == 0.0
        assert normalized.y == 0.0

    def test_zero_column_width_raises_error(self):
        """Test that zero column width raises ValueError."""
        asset = Asset(
            asset_id="test-asset-3",
            asset_type=AssetType.IMAGE,
            sha256="c" * 64,
            page_number=0,
            bbox=BBox(50, 100, 100, 150),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="",
            image_width=50,
            image_height=50,
        )

        # Column with zero width
        column = Column(
            column_id=0,
            x_min=50,
            x_max=50,  # Same as x_min
            y_min=100,
            y_max=700,
            blocks=[],
        )

        with pytest.raises(ValueError, match="Column width must be positive"):
            compute_normalized_bbox(asset, column)


class TestFindNearestBlock:
    """Tests for find_nearest_block function."""

    def test_prefer_block_below(self):
        """Test that algorithm prefers blocks below asset."""
        asset = Asset(
            asset_id="test-asset-4",
            asset_type=AssetType.IMAGE,
            sha256="d" * 64,
            page_number=0,
            bbox=BBox(100, 200, 200, 300),  # Asset at y=200-300
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="",
            image_width=100,
            image_height=100,
        )

        blocks = [
            ContentBlock(
                block_id="block-below",
                block_type=BlockType.PARAGRAPH,
                content="Text below",
                bbox=BBox(100, 310, 200, 330),  # 10pt below asset
                page_number=0,
            ),
            ContentBlock(
                block_id="block-above",
                block_type=BlockType.PARAGRAPH,
                content="Text above",
                bbox=BBox(100, 150, 200, 190),  # 10pt above asset
                page_number=0,
            ),
        ]

        nearest = find_nearest_block(asset, blocks, prefer_below=True)

        assert nearest is not None
        assert nearest.block_id == "block-below"

    def test_fallback_to_above_when_no_blocks_below(self):
        """Test fallback to blocks above when none below."""
        asset = Asset(
            asset_id="test-asset-5",
            asset_type=AssetType.IMAGE,
            sha256="e" * 64,
            page_number=0,
            bbox=BBox(100, 500, 200, 600),  # Asset at bottom
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="",
            image_width=100,
            image_height=100,
        )

        blocks = [
            ContentBlock(
                block_id="block-above-1",
                block_type=BlockType.PARAGRAPH,
                content="Text above 1",
                bbox=BBox(100, 400, 200, 420),
                page_number=0,
            ),
            ContentBlock(
                block_id="block-above-2",
                block_type=BlockType.PARAGRAPH,
                content="Text above 2",
                bbox=BBox(100, 200, 200, 220),
                page_number=0,
            ),
        ]

        nearest = find_nearest_block(asset, blocks, prefer_below=True)

        assert nearest is not None
        # Should select nearest above (block-above-1)
        assert nearest.block_id == "block-above-1"

    def test_column_constraint(self):
        """Test that column constraint filters blocks correctly."""
        asset = Asset(
            asset_id="test-asset-6",
            asset_type=AssetType.IMAGE,
            sha256="f" * 64,
            page_number=0,
            bbox=BBox(350, 200, 450, 300),  # Asset in right column
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="",
            image_width=100,
            image_height=100,
        )

        # Define right column
        right_column = Column(
            column_id=1,
            x_min=300,
            x_max=500,
            y_min=0,
            y_max=700,
            blocks=[],
        )

        blocks = [
            ContentBlock(
                block_id="left-column-block",
                block_type=BlockType.PARAGRAPH,
                content="Text in left column",
                bbox=BBox(50, 310, 150, 330),  # Left column
                page_number=0,
            ),
            ContentBlock(
                block_id="right-column-block",
                block_type=BlockType.PARAGRAPH,
                content="Text in right column",
                bbox=BBox(350, 310, 450, 330),  # Right column
                page_number=0,
            ),
        ]

        nearest = find_nearest_block(asset, blocks, same_column=right_column)

        assert nearest is not None
        # Should only select block in right column
        assert nearest.block_id == "right-column-block"


class TestAnchorAssetsToBlocks:
    """Tests for anchor_assets_to_blocks function."""

    def test_full_anchoring_workflow(self):
        """Test complete anchoring workflow with multiple assets."""
        # Create test document
        blocks = [
            ContentBlock(
                block_id="p.intro.001",
                block_type=BlockType.PARAGRAPH,
                content="Introduction text",
                bbox=BBox(50, 100, 250, 150),
                page_number=0,
            ),
            ContentBlock(
                block_id="p.intro.002",
                block_type=BlockType.PARAGRAPH,
                content="More text below",
                bbox=BBox(50, 250, 250, 300),
                page_number=0,
            ),
        ]

        document = KPSDocument(
            slug="test-pattern",
            metadata=DocumentMetadata(title="Test Pattern"),
            sections=[
                Section(
                    section_type=SectionType.MATERIALS,
                    title="Introduction",
                    blocks=blocks,
                )
            ],
        )

        # Create test assets
        assets = [
            Asset(
                asset_id="img-test-001",
                asset_type=AssetType.IMAGE,
                sha256="1" * 64,
                page_number=0,
                bbox=BBox(100, 160, 200, 240),  # Between the two blocks
                ctm=(1, 0, 0, 1, 0, 0),
                file_path=Path("/tmp/test1.png"),
                occurrence=1,
                anchor_to="",
                image_width=100,
                image_height=80,
            ),
        ]

        ledger = AssetLedger(
            assets=assets,
            source_pdf=Path("/tmp/test.pdf"),
            total_pages=1,
        )

        # Run anchoring
        anchored_ledger, report = anchor_assets_to_blocks(ledger, document)

        # Verify results
        assert report.total_assets == 1
        assert report.anchored_assets == 1
        assert len(report.unanchored_assets) == 0
        assert report.success_rate == 1.0

        # Check that anchor_to was set
        assert anchored_ledger.assets[0].anchor_to != ""
        # Should anchor to block below (p.intro.002)
        assert anchored_ledger.assets[0].anchor_to == "p.intro.002"

    def test_multi_column_anchoring(self):
        """Test anchoring with multi-column layout."""
        # Create two-column layout
        left_blocks = [
            ContentBlock(
                block_id="p.left.001",
                block_type=BlockType.PARAGRAPH,
                content="Left column text",
                bbox=BBox(50, 100, 200, 150),
                page_number=0,
            ),
        ]

        right_blocks = [
            ContentBlock(
                block_id="p.right.001",
                block_type=BlockType.PARAGRAPH,
                content="Right column text",
                bbox=BBox(300, 100, 450, 150),
                page_number=0,
            ),
        ]

        document = KPSDocument(
            slug="test-pattern",
            metadata=DocumentMetadata(title="Test Pattern"),
            sections=[
                Section(
                    section_type=SectionType.MATERIALS,
                    title="Content",
                    blocks=left_blocks + right_blocks,
                )
            ],
        )

        # Create assets in both columns
        assets = [
            Asset(
                asset_id="img-left",
                asset_type=AssetType.IMAGE,
                sha256="2" * 64,
                page_number=0,
                bbox=BBox(75, 160, 175, 200),  # Left column
                ctm=(1, 0, 0, 1, 0, 0),
                file_path=Path("/tmp/left.png"),
                occurrence=1,
                anchor_to="",
                image_width=100,
                image_height=40,
            ),
            Asset(
                asset_id="img-right",
                asset_type=AssetType.IMAGE,
                sha256="3" * 64,
                page_number=0,
                bbox=BBox(325, 160, 425, 200),  # Right column
                ctm=(1, 0, 0, 1, 0, 0),
                file_path=Path("/tmp/right.png"),
                occurrence=1,
                anchor_to="",
                image_width=100,
                image_height=40,
            ),
        ]

        ledger = AssetLedger(
            assets=assets,
            source_pdf=Path("/tmp/test.pdf"),
            total_pages=1,
        )

        # Run anchoring
        anchored_ledger, report = anchor_assets_to_blocks(ledger, document)

        # Verify results
        assert report.total_assets == 2
        assert report.anchored_assets == 2
        assert report.success_rate == 1.0

        # Each asset should anchor to block in same column
        left_asset = anchored_ledger.find_by_id("img-left")
        right_asset = anchored_ledger.find_by_id("img-right")

        assert left_asset.anchor_to == "p.left.001"
        assert right_asset.anchor_to == "p.right.001"


class TestValidateGeometryPreservation:
    """Tests for validate_geometry_preservation function."""

    def test_valid_geometry(self):
        """Test validation of valid geometry."""
        asset = Asset(
            asset_id="test-asset-7",
            asset_type=AssetType.IMAGE,
            sha256="g" * 64,
            page_number=0,
            bbox=BBox(60, 110, 160, 210),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="",
            image_width=100,
            image_height=100,
        )

        column = Column(
            column_id=0,
            x_min=50,
            x_max=250,
            y_min=100,
            y_max=700,
            blocks=[],
        )

        is_valid, deviation = validate_geometry_preservation(
            asset, column, tolerance_pt=2.0, tolerance_pct=0.01
        )

        assert is_valid
        assert deviation < 0.02  # Within 2% tolerance
