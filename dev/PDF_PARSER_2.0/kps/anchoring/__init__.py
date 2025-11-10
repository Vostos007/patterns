"""KPS Anchoring module - Column detection and asset-to-text anchoring."""

from .columns import (
    Column,
    detect_columns,
    find_block_column,
    find_asset_column,
)
from .anchor import (
    compute_normalized_bbox,
    find_nearest_block,
    anchor_assets_to_blocks,
    validate_geometry_preservation,
    AnchoringReport,
)

__all__ = [
    # Column detection
    "Column",
    "detect_columns",
    "find_block_column",
    "find_asset_column",
    # Anchoring algorithm
    "compute_normalized_bbox",
    "find_nearest_block",
    "anchor_assets_to_blocks",
    "validate_geometry_preservation",
    "AnchoringReport",
]
