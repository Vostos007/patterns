"""Column detection for multi-column PDF layouts.

This module implements DBSCAN-based column detection for KPS v2.0,
enabling column-aware anchoring of assets to text blocks.

Algorithm:
    - DBSCAN clustering on x-coordinates of content blocks
    - Epsilon = 30pt (minimum column gap threshold)
    - MinPoints = 3 (minimum blocks per column)
    - Handles 1-3 column layouts

References:
    - KPS_MASTER_PLAN.md Section: "Column Detection"
    - Anchoring Algorithm (Section 4: Column-aware matching)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
import numpy as np
from sklearn.cluster import DBSCAN

from ..core.document import ContentBlock
from ..core.bbox import BBox


@dataclass
class Column:
    """
    Represents a single column in a multi-column layout.

    Attributes:
        column_id: Unique column identifier (0-indexed, left to right)
        x_min: Left boundary in PDF points
        x_max: Right boundary in PDF points
        y_min: Top boundary in PDF points (minimum y across all blocks)
        y_max: Bottom boundary in PDF points (maximum y across all blocks)
        blocks: List of ContentBlock instances in this column
    """

    column_id: int
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    blocks: List[ContentBlock] = field(default_factory=list)

    @property
    def width(self) -> float:
        """Column width in PDF points."""
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        """Column height in PDF points."""
        return self.y_max - self.y_min

    @property
    def center_x(self) -> float:
        """Horizontal center of column."""
        return (self.x_min + self.x_max) / 2

    @property
    def bounds(self) -> BBox:
        """Column boundaries as BBox."""
        return BBox(self.x_min, self.y_min, self.x_max, self.y_max)

    def contains_x(self, x: float, tolerance: float = 0.0) -> bool:
        """
        Check if x-coordinate falls within this column.

        Args:
            x: X-coordinate to check
            tolerance: Optional tolerance for boundary checks (in points)

        Returns:
            True if x is within column boundaries (with tolerance)
        """
        return (self.x_min - tolerance) <= x <= (self.x_max + tolerance)

    def contains_bbox(self, bbox: BBox, threshold: float = 0.5) -> bool:
        """
        Check if a bbox belongs to this column.

        A bbox belongs to a column if its horizontal overlap
        exceeds the threshold (default 50%).

        Args:
            bbox: BBox to check
            threshold: Minimum overlap ratio (0-1)

        Returns:
            True if bbox has sufficient horizontal overlap with column
        """
        # Calculate horizontal overlap
        overlap_left = max(self.x_min, bbox.x0)
        overlap_right = min(self.x_max, bbox.x1)
        overlap_width = max(0, overlap_right - overlap_left)

        # Check overlap ratio
        bbox_width = bbox.width
        if bbox_width == 0:
            return False

        overlap_ratio = overlap_width / bbox_width
        return overlap_ratio >= threshold


def detect_columns(
    blocks: List[ContentBlock],
    eps: float = 30.0,
    min_samples: int = 3,
    min_column_width: float = 50.0,
) -> List[Column]:
    """
    Detect column structure in a list of content blocks using DBSCAN.

    The algorithm clusters blocks by their x-coordinates to identify
    distinct columns. Blocks with no bbox are excluded.

    Algorithm steps:
        1. Filter blocks with valid bboxes
        2. Extract x-center coordinates for DBSCAN
        3. Cluster using DBSCAN (eps=30pt, min_samples=3)
        4. Build Column objects with boundaries
        5. Assign blocks to columns
        6. Sort columns left-to-right

    Args:
        blocks: List of ContentBlock instances with bbox coordinates
        eps: DBSCAN epsilon (max distance between samples, in points)
            Default: 30.0 (minimum column gap)
        min_samples: DBSCAN min_samples (minimum blocks per cluster)
            Default: 3 (minimum blocks per column)
        min_column_width: Minimum width for valid columns (filters noise)
            Default: 50.0 points

    Returns:
        List of Column objects, sorted left-to-right by column_id

    Raises:
        ValueError: If blocks list is empty or all blocks lack bboxes

    Edge Cases Handled:
        - Single column: Returns 1 column with all blocks
        - Uneven columns: Each column has independent boundaries
        - Blocks spanning columns: Assigned to column with max horizontal overlap
        - Outliers: DBSCAN noise points assigned to nearest column
        - Empty input: Raises ValueError

    Example:
        >>> blocks = [
        ...     ContentBlock("p.1", BlockType.PARAGRAPH, "Text", bbox=BBox(50, 100, 150, 120)),
        ...     ContentBlock("p.2", BlockType.PARAGRAPH, "Text", bbox=BBox(300, 100, 400, 120)),
        ... ]
        >>> columns = detect_columns(blocks)
        >>> len(columns)
        2
        >>> columns[0].x_min < columns[1].x_min
        True
    """
    # Validation
    if not blocks:
        raise ValueError("Empty blocks list provided to detect_columns()")

    # Filter blocks with valid bboxes
    blocks_with_bbox = [b for b in blocks if b.bbox is not None]

    if not blocks_with_bbox:
        raise ValueError("No blocks with bbox found in detect_columns()")

    # Edge case: single block
    if len(blocks_with_bbox) == 1:
        block = blocks_with_bbox[0]
        return [
            Column(
                column_id=0,
                x_min=block.bbox.x0,
                x_max=block.bbox.x1,
                y_min=block.bbox.y0,
                y_max=block.bbox.y1,
                blocks=[block],
            )
        ]

    # Extract x-center coordinates for clustering
    x_centers = np.array([b.bbox.center[0] for b in blocks_with_bbox]).reshape(-1, 1)

    # Apply DBSCAN clustering
    dbscan = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean")
    cluster_labels = dbscan.fit_predict(x_centers)

    # Build clusters (including noise points initially)
    clusters: Dict[int, List[ContentBlock]] = {}
    for block, label in zip(blocks_with_bbox, cluster_labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(block)

    # Handle noise points (label = -1)
    noise_blocks = clusters.pop(-1, [])

    # Build Column objects from clusters
    columns: List[Column] = []

    for cluster_id, cluster_blocks in clusters.items():
        # Calculate column boundaries
        x_coords = [b.bbox.center[0] for b in cluster_blocks]
        all_x0 = [b.bbox.x0 for b in cluster_blocks]
        all_x1 = [b.bbox.x1 for b in cluster_blocks]
        all_y0 = [b.bbox.y0 for b in cluster_blocks]
        all_y1 = [b.bbox.y1 for b in cluster_blocks]

        x_min = min(all_x0)
        x_max = max(all_x1)
        y_min = min(all_y0)
        y_max = max(all_y1)

        # Filter out narrow columns (likely noise)
        if (x_max - x_min) < min_column_width:
            noise_blocks.extend(cluster_blocks)
            continue

        column = Column(
            column_id=-1,  # Will be set after sorting
            x_min=x_min,
            x_max=x_max,
            y_min=y_min,
            y_max=y_max,
            blocks=cluster_blocks,
        )
        columns.append(column)

    # Edge case: all blocks were noise or filtered out
    if not columns:
        # Fallback: create single column with all blocks
        all_blocks = blocks_with_bbox
        return [
            Column(
                column_id=0,
                x_min=min(b.bbox.x0 for b in all_blocks),
                x_max=max(b.bbox.x1 for b in all_blocks),
                y_min=min(b.bbox.y0 for b in all_blocks),
                y_max=max(b.bbox.y1 for b in all_blocks),
                blocks=all_blocks,
            )
        ]

    # Sort columns left-to-right and assign column_ids
    columns.sort(key=lambda c: c.center_x)
    for i, column in enumerate(columns):
        # Update column_id (immutable dataclass workaround)
        object.__setattr__(column, "column_id", i)

    # Assign noise blocks to nearest column
    if noise_blocks:
        columns = _assign_noise_blocks(noise_blocks, columns)

    # Validate: ensure all blocks assigned to exactly one column
    _validate_block_assignment(blocks_with_bbox, columns)

    return columns


def _assign_noise_blocks(
    noise_blocks: List[ContentBlock], columns: List[Column]
) -> List[Column]:
    """
    Assign noise blocks (DBSCAN outliers) to nearest columns.

    Strategy:
        - Calculate horizontal overlap with each column
        - Assign to column with maximum overlap
        - If no overlap, assign to nearest column by x-distance

    Args:
        noise_blocks: Blocks labeled as noise by DBSCAN
        columns: Existing Column objects

    Returns:
        Updated columns list with noise blocks assigned
    """
    for block in noise_blocks:
        best_column = None
        max_overlap = 0.0
        min_distance = float("inf")

        for column in columns:
            # Calculate horizontal overlap
            overlap_left = max(column.x_min, block.bbox.x0)
            overlap_right = min(column.x_max, block.bbox.x1)
            overlap_width = max(0, overlap_right - overlap_left)

            if overlap_width > max_overlap:
                max_overlap = overlap_width
                best_column = column

            # Calculate distance to column center
            block_center_x = block.bbox.center[0]
            distance = abs(column.center_x - block_center_x)
            if distance < min_distance:
                min_distance = distance
                if max_overlap == 0:  # Only update if no overlap found yet
                    best_column = column

        # Assign to best column
        if best_column:
            best_column.blocks.append(block)

            # Update column boundaries if needed
            object.__setattr__(
                best_column, "x_min", min(best_column.x_min, block.bbox.x0)
            )
            object.__setattr__(
                best_column, "x_max", max(best_column.x_max, block.bbox.x1)
            )
            object.__setattr__(
                best_column, "y_min", min(best_column.y_min, block.bbox.y0)
            )
            object.__setattr__(
                best_column, "y_max", max(best_column.y_max, block.bbox.y1)
            )

    return columns


def _validate_block_assignment(
    blocks: List[ContentBlock], columns: List[Column]
) -> None:
    """
    Validate that all blocks are assigned to exactly one column.

    Args:
        blocks: Original list of blocks
        columns: List of columns with assigned blocks

    Raises:
        AssertionError: If validation fails

    Validation rules:
        1. Each block appears in exactly one column
        2. No blocks are lost
        3. No blocks are duplicated
    """
    # Collect all assigned blocks
    assigned_blocks: Set[str] = set()
    duplicates: List[str] = []

    for column in columns:
        for block in column.blocks:
            if block.block_id in assigned_blocks:
                duplicates.append(block.block_id)
            assigned_blocks.add(block.block_id)

    # Check for duplicates
    assert not duplicates, f"Blocks assigned to multiple columns: {duplicates}"

    # Check for missing blocks
    expected_block_ids = {b.block_id for b in blocks}
    missing = expected_block_ids - assigned_blocks

    assert not missing, f"Blocks not assigned to any column: {missing}"

    # Check for extra blocks
    extra = assigned_blocks - expected_block_ids
    assert not extra, f"Unknown blocks found in columns: {extra}"


def find_block_column(block: ContentBlock, columns: List[Column]) -> Optional[Column]:
    """
    Find which column a block belongs to.

    Args:
        block: ContentBlock to locate
        columns: List of Column objects

    Returns:
        Column containing the block, or None if not found

    Note:
        This is a convenience function for looking up a block's column
        after detect_columns() has been run.
    """
    if not block.bbox:
        return None

    for column in columns:
        if block in column.blocks:
            return column

    return None


def find_asset_column(bbox: BBox, columns: List[Column], threshold: float = 0.5) -> Optional[Column]:
    """
    Find which column an asset (by bbox) belongs to.

    Uses horizontal overlap ratio to determine column membership.

    Args:
        bbox: BBox of the asset
        columns: List of Column objects
        threshold: Minimum overlap ratio to consider (0-1)

    Returns:
        Column with maximum overlap, or None if no sufficient overlap

    Example:
        >>> asset_bbox = BBox(100, 200, 200, 300)
        >>> column = find_asset_column(asset_bbox, columns)
        >>> if column:
        ...     print(f"Asset in column {column.column_id}")
    """
    best_column = None
    max_overlap = 0.0

    for column in columns:
        # Calculate horizontal overlap
        overlap_left = max(column.x_min, bbox.x0)
        overlap_right = min(column.x_max, bbox.x1)
        overlap_width = max(0, overlap_right - overlap_left)

        if bbox.width > 0:
            overlap_ratio = overlap_width / bbox.width

            if overlap_ratio > max_overlap:
                max_overlap = overlap_ratio
                best_column = column

    # Only return if overlap exceeds threshold
    if max_overlap >= threshold:
        return best_column

    return None
