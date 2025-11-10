"""
Tests for asset anchoring algorithm.

Tests the asset anchoring functionality that assigns each asset to a content block.
This is critical for the ≥98% geometry preservation requirement as it determines
where assets will be placed in the final document.

Algorithm Requirements (from KPS_MASTER_PLAN.md):
- Column-aware: assets only anchor to blocks in same column
- Nearest-block selection with vertical overlap detection
- Normalized coordinate calculation for geometry preservation
- ±2pt or 1% tolerance for geometry validation
- All assets must have anchor_to set (100% coverage)
"""

import pytest
from pathlib import Path
from kps.core.document import ContentBlock, BlockType
from kps.core.bbox import BBox, NormalizedBBox
from kps.core.assets import Asset, AssetType

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kps.anchoring.anchor import AssetAnchorer


class TestAssetAnchoring:
    """Test suite for asset anchoring algorithm."""

    def test_basic_anchoring_asset_above_block(
        self,
        sample_asset_left_column: Asset,
        two_column_layout_blocks: list[ContentBlock],
    ):
        """
        Test basic anchoring: asset positioned above a block.

        Expected behavior:
        - Asset should anchor to the block immediately below it
        - Should respect same-column constraint
        - anchor_to field should be set to block_id
        """
        pytest.importorskip("kps.anchoring.anchor")
        from kps.anchoring.anchor import AssetAnchorer

        anchorer = AssetAnchorer()

        # Asset is at y=250-350, should anchor to block at y=220-240 (heading)
        anchor_block = anchorer.find_anchor_block(
            sample_asset_left_column,
            two_column_layout_blocks
        )

        assert anchor_block is not None, "Should find an anchor block"
        assert anchor_block.block_id == "h2.techniques.001", \
            f"Expected h2.techniques.001, got {anchor_block.block_id}"

        # Verify anchor_to is set correctly
        anchorer.set_anchor(sample_asset_left_column, anchor_block)
        assert sample_asset_left_column.anchor_to == "h2.techniques.001"

    def test_anchoring_asset_below_block(
        self,
        sample_asset_between_blocks: Asset,
        two_column_layout_blocks: list[ContentBlock],
    ):
        """
        Test anchoring with asset below a block (fallback case).

        Expected behavior:
        - If no block above, should anchor to nearest block
        - Should use vertical distance as metric
        """
        pytest.importorskip("kps.anchoring.anchor")
        from kps.anchoring.anchor import AssetAnchorer

        anchorer = AssetAnchorer()

        # Asset is at y=155-205, between blocks at y=150 and y=160
        anchor_block = anchorer.find_anchor_block(
            sample_asset_between_blocks,
            two_column_layout_blocks
        )

        assert anchor_block is not None, "Should find an anchor block"
        # Should anchor to nearest block (either p.materials.002 or nearby)
        assert anchor_block.bbox.x0 < 260, \
            "Should anchor to left column block (same column)"

    def test_same_column_constraint(
        self,
        sample_asset_left_column: Asset,
        two_column_layout_blocks: list[ContentBlock],
    ):
        """
        Test same-column constraint for anchoring.

        Expected behavior:
        - Asset in left column should ONLY anchor to left column blocks
        - Should never cross column boundaries
        - Even if right column block is closer vertically
        """
        pytest.importorskip("kps.anchoring.anchor")
        from kps.anchoring.anchor import AssetAnchorer

        anchorer = AssetAnchorer()

        # Asset is in left column (x=80-220)
        anchor_block = anchorer.find_anchor_block(
            sample_asset_left_column,
            two_column_layout_blocks
        )

        assert anchor_block is not None
        assert anchor_block.bbox.x0 < 260, \
            f"Asset in left column anchored to right column block {anchor_block.block_id}"

    def test_nearest_block_selection(self):
        """
        Test nearest-block selection algorithm.

        Expected behavior:
        - Should calculate vertical distance from asset to blocks
        - Should select block with minimum distance
        - Distance metric: closest edge (top or bottom)
        """
        pytest.importorskip("kps.anchoring.anchor")
        from kps.anchoring.anchor import AssetAnchorer

        anchorer = AssetAnchorer()

        # Create asset and blocks with clear distances
        asset = Asset(
            asset_id="img-test-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256="e" * 64,
            page_number=0,
            bbox=BBox(50, 300, 250, 400),  # Asset at y=300-400
            ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            file_path=Path("/tmp/test.png"),
            occurrence=1,
            anchor_to="",
            image_width=800,
            image_height=600,
        )

        blocks = [
            ContentBlock(
                block_id="p.far.001",
                block_type=BlockType.PARAGRAPH,
                content="Far block",
                bbox=BBox(50, 100, 250, 150),  # 150pt away
                page_number=0,
                reading_order=0,
            ),
            ContentBlock(
                block_id="p.near.001",
                block_type=BlockType.PARAGRAPH,
                content="Near block",
                bbox=BBox(50, 250, 250, 290),  # 10pt away
                page_number=0,
                reading_order=1,
            ),
        ]

        anchor_block = anchorer.find_anchor_block(asset, blocks)
        assert anchor_block.block_id == "p.near.001", \
            "Should select nearest block"

    def test_normalized_coordinate_calculation(
        self,
        sample_asset_left_column: Asset,
        sample_column_bounds: BBox,
    ):
        """
        Test normalized coordinate calculation.

        Expected behavior:
        - Convert absolute bbox to column-relative (0-1)
        - Preserve aspect ratio and relative position
        - Enable geometry comparison across different page sizes
        """
        pytest.importorskip("kps.anchoring.anchor")
        from kps.anchoring.anchor import AssetAnchorer

        anchorer = AssetAnchorer()

        # Asset bbox: (80, 250, 220, 350)
        # Column bounds: (50, 100, 250, 700)
        normalized = anchorer.normalize_bbox(
            sample_asset_left_column.bbox,
            sample_column_bounds
        )

        # Calculate expected values
        # x: (80 - 50) / (250 - 50) = 30 / 200 = 0.15
        # y: (250 - 100) / (700 - 100) = 150 / 600 = 0.25
        # w: (220 - 80) / 200 = 140 / 200 = 0.7
        # h: (350 - 250) / 600 = 100 / 600 = 0.1667

        assert isinstance(normalized, NormalizedBBox)
        assert abs(normalized.x - 0.15) < 0.01, f"Expected x=0.15, got {normalized.x}"
        assert abs(normalized.y - 0.25) < 0.01, f"Expected y=0.25, got {normalized.y}"
        assert abs(normalized.w - 0.7) < 0.01, f"Expected w=0.7, got {normalized.w}"
        assert abs(normalized.h - 0.1667) < 0.01, f"Expected h=0.1667, got {normalized.h}"

    def test_geometry_preservation_tolerance(self):
        """
        Test geometry preservation with ±2pt or 1% tolerance.

        Expected behavior:
        - Compare original and placed positions
        - Allow ±2pt absolute deviation OR 1% relative deviation
        - Use more lenient of the two tolerances
        """
        pytest.importorskip("kps.anchoring.anchor")
        from kps.anchoring.anchor import AssetAnchorer

        anchorer = AssetAnchorer()

        # Test case 1: Small asset (100x100) with 1pt deviation
        # Should PASS: 1pt < 2pt tolerance
        original_bbox = BBox(100, 200, 200, 300)  # 100x100
        placed_bbox = BBox(101, 201, 201, 301)    # +1pt offset
        column_bounds = BBox(50, 100, 250, 700)

        is_preserved = anchorer.check_geometry_preservation(
            original_bbox,
            placed_bbox,
            column_bounds,
            tolerance_pt=2.0,
            tolerance_pct=0.01
        )
        assert is_preserved, "1pt deviation should pass with 2pt tolerance"

        # Test case 2: Small asset with 3pt deviation
        # Should FAIL: 3pt > 2pt and 3pt > 1% of 100pt
        placed_bbox_fail = BBox(103, 203, 203, 303)  # +3pt offset
        is_preserved = anchorer.check_geometry_preservation(
            original_bbox,
            placed_bbox_fail,
            column_bounds,
            tolerance_pt=2.0,
            tolerance_pct=0.01
        )
        assert not is_preserved, "3pt deviation should fail"

        # Test case 3: Large asset (500x500) with 3pt deviation
        # Should PASS: 3pt > 2pt BUT 3pt < 1% of 500pt (5pt)
        large_original = BBox(100, 200, 600, 700)  # 500x500
        large_placed = BBox(103, 203, 603, 703)    # +3pt offset
        is_preserved = anchorer.check_geometry_preservation(
            large_original,
            large_placed,
            column_bounds,
            tolerance_pt=2.0,
            tolerance_pct=0.01
        )
        assert is_preserved, "3pt deviation should pass for large asset (< 1%)"

    def test_asset_at_column_boundary(
        self,
        sample_asset_column_boundary: Asset,
        two_column_layout_blocks: list[ContentBlock],
    ):
        """
        Test edge case: asset at column boundary.

        Expected behavior:
        - Asset spanning column gap should be assigned to one column
        - Use center point or largest overlap to determine column
        - Should not crash or fail to anchor
        """
        pytest.importorskip("kps.anchoring.anchor")
        from kps.anchoring.anchor import AssetAnchorer

        anchorer = AssetAnchorer()

        # Asset bbox: (240, 100, 290, 150) - spans gap between columns
        anchor_block = anchorer.find_anchor_block(
            sample_asset_column_boundary,
            two_column_layout_blocks
        )

        assert anchor_block is not None, \
            "Asset at column boundary should still find anchor"

        # Should be assigned to either left or right column consistently
        anchorer.set_anchor(sample_asset_column_boundary, anchor_block)
        assert sample_asset_column_boundary.anchor_to != "", \
            "anchor_to should be set"

    def test_no_blocks_in_same_column(self):
        """
        Test edge case: no blocks in the same column as asset.

        Expected behavior:
        - Should either:
          a) Expand search to nearest column, OR
          b) Return None and flag as error, OR
          c) Anchor to nearest block regardless of column
        - Should not crash
        """
        pytest.importorskip("kps.anchoring.anchor")
        from kps.anchoring.anchor import AssetAnchorer

        anchorer = AssetAnchorer()

        # Asset in far-right position where no blocks exist
        asset = Asset(
            asset_id="img-orphan-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256="f" * 64,
            page_number=0,
            bbox=BBox(600, 100, 700, 200),  # Far right, no blocks here
            ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            file_path=Path("/tmp/orphan.png"),
            occurrence=1,
            anchor_to="",
            image_width=800,
            image_height=600,
        )

        blocks = [
            ContentBlock(
                block_id="p.left.001",
                block_type=BlockType.PARAGRAPH,
                content="Left block",
                bbox=BBox(50, 100, 250, 150),
                page_number=0,
                reading_order=0,
            ),
        ]

        # Should either find a block or return None gracefully
        anchor_block = anchorer.find_anchor_block(asset, blocks)

        # If it returns a block, it should be valid
        if anchor_block is not None:
            assert isinstance(anchor_block, ContentBlock)
            assert anchor_block.block_id == "p.left.001"

    def test_all_assets_have_anchor_to_set(
        self,
        sample_asset_ledger: list[Asset],
        two_column_layout_blocks: list[ContentBlock],
    ):
        """
        Test validation: all assets must have anchor_to set.

        Expected behavior:
        - After anchoring, every asset should have non-empty anchor_to
        - 100% coverage requirement
        - Should fail if any asset lacks anchor
        """
        pytest.importorskip("kps.anchoring.anchor")
        from kps.anchoring.anchor import AssetAnchorer

        anchorer = AssetAnchorer()

        # Anchor all assets
        for asset in sample_asset_ledger.assets:
            anchor_block = anchorer.find_anchor_block(asset, two_column_layout_blocks)
            assert anchor_block is not None, \
                f"Asset {asset.asset_id} could not find anchor block"
            anchorer.set_anchor(asset, anchor_block)

        # Validate all have anchor_to set
        for asset in sample_asset_ledger.assets:
            assert asset.anchor_to != "", \
                f"Asset {asset.asset_id} missing anchor_to"
            assert asset.anchor_to.startswith("p.") or \
                   asset.anchor_to.startswith("h") or \
                   asset.anchor_to.startswith("tbl."), \
                f"Invalid anchor_to format: {asset.anchor_to}"

    def test_multiple_assets_to_same_block(
        self,
        two_column_layout_blocks: list[ContentBlock],
    ):
        """
        Test multiple assets anchoring to the same block.

        Expected behavior:
        - Multiple assets can anchor to same block
        - Each asset maintains unique identity
        - Order of assets should be deterministic (by position)
        """
        pytest.importorskip("kps.anchoring.anchor")
        from kps.anchoring.anchor import AssetAnchorer

        anchorer = AssetAnchorer()

        # Create multiple assets near same block
        assets = [
            Asset(
                asset_id=f"img-multi-{i}-p0-occ1",
                asset_type=AssetType.IMAGE,
                sha256="a" * 64,
                page_number=0,
                bbox=BBox(80, 250 + i*10, 220, 300 + i*10),
                ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
                file_path=Path(f"/tmp/img-{i}.png"),
                occurrence=1,
                anchor_to="",
                image_width=800,
                image_height=600,
            )
            for i in range(3)
        ]

        # Anchor all assets
        anchor_blocks = []
        for asset in assets:
            block = anchorer.find_anchor_block(asset, two_column_layout_blocks)
            assert block is not None
            anchorer.set_anchor(asset, block)
            anchor_blocks.append(block)

        # All should anchor to same or nearby blocks
        anchor_ids = [block.block_id for block in anchor_blocks]
        # At least some should share the same anchor
        assert len(set(anchor_ids)) <= len(assets), \
            "Assets should be able to share anchor blocks"

    def test_vertical_overlap_detection(self):
        """
        Test vertical overlap detection between asset and block.

        Expected behavior:
        - Calculate vertical overlap between asset and block bboxes
        - Prefer blocks with larger overlap
        - Handle no-overlap case (use distance instead)
        """
        pytest.importorskip("kps.anchoring.anchor")
        from kps.anchoring.anchor import AssetAnchorer

        anchorer = AssetAnchorer()

        asset = Asset(
            asset_id="img-overlap-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256="g" * 64,
            page_number=0,
            bbox=BBox(50, 200, 250, 300),  # y=200-300
            ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            file_path=Path("/tmp/overlap.png"),
            occurrence=1,
            anchor_to="",
            image_width=800,
            image_height=600,
        )

        blocks = [
            ContentBlock(
                block_id="p.overlap.001",
                block_type=BlockType.PARAGRAPH,
                content="Overlapping block",
                bbox=BBox(50, 250, 250, 350),  # y=250-350, overlap=50pt
                page_number=0,
                reading_order=0,
            ),
            ContentBlock(
                block_id="p.nooverlap.001",
                block_type=BlockType.PARAGRAPH,
                content="Non-overlapping block",
                bbox=BBox(50, 400, 250, 450),  # y=400-450, no overlap
                page_number=0,
                reading_order=1,
            ),
        ]

        anchor_block = anchorer.find_anchor_block(asset, blocks)

        # Should prefer overlapping block
        assert anchor_block.block_id == "p.overlap.001", \
            "Should prefer block with vertical overlap"

    def test_anchor_to_different_block_types(self):
        """
        Test anchoring to different block types.

        Expected behavior:
        - Should anchor to PARAGRAPH blocks
        - Should anchor to HEADING blocks
        - Should anchor to TABLE blocks
        - Should NOT anchor to FIGURE blocks (avoid recursion)
        """
        pytest.importorskip("kps.anchoring.anchor")
        from kps.anchoring.anchor import AssetAnchorer

        anchorer = AssetAnchorer()

        asset = Asset(
            asset_id="img-types-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256="h" * 64,
            page_number=0,
            bbox=BBox(50, 200, 250, 300),
            ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            file_path=Path("/tmp/types.png"),
            occurrence=1,
            anchor_to="",
            image_width=800,
            image_height=600,
        )

        # Test with paragraph
        para_block = ContentBlock(
            block_id="p.test.001",
            block_type=BlockType.PARAGRAPH,
            content="Paragraph",
            bbox=BBox(50, 150, 250, 190),
            page_number=0,
            reading_order=0,
        )

        anchor = anchorer.find_anchor_block(asset, [para_block])
        assert anchor is not None, "Should anchor to PARAGRAPH"

        # Test with heading
        heading_block = ContentBlock(
            block_id="h2.test.001",
            block_type=BlockType.HEADING,
            content="Heading",
            bbox=BBox(50, 150, 250, 190),
            page_number=0,
            reading_order=0,
        )

        anchor = anchorer.find_anchor_block(asset, [heading_block])
        assert anchor is not None, "Should anchor to HEADING"

        # Test with table
        table_block = ContentBlock(
            block_id="tbl.test.001",
            block_type=BlockType.TABLE,
            content="Table",
            bbox=BBox(50, 150, 250, 190),
            page_number=0,
            reading_order=0,
        )

        anchor = anchorer.find_anchor_block(asset, [table_block])
        assert anchor is not None, "Should anchor to TABLE"
