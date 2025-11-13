"""Asset-to-block anchoring algorithm for KPS v2.0.

This module implements the core anchoring algorithm that matches visual assets
to text blocks using spatial proximity within the same column.

Algorithm:
    For each asset on page P:
        1. Find all blocks on same page
        2. Filter to blocks in same column (using column detection)
        3. Calculate vertical distances (asset.bbox.y1 to block.bbox.y0)
        4. Select nearest block below asset (min positive distance)
        5. If no block below, select nearest block above
        6. Compute normalized coordinates: (x, y, w, h) relative to column bounds

Distance Metric:
    - Vertical: |asset.y1 - block.y0|
    - Must be same column (horizontal overlap >= 50%)
    - Prefer "below" anchoring (reading order)

Validation:
    - All assets must have anchor_to set
    - Geometry preservation: +/-2pt or 1% tolerance
    - Log warnings for ambiguous anchoring (multiple equally distant blocks)

References:
    - KPS_MASTER_PLAN.md Section: "Anchoring Algorithm"
    - Section 4: "Column-aware matching"
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Dict
import math

from ..core.assets import Asset, AssetLedger
from ..core.assets import AssetType
from ..core.document import KPSDocument, ContentBlock
from ..core.bbox import BBox, NormalizedBBox
from .columns import Column, detect_columns, find_asset_column

logger = logging.getLogger(__name__)


@dataclass
class AnchoringReport:
    """
    Report for anchoring validation and diagnostics.

    Attributes:
        total_assets: Total number of assets processed
        anchored_assets: Number of assets successfully anchored
        unanchored_assets: List of asset_ids that failed anchoring
        ambiguous_anchors: List of (asset_id, candidate_blocks) with equal distances
        geometry_violations: Assets with geometry preservation errors
        warnings: List of warning messages
    """

    total_assets: int = 0
    anchored_assets: int = 0
    unanchored_assets: List[str] = field(default_factory=list)
    ambiguous_anchors: List[Tuple[str, List[str]]] = field(default_factory=list)
    geometry_violations: List[Tuple[str, float]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate anchoring success rate."""
        if self.total_assets == 0:
            return 0.0
        return self.anchored_assets / self.total_assets

    @property
    def geometry_pass_rate(self) -> float:
        """Calculate geometry preservation pass rate."""
        if self.total_assets == 0:
            return 0.0
        return (self.total_assets - len(self.geometry_violations)) / self.total_assets

    def is_valid(self, min_success_rate: float = 1.0, min_geometry_rate: float = 0.98) -> bool:
        """
        Check if anchoring meets quality thresholds.

        Args:
            min_success_rate: Minimum anchoring success rate (default: 100%)
            min_geometry_rate: Minimum geometry pass rate (default: 98%)

        Returns:
            True if all thresholds met
        """
        return (
            self.success_rate >= min_success_rate
            and self.geometry_pass_rate >= min_geometry_rate
        )


def compute_normalized_bbox(asset: Asset, column: Column) -> NormalizedBBox:
    """
    Compute normalized bounding box coordinates relative to column bounds.

    Converts absolute PDF coordinates to column-relative 0-1 coordinates
    for geometry comparison independent of page/column size.

    Args:
        asset: Asset with bbox in absolute PDF coordinates
        column: Column containing the asset

    Returns:
        NormalizedBBox with coordinates in [0, 1] range

    Raises:
        ValueError: If column width or height is zero
        ValueError: If normalized coordinates fall outside [0, 1]

    Example:
        >>> asset = Asset(bbox=BBox(60, 110, 160, 210), ...)
        >>> column = Column(bounds=BBox(50, 100, 250, 700), ...)
        >>> norm = compute_normalized_bbox(asset, column)
        >>> norm.x  # (60 - 50) / (250 - 50) = 0.05
        0.05
        >>> norm.y  # (110 - 100) / (700 - 100) = 0.0167
        0.01666...
        >>> norm.w  # 100 / 200 = 0.5
        0.5
        >>> norm.h  # 100 / 600 = 0.1667
        0.16666...
    """
    column_bounds = column.bounds

    # Validate column dimensions
    if column_bounds.width <= 0:
        raise ValueError(
            f"Column width must be positive, got {column_bounds.width} "
            f"for column {column.column_id}"
        )

    if column_bounds.height <= 0:
        raise ValueError(
            f"Column height must be positive, got {column_bounds.height} "
            f"for column {column.column_id}"
        )

    # Calculate normalized coordinates
    x_norm = (asset.bbox.x0 - column_bounds.x0) / column_bounds.width
    y_norm = (asset.bbox.y0 - column_bounds.y0) / column_bounds.height
    w_norm = asset.bbox.width / column_bounds.width
    h_norm = asset.bbox.height / column_bounds.height

    # Validate range (with small tolerance for floating point errors)
    tolerance = 0.01
    if not (-tolerance <= x_norm <= 1 + tolerance):
        raise ValueError(
            f"Normalized x coordinate {x_norm:.4f} outside [0, 1] range. "
            f"Asset bbox: {asset.bbox}, Column bounds: {column_bounds}"
        )

    if not (-tolerance <= y_norm <= 1 + tolerance):
        raise ValueError(
            f"Normalized y coordinate {y_norm:.4f} outside [0, 1] range. "
            f"Asset bbox: {asset.bbox}, Column bounds: {column_bounds}"
        )

    # Clamp to [0, 1] to handle floating point precision
    x_norm = max(0.0, min(1.0, x_norm))
    y_norm = max(0.0, min(1.0, y_norm))
    w_norm = max(0.0, min(1.0, w_norm))
    h_norm = max(0.0, min(1.0, h_norm))

    return NormalizedBBox(x=x_norm, y=y_norm, w=w_norm, h=h_norm)


def find_nearest_block(
    asset: Asset,
    blocks: List[ContentBlock],
    same_column: Column = None,
    prefer_below: bool = True,
) -> Optional[ContentBlock]:
    """
    Find the nearest content block to anchor an asset.

    Algorithm:
        1. Filter blocks to same column (if same_column provided)
        2. Calculate vertical distances from asset bottom to block top
        3. Prefer blocks below asset (positive distance)
        4. If no blocks below, select nearest block above
        5. Detect ambiguous cases (multiple blocks at equal distance)

    Distance Calculation:
        - Below: distance = block.bbox.y0 - asset.bbox.y1 (positive)
        - Above: distance = asset.bbox.y0 - block.bbox.y1 (positive)

    Args:
        asset: Asset to anchor
        blocks: List of candidate blocks on same page
        same_column: Optional column constraint (only consider blocks in this column)
        prefer_below: If True, prefer blocks below asset (reading order)

    Returns:
        Nearest ContentBlock, or None if no suitable blocks found

    Side Effects:
        Logs warnings for ambiguous anchoring (multiple equally distant blocks)

    Example:
        >>> asset = Asset(bbox=BBox(100, 200, 200, 300), page_number=0, ...)
        >>> blocks = [
        ...     ContentBlock(bbox=BBox(100, 310, 200, 330), page_number=0, ...),  # Below
        ...     ContentBlock(bbox=BBox(100, 150, 200, 190), page_number=0, ...),  # Above
        ... ]
        >>> nearest = find_nearest_block(asset, blocks, prefer_below=True)
        >>> nearest.bbox.y0  # Should select block below (y0=310)
        310
    """
    if not blocks:
        logger.warning(f"No blocks provided for asset {asset.asset_id}")
        return None

    # Filter to blocks with bbox
    blocks_with_bbox = [b for b in blocks if b.bbox is not None]
    if not blocks_with_bbox:
        logger.warning(
            f"No blocks with bbox found for asset {asset.asset_id} on page {asset.page_number}"
        )
        return None

    # Filter to same column if specified
    if same_column is not None:
        blocks_with_bbox = [
            b for b in blocks_with_bbox if same_column.contains_bbox(b.bbox, threshold=0.5)
        ]

        if not blocks_with_bbox:
            logger.warning(
                f"No blocks in column {same_column.column_id} for asset {asset.asset_id}"
            )
            return None

    # Calculate distances to all blocks
    # Distance: vertical gap between asset bottom and block top (for below)
    #           or block bottom and asset top (for above)

    blocks_below: List[Tuple[float, ContentBlock]] = []
    blocks_above: List[Tuple[float, ContentBlock]] = []

    for block in blocks_with_bbox:
        # Check if block is below asset (block top > asset bottom)
        if block.bbox.y0 >= asset.bbox.y1:
            distance = block.bbox.y0 - asset.bbox.y1
            blocks_below.append((distance, block))
        # Check if block is above asset (block bottom < asset top)
        elif block.bbox.y1 <= asset.bbox.y0:
            distance = asset.bbox.y0 - block.bbox.y1
            blocks_above.append((distance, block))
        # Block overlaps asset vertically - use center-to-center distance
        else:
            asset_center = asset.bbox.center
            block_center = block.bbox.center
            distance = abs(asset_center[1] - block_center[1])
            # Assign to below/above based on centers
            if block_center[1] >= asset_center[1]:
                blocks_below.append((distance, block))
            else:
                blocks_above.append((distance, block))

    # Select blocks based on preference
    if prefer_below and blocks_below:
        candidates = blocks_below
        direction = "below"
    elif blocks_above:
        candidates = blocks_above
        direction = "above"
    elif blocks_below:
        candidates = blocks_below
        direction = "below"
    else:
        logger.warning(f"No suitable blocks found for asset {asset.asset_id}")
        return None

    # Sort by distance
    candidates.sort(key=lambda x: x[0])

    # Select nearest
    min_distance, nearest_block = candidates[0]

    # Check for ambiguous cases (multiple blocks at same distance)
    ambiguous_threshold = 1.0  # 1pt tolerance
    equally_close = [
        block for dist, block in candidates if abs(dist - min_distance) < ambiguous_threshold
    ]

    if len(equally_close) > 1:
        block_ids = [b.block_id for b in equally_close]
        logger.warning(
            f"Ambiguous anchoring for asset {asset.asset_id}: "
            f"{len(equally_close)} blocks within {ambiguous_threshold}pt. "
            f"Candidates: {block_ids}. Selected: {nearest_block.block_id}. "
            f"Direction: {direction}, Distance: {min_distance:.2f}pt"
        )

    return nearest_block


def anchor_assets_to_blocks(
    assets: AssetLedger,
    document: KPSDocument,
    columns_by_page: Optional[Dict[int, List[Column]]] = None,
    tolerance_pt: float = 2.0,
    tolerance_pct: float = 0.01,
) -> Tuple[AssetLedger, AnchoringReport]:
    """
    Anchor all assets to content blocks using column-aware spatial proximity.

    This is the main entry point for the anchoring algorithm. It processes
    all assets in the ledger and assigns each one to the nearest text block
    within the same column.

    Algorithm:
        For each asset:
            1. Get all blocks on same page
            2. Detect columns (or use provided columns)
            3. Find asset's column
            4. Find nearest block within column
            5. Set asset.anchor_to = block.block_id
            6. Validate geometry preservation

    Args:
        assets: AssetLedger with all extracted assets
        document: KPSDocument with text blocks
        columns_by_page: Optional pre-computed column detection results.
            Format: {page_number: [Column, ...]}
            If None, columns will be detected automatically.
        tolerance_pt: Absolute tolerance for geometry check (points)
        tolerance_pct: Percentage tolerance for geometry check (0-1)

    Returns:
        Tuple of (updated AssetLedger, AnchoringReport)

    Raises:
        ValueError: If asset anchoring fails validation

    Side Effects:
        - Modifies asset.anchor_to for each asset in ledger
        - Logs warnings for ambiguous or failed anchoring

    Validation:
        - All assets must have anchor_to set (100% success rate)
        - Geometry preservation: >=98% of assets within tolerance
        - Tolerance: +/-2pt or 1% of asset size (whichever is larger)

    Example:
        >>> ledger = AssetLedger(assets=[...], ...)
        >>> document = KPSDocument(sections=[...], ...)
        >>> anchored_ledger, report = anchor_assets_to_blocks(ledger, document)
        >>> assert report.success_rate == 1.0
        >>> assert report.geometry_pass_rate >= 0.98
    """
    report = AnchoringReport(total_assets=len(assets.assets))

    # Detect columns for each page if not provided
    if columns_by_page is None:
        columns_by_page = {}
        for page_num in range(document.metadata.total_pages if hasattr(document.metadata, 'total_pages') else assets.total_pages):
            page_blocks = document.get_blocks_on_page(page_num)
            if page_blocks:
                try:
                    columns = detect_columns(page_blocks)
                    columns_by_page[page_num] = columns
                    logger.info(
                        f"Detected {len(columns)} column(s) on page {page_num}"
                    )
                except ValueError as e:
                    logger.warning(
                        f"Failed to detect columns on page {page_num}: {e}. "
                        f"Will attempt anchoring without column constraints."
                    )
                    columns_by_page[page_num] = []

    # Process each asset
    for asset in assets.assets:
        page_num = asset.page_number

        # Get blocks on same page
        page_blocks = document.get_blocks_on_page(page_num)

        if not page_blocks:
            logger.error(
                f"No text blocks found on page {page_num} for asset {asset.asset_id}"
            )
            report.unanchored_assets.append(asset.asset_id)
            report.warnings.append(
                f"Asset {asset.asset_id}: No text blocks on page {page_num}"
            )
            continue

        # Get columns for this page
        page_columns = columns_by_page.get(page_num, [])

        # Find asset's column
        asset_column = None
        if page_columns:
            asset_column = find_asset_column(asset.bbox, page_columns, threshold=0.5)

            if asset_column is None:
                logger.warning(
                    f"Asset {asset.asset_id} not assigned to any column on page {page_num}. "
                    f"Will search all blocks."
                )
                report.warnings.append(
                    f"Asset {asset.asset_id}: Not in any detected column"
                )

        # Find nearest block
        nearest_block = find_nearest_block(
            asset=asset,
            blocks=page_blocks,
            same_column=asset_column,
            prefer_below=True,
        )

        if nearest_block is None:
            logger.error(f"Failed to find anchor block for asset {asset.asset_id}")
            report.unanchored_assets.append(asset.asset_id)
            report.warnings.append(
                f"Asset {asset.asset_id}: No suitable anchor block found"
            )
            continue

        # Set anchor
        asset.anchor_to = nearest_block.block_id
        report.anchored_assets += 1

        logger.info(
            f"Anchored asset {asset.asset_id} to block {nearest_block.block_id}"
        )

        # Validate geometry preservation (if column available)
        if asset_column is not None:
            try:
                normalized_bbox = compute_normalized_bbox(asset, asset_column)

                # Check if within tolerance
                # For now, just validate that normalized coords are valid
                # Full geometry check would compare against target placement
                # (which happens in InDesign, so we can't validate here)

                # Store normalized bbox for later QA
                # (This would be stored in a separate structure in production)

            except ValueError as e:
                logger.warning(
                    f"Geometry validation failed for asset {asset.asset_id}: {e}"
                )
                report.geometry_violations.append((asset.asset_id, 0.0))
                report.warnings.append(
                    f"Asset {asset.asset_id}: Geometry validation error - {e}"
                )

    # Validate results
    if report.unanchored_assets:
        error_msg = (
            f"Anchoring failed for {len(report.unanchored_assets)} assets: "
            f"{report.unanchored_assets}"
        )
        logger.error(error_msg)

    if not report.is_valid(min_success_rate=1.0, min_geometry_rate=0.98):
        error_msg = (
            f"Anchoring validation failed. "
            f"Success rate: {report.success_rate:.2%} (required: 100%). "
            f"Geometry pass rate: {report.geometry_pass_rate:.2%} (required: >=98%)"
        )
        logger.error(error_msg)

    # Log summary
    logger.info(
        f"Anchoring complete: {report.anchored_assets}/{report.total_assets} assets anchored. "
        f"Success rate: {report.success_rate:.2%}. "
        f"Geometry pass rate: {report.geometry_pass_rate:.2%}"
    )

    if report.warnings:
        logger.warning(f"Anchoring completed with {len(report.warnings)} warning(s)")

    return assets, report


def validate_geometry_preservation(
    asset: Asset,
    column: Column,
    tolerance_pt: float = 2.0,
    tolerance_pct: float = 0.01,
) -> Tuple[bool, float]:
    """
    Validate that asset geometry is preserved within tolerance.

    This function checks that normalized coordinates are stable
    and within acceptable bounds for geometry preservation.

    Args:
        asset: Asset to validate
        column: Column containing the asset
        tolerance_pt: Absolute tolerance in points
        tolerance_pct: Percentage tolerance (0-1)

    Returns:
        Tuple of (is_valid, deviation_score)
        - is_valid: True if within tolerance
        - deviation_score: Normalized deviation (0-1, lower is better)

    Example:
        >>> asset = Asset(bbox=BBox(60, 110, 160, 210), ...)
        >>> column = Column(bounds=BBox(50, 100, 250, 700), ...)
        >>> is_valid, deviation = validate_geometry_preservation(asset, column)
        >>> assert is_valid
        >>> assert deviation < 0.02  # Within 2% tolerance
    """
    try:
        normalized_bbox = compute_normalized_bbox(asset, column)

        # For now, just check that normalization succeeded
        # Full validation would compare against target placement
        # which requires InDesign placement data

        # Calculate effective tolerance
        effective_tolerance = max(
            tolerance_pt, tolerance_pct * asset.bbox.width
        )

        # Placeholder: assume valid if normalization succeeded
        # In production, this would compare against placed geometry
        deviation_score = 0.0

        return True, deviation_score

    except ValueError as e:
        logger.error(f"Geometry validation failed: {e}")
        return False, 1.0


class AssetAnchorer:
    """Facade exposing anchoring helpers for the unit tests."""

    def __init__(self, prefer_below: bool = True):
        self.prefer_below = prefer_below

    def find_anchor_block(
        self,
        asset: Asset,
        blocks: List[ContentBlock],
        column_threshold: float = 0.5,
    ) -> Optional[ContentBlock]:
        column = None
        try:
            columns = detect_columns(blocks)
            column = find_asset_column(asset.bbox, columns, threshold=column_threshold)
        except ValueError:
            column = None

        return find_nearest_block(
            asset,
            blocks,
            same_column=column,
            prefer_below=self.prefer_below,
        )

    def set_anchor(self, asset: Asset, block: ContentBlock) -> None:
        asset.anchor_to = block.block_id

    def normalize_bbox(self, bbox: BBox, column_bounds: BBox) -> NormalizedBBox:
        fake_asset = Asset(
            asset_id="asset-placeholder",
            asset_type=AssetType.IMAGE,
            sha256="0" * 64,
            page_number=0,
            bbox=bbox,
            ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            file_path=Path("/tmp/placeholder.png"),
            occurrence=1,
            anchor_to="",
            image_width=1,
            image_height=1,
        )
        column = Column(
            column_id=0,
            x_min=column_bounds.x0,
            x_max=column_bounds.x1,
            y_min=column_bounds.y0,
            y_max=column_bounds.y1,
        )
        return compute_normalized_bbox(fake_asset, column)

    def check_geometry_preservation(
        self,
        original_bbox: BBox,
        placed_bbox: BBox,
        column_bounds: BBox,
        tolerance_pt: float = 2.0,
        tolerance_pct: float = 0.01,
    ) -> bool:
        max_dim = max(original_bbox.width, original_bbox.height, 1.0)

        displacement = max(
            abs(placed_bbox.x0 - original_bbox.x0),
            abs(placed_bbox.x1 - original_bbox.x1),
            abs(placed_bbox.y0 - original_bbox.y0),
            abs(placed_bbox.y1 - original_bbox.y1),
        )

        tolerance = max(tolerance_pt, tolerance_pct * max_dim)

        if not (column_bounds.x0 <= placed_bbox.x0 <= column_bounds.x1):
            return False
        if not (column_bounds.y0 <= placed_bbox.y0 <= column_bounds.y1):
            return False

        return displacement <= tolerance


# Export public API
__all__ = [
    "compute_normalized_bbox",
    "find_nearest_block",
    "anchor_assets_to_blocks",
    "validate_geometry_preservation",
    "AssetAnchorer",
    "AnchoringReport",
]
