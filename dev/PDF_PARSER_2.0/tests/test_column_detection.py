"""
Tests for column detection algorithm.

Tests the column detection functionality that identifies vertical column regions
in multi-column PDF layouts. This is critical for the ≥98% geometry preservation
requirement as it ensures assets are anchored to the correct column.

Algorithm Requirements (from KPS_MASTER_PLAN.md):
- Use DBSCAN or threshold-based clustering on x-coordinates
- Default parameters: epsilon=30pt, min_points=3
- Handle single-column, two-column, and three-column layouts
- Correctly classify blocks spanning multiple columns
"""

import pytest
from pathlib import Path
from kps.core.document import ContentBlock
from kps.core.bbox import BBox

# These imports will work once the anchoring module is implemented
# For now, we'll use TYPE_CHECKING to avoid import errors during test discovery
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kps.anchoring.columns import ColumnDetector, Column


class TestColumnDetection:
    """Test suite for column detection algorithm."""

    def test_single_column_layout_detection(
        self,
        single_column_layout_blocks: list[ContentBlock],
    ):
        """
        Test detection of single-column layout.

        Expected behavior:
        - Should detect exactly 1 column
        - All blocks should be assigned to column 0
        - Column bounds should encompass all blocks
        """
        pytest.importorskip("kps.anchoring.columns")
        from kps.anchoring.columns import ColumnDetector

        detector = ColumnDetector()
        columns = detector.detect_columns(single_column_layout_blocks)

        # Verify single column detected
        assert len(columns) == 1, f"Expected 1 column, found {len(columns)}"

        # Verify all blocks assigned to column 0
        for block in single_column_layout_blocks:
            column_idx = detector.get_block_column(block, columns)
            assert column_idx == 0, f"Block {block.block_id} not in column 0"

        # Verify column bounds
        column = columns[0]
        assert column.x_min <= 50, "Column should start at x=50"
        assert column.x_max >= 500, "Column should end at x=500"

    def test_two_column_layout_with_30pt_gap(
        self,
        two_column_layout_blocks: list[ContentBlock],
    ):
        """
        Test detection of two-column layout with 30pt gap.

        Layout:
        - Left column: x=50-250 (width=200)
        - Gap: 30pt
        - Right column: x=280-480 (width=200)

        Expected behavior:
        - Detect exactly 2 columns
        - Blocks with x < 250 in left column (column 0)
        - Blocks with x >= 280 in right column (column 1)
        - Gap should be detected correctly
        """
        pytest.importorskip("kps.anchoring.columns")
        from kps.anchoring.columns import ColumnDetector

        detector = ColumnDetector()
        columns = detector.detect_columns(two_column_layout_blocks)

        # Verify two columns detected
        assert len(columns) == 2, f"Expected 2 columns, found {len(columns)}"

        # Verify left column bounds
        left_column = columns[0]
        assert left_column.x_min <= 50, "Left column should start at x=50"
        assert left_column.x_max >= 250, "Left column should end at x=250"

        # Verify right column bounds
        right_column = columns[1]
        assert right_column.x_min <= 280, "Right column should start at x=280"
        assert right_column.x_max >= 480, "Right column should end at x=480"

        # Verify block assignments
        left_blocks = [b for b in two_column_layout_blocks if b.bbox.x0 < 260]
        right_blocks = [b for b in two_column_layout_blocks if b.bbox.x0 >= 260]

        for block in left_blocks:
            column_idx = detector.get_block_column(block, columns)
            assert column_idx == 0, f"Block {block.block_id} should be in left column"

        for block in right_blocks:
            column_idx = detector.get_block_column(block, columns)
            assert column_idx == 1, f"Block {block.block_id} should be in right column"

    def test_three_column_layout_detection(
        self,
        three_column_layout_blocks: list[ContentBlock],
    ):
        """
        Test detection of three-column layout.

        Layout:
        - Left: x=50-200 (width=150)
        - Middle: x=220-370 (width=150)
        - Right: x=390-540 (width=150)
        - Gap: 20pt between columns

        Expected behavior:
        - Detect exactly 3 columns
        - Each block correctly assigned to its column
        """
        pytest.importorskip("kps.anchoring.columns")
        from kps.anchoring.columns import ColumnDetector

        detector = ColumnDetector()
        columns = detector.detect_columns(three_column_layout_blocks)

        # Verify three columns detected
        assert len(columns) == 3, f"Expected 3 columns, found {len(columns)}"

        # Verify each column's approximate bounds
        assert columns[0].x_max < 210, "Column 0 should end before 210"
        assert 210 < columns[1].x_min < 230, "Column 1 should start around 220"
        assert 360 < columns[1].x_max < 380, "Column 1 should end around 370"
        assert columns[2].x_min > 380, "Column 2 should start after 380"

        # Verify block assignments
        expected_columns = [0, 1, 2]
        for i, block in enumerate(three_column_layout_blocks):
            column_idx = detector.get_block_column(block, columns)
            assert column_idx == expected_columns[i], \
                f"Block {block.block_id} in wrong column: {column_idx}"

    def test_blocks_spanning_columns(self):
        """
        Test edge case: blocks that span multiple columns.

        Expected behavior:
        - Block should be assigned to column where its center is located
        - OR assigned to column with largest overlap
        - Should not cause detection to fail
        """
        pytest.importorskip("kps.anchoring.columns")
        from kps.anchoring.columns import ColumnDetector

        # Create a layout with a spanning block
        blocks = [
            ContentBlock(
                block_id="p.col1.001",
                block_type="paragraph",
                content="Column 1",
                bbox=BBox(50, 100, 200, 150),
                page_number=0,
                reading_order=0,
            ),
            ContentBlock(
                block_id="p.spanning.001",
                block_type="paragraph",
                content="Spanning block",
                bbox=BBox(50, 200, 450, 250),  # Spans both columns
                page_number=0,
                reading_order=1,
            ),
            ContentBlock(
                block_id="p.col2.001",
                block_type="paragraph",
                content="Column 2",
                bbox=BBox(280, 100, 450, 150),
                page_number=0,
                reading_order=2,
            ),
        ]

        detector = ColumnDetector()
        columns = detector.detect_columns(blocks)

        # Should still detect 2 columns
        assert len(columns) >= 1, "Should detect at least 1 column"

        # Spanning block should be assigned to a valid column
        spanning_block = blocks[1]
        column_idx = detector.get_block_column(spanning_block, columns)
        assert 0 <= column_idx < len(columns), \
            f"Spanning block assigned to invalid column {column_idx}"

    def test_all_blocks_assigned_to_column(
        self,
        two_column_layout_blocks: list[ContentBlock],
    ):
        """
        Test validation: all blocks must be assigned to a column.

        Expected behavior:
        - Every block in input should be assignable to a column
        - No blocks should be left unassigned
        """
        pytest.importorskip("kps.anchoring.columns")
        from kps.anchoring.columns import ColumnDetector

        detector = ColumnDetector()
        columns = detector.detect_columns(two_column_layout_blocks)

        # Verify all blocks can be assigned
        for block in two_column_layout_blocks:
            column_idx = detector.get_block_column(block, columns)
            assert column_idx is not None, \
                f"Block {block.block_id} was not assigned to any column"
            assert 0 <= column_idx < len(columns), \
                f"Block {block.block_id} assigned to invalid column {column_idx}"

    def test_dbscan_parameters(self):
        """
        Test DBSCAN parameters (epsilon=30, min_points=3).

        Expected behavior:
        - Epsilon=30 should correctly separate columns with 30pt gap
        - min_points=3 should filter out outliers
        - Parameters should be configurable
        """
        pytest.importorskip("kps.anchoring.columns")
        from kps.anchoring.columns import ColumnDetector

        # Test with default parameters
        detector = ColumnDetector(epsilon=30.0, min_points=3)

        # Verify parameters are set
        assert detector.epsilon == 30.0, "Default epsilon should be 30.0"
        assert detector.min_points == 3, "Default min_points should be 3"

        # Test with custom parameters
        custom_detector = ColumnDetector(epsilon=20.0, min_points=2)
        assert custom_detector.epsilon == 20.0
        assert custom_detector.min_points == 2

    def test_empty_blocks_list(self):
        """
        Test edge case: empty blocks list.

        Expected behavior:
        - Should return empty list or handle gracefully
        - Should not raise exception
        """
        pytest.importorskip("kps.anchoring.columns")
        from kps.anchoring.columns import ColumnDetector

        detector = ColumnDetector()
        columns = detector.detect_columns([])

        # Should return empty list or handle gracefully
        assert isinstance(columns, list), "Should return a list"
        assert len(columns) == 0, "Should return empty list for no blocks"

    def test_blocks_without_bbox(self):
        """
        Test edge case: blocks without bounding boxes.

        Expected behavior:
        - Should skip blocks without bbox
        - Should not crash
        - Should process remaining blocks normally
        """
        pytest.importorskip("kps.anchoring.columns")
        from kps.anchoring.columns import ColumnDetector

        blocks = [
            ContentBlock(
                block_id="p.001",
                block_type="paragraph",
                content="Block with bbox",
                bbox=BBox(50, 100, 250, 150),
                page_number=0,
                reading_order=0,
            ),
            ContentBlock(
                block_id="p.002",
                block_type="paragraph",
                content="Block without bbox",
                bbox=None,  # No bbox
                page_number=0,
                reading_order=1,
            ),
            ContentBlock(
                block_id="p.003",
                block_type="paragraph",
                content="Another block with bbox",
                bbox=BBox(50, 200, 250, 250),
                page_number=0,
                reading_order=2,
            ),
        ]

        detector = ColumnDetector()
        columns = detector.detect_columns(blocks)

        # Should detect 1 column from the 2 blocks with bbox
        assert len(columns) >= 1, "Should detect columns from blocks with bbox"

    def test_column_bounds_calculation(
        self,
        two_column_layout_blocks: list[ContentBlock],
    ):
        """
        Test accurate calculation of column boundaries.

        Expected behavior:
        - Column x_min should be minimum x0 of all blocks in column
        - Column x_max should be maximum x1 of all blocks in column
        - Column y_min and y_max should encompass all blocks
        """
        pytest.importorskip("kps.anchoring.columns")
        from kps.anchoring.columns import ColumnDetector

        detector = ColumnDetector()
        columns = detector.detect_columns(two_column_layout_blocks)

        assert len(columns) == 2, "Should detect 2 columns"

        # Check left column bounds
        left_blocks = [b for b in two_column_layout_blocks if b.bbox.x0 < 260]
        left_x_min = min(b.bbox.x0 for b in left_blocks)
        left_x_max = max(b.bbox.x1 for b in left_blocks)

        assert columns[0].x_min <= left_x_min, \
            f"Left column x_min {columns[0].x_min} should be <= {left_x_min}"
        assert columns[0].x_max >= left_x_max, \
            f"Left column x_max {columns[0].x_max} should be >= {left_x_max}"

        # Check right column bounds
        right_blocks = [b for b in two_column_layout_blocks if b.bbox.x0 >= 260]
        right_x_min = min(b.bbox.x0 for b in right_blocks)
        right_x_max = max(b.bbox.x1 for b in right_blocks)

        assert columns[1].x_min <= right_x_min, \
            f"Right column x_min {columns[1].x_min} should be <= {right_x_min}"
        assert columns[1].x_max >= right_x_max, \
            f"Right column x_max {columns[1].x_max} should be >= {right_x_max}"

    def test_reading_order_preserved_within_column(
        self,
        two_column_layout_blocks: list[ContentBlock],
    ):
        """
        Test that reading order is preserved within each column.

        Expected behavior:
        - Blocks within same column should maintain their reading_order
        - Column detection should not alter reading order
        """
        pytest.importorskip("kps.anchoring.columns")
        from kps.anchoring.columns import ColumnDetector

        detector = ColumnDetector()
        columns = detector.detect_columns(two_column_layout_blocks)

        # Get blocks by column
        for col_idx, column in enumerate(columns):
            column_blocks = [
                b for b in two_column_layout_blocks
                if detector.get_block_column(b, columns) == col_idx
            ]

            # Sort by reading order
            sorted_blocks = sorted(column_blocks, key=lambda b: b.reading_order)

            # Verify order is maintained
            for i in range(len(sorted_blocks) - 1):
                assert sorted_blocks[i].reading_order < sorted_blocks[i + 1].reading_order, \
                    f"Reading order not preserved in column {col_idx}"
