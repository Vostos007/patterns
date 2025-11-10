"""Coordinate Conversion and Asset Placement Utilities.

This module provides utilities for converting between different coordinate systems
used in the KPS pipeline:

1. PDF Coordinates: Origin at bottom-left, y-axis points up
2. InDesign Coordinates: Origin at top-left, y-axis points down
3. Normalized Coordinates: 0-1 range relative to column bounds

Author: KPS v2.0 InDesign Automation
Last Modified: 2025-11-06
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..anchoring.columns import Column
from ..core.bbox import BBox, NormalizedBBox


@dataclass
class PlacementSpec:
    """Complete specification for placing an asset in InDesign.

    Attributes:
        asset_id: Unique asset identifier
        page_number: Target page (0-indexed)
        indesign_bounds: Bounds in InDesign coordinate system [y1, x0, y0, x1]
        rotation: Rotation angle in degrees (default: 0)
        scale_x: Horizontal scale factor (default: 1.0)
        scale_y: Vertical scale factor (default: 1.0)
        file_path: Path to asset file
    """

    asset_id: str
    page_number: int
    indesign_bounds: List[float]  # [y1, x0, y0, x1]
    rotation: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    file_path: Optional[str] = None


class CoordinateConverter:
    """Convert between different coordinate systems."""

    def __init__(self, page_width: float, page_height: float):
        """Initialize converter with page dimensions.

        Args:
            page_width: Page width in points (72 DPI)
            page_height: Page height in points (72 DPI)
        """
        self.page_width = page_width
        self.page_height = page_height

    def pdf_to_indesign(self, bbox: BBox) -> List[float]:
        """Convert PDF bbox to InDesign geometric bounds.

        PDF coordinate system:
        - Origin at bottom-left
        - x increases right
        - y increases up

        InDesign coordinate system:
        - Origin at top-left
        - x increases right
        - y increases down
        - Format: [top, left, bottom, right] = [y1, x0, y0, x1]

        Args:
            bbox: BBox in PDF coordinates

        Returns:
            InDesign geometric bounds [y1, x0, y0, x1]
        """
        # Flip y-coordinates
        indesign_top = self.page_height - bbox.y1
        indesign_bottom = self.page_height - bbox.y0

        return [
            indesign_top,  # y1 (top)
            bbox.x0,  # x0 (left)
            indesign_bottom,  # y0 (bottom)
            bbox.x1,  # x1 (right)
        ]

    def indesign_to_pdf(self, bounds: List[float]) -> BBox:
        """Convert InDesign geometric bounds to PDF bbox.

        Args:
            bounds: InDesign bounds [y1, x0, y0, x1]

        Returns:
            BBox in PDF coordinates
        """
        # Unpack InDesign format
        top, left, bottom, right = bounds

        # Flip y-coordinates
        pdf_y0 = self.page_height - bottom
        pdf_y1 = self.page_height - top

        return BBox(x0=left, y0=pdf_y0, x1=right, y1=pdf_y1)

    def normalized_to_pdf(
        self, normalized: NormalizedBBox, column: Column
    ) -> BBox:
        """Convert normalized coordinates to PDF coordinates.

        Args:
            normalized: Normalized bbox (0-1 range relative to column)
            column: Column bounds in PDF coordinates

        Returns:
            BBox in PDF coordinates
        """
        x0 = column.x_min + normalized.x * column.width
        y0 = column.y_min + normalized.y * column.height
        width = normalized.w * column.width
        height = normalized.h * column.height

        return BBox(x0=x0, y0=y0, x1=x0 + width, y1=y0 + height)

    def pdf_to_normalized(self, bbox: BBox, column: Column) -> NormalizedBBox:
        """Convert PDF coordinates to normalized coordinates.

        Args:
            bbox: BBox in PDF coordinates
            column: Column bounds in PDF coordinates

        Returns:
            Normalized bbox (0-1 range relative to column)
        """
        x = (bbox.x0 - column.x_min) / column.width
        y = (bbox.y0 - column.y_min) / column.height
        w = bbox.width / column.width
        h = bbox.height / column.height

        return NormalizedBBox(x=x, y=y, w=w, h=h)


def calculate_placement_position(
    normalized_bbox: NormalizedBBox, column: Column, page_height: float
) -> BBox:
    """Calculate placement position from normalized coordinates.

    This is the main function for converting asset coordinates from the
    normalized (0-1) system to actual PDF points for InDesign placement.

    Args:
        normalized_bbox: Normalized coordinates (0-1 range)
        column: Column bounds in PDF coordinates
        page_height: Page height in points

    Returns:
        BBox in PDF coordinates ready for placement

    Example:
        >>> normalized = NormalizedBBox(x=0.1, y=0.2, w=0.3, h=0.4)
        >>> column = Column(
        ...     column_id=0,
        ...     x_min=50.0,
        ...     x_max=300.0,
        ...     y_min=100.0,
        ...     y_max=700.0,
        ...     blocks=[]
        ... )
        >>> bbox = calculate_placement_position(normalized, column, 792.0)
        >>> print(f"x0={bbox.x0}, y0={bbox.y0}")
        x0=75.0, y0=220.0
    """
    converter = CoordinateConverter(
        page_width=column.x_max,  # Approximate
        page_height=page_height,
    )

    return converter.normalized_to_pdf(normalized, column)


def calculate_placement_spec(
    asset_id: str,
    page_number: int,
    normalized_bbox: NormalizedBBox,
    column: Column,
    page_height: float,
    file_path: Optional[str] = None,
    ctm: Optional[Tuple[float, float, float, float, float, float]] = None,
) -> PlacementSpec:
    """Calculate complete placement specification for an asset.

    Args:
        asset_id: Asset identifier
        page_number: Target page (0-indexed)
        normalized_bbox: Normalized coordinates
        column: Column bounds
        page_height: Page height in points
        file_path: Optional path to asset file
        ctm: Optional transformation matrix [a, b, c, d, e, f]

    Returns:
        PlacementSpec ready for InDesign placement
    """
    # Convert normalized to PDF coordinates
    pdf_bbox = calculate_placement_position(normalized_bbox, column, page_height)

    # Convert PDF to InDesign coordinates
    converter = CoordinateConverter(
        page_width=column.x_max, page_height=page_height
    )
    indesign_bounds = converter.pdf_to_indesign(pdf_bbox)

    # Extract transformation parameters from CTM if provided
    rotation = 0.0
    scale_x = 1.0
    scale_y = 1.0

    if ctm:
        a, b, c, d, e, f = ctm
        scale_x = a  # Horizontal scale
        scale_y = d  # Vertical scale

        # Calculate rotation from skew components
        if b != 0 or c != 0:
            import math

            rotation = math.atan2(b, a) * (180 / math.pi)

    return PlacementSpec(
        asset_id=asset_id,
        page_number=page_number,
        indesign_bounds=indesign_bounds,
        rotation=rotation,
        scale_x=scale_x,
        scale_y=scale_y,
        file_path=file_path,
    )


def find_asset_column(
    bbox: BBox, columns: List[Column], threshold: float = 0.5
) -> Optional[Column]:
    """Find which column an asset belongs to based on horizontal overlap.

    Args:
        bbox: Asset bbox in PDF coordinates
        columns: List of columns
        threshold: Minimum overlap ratio (0-1) to consider

    Returns:
        Column with maximum overlap, or None if no sufficient overlap
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


def validate_placement_bounds(
    bounds: List[float], page_width: float, page_height: float, tolerance: float = 2.0
) -> Tuple[bool, Optional[str]]:
    """Validate that placement bounds are within page boundaries.

    Args:
        bounds: InDesign bounds [y1, x0, y0, x1]
        page_width: Page width in points
        page_height: Page height in points
        tolerance: Tolerance in points for boundary checks

    Returns:
        Tuple of (is_valid, error_message)
    """
    top, left, bottom, right = bounds

    # Check horizontal bounds
    if left < -tolerance or right > page_width + tolerance:
        return (
            False,
            f"Horizontal bounds out of range: left={left}, right={right}, page_width={page_width}",
        )

    # Check vertical bounds
    if top < -tolerance or bottom > page_height + tolerance:
        return (
            False,
            f"Vertical bounds out of range: top={top}, bottom={bottom}, page_height={page_height}",
        )

    # Check bounds order
    if left >= right:
        return False, f"Invalid horizontal order: left={left} >= right={right}"

    if top >= bottom:
        return False, f"Invalid vertical order: top={top} >= bottom={bottom}"

    return True, None


def calculate_dpi(
    bbox: BBox, image_width: int, image_height: int
) -> Tuple[float, float]:
    """Calculate DPI (dots per inch) from bbox and image dimensions.

    Args:
        bbox: Asset bbox in PDF points (72 DPI)
        image_width: Image width in pixels
        image_height: Image height in pixels

    Returns:
        Tuple of (dpi_x, dpi_y)
    """
    # PDF points to inches (72 points = 1 inch)
    bbox_width_inches = bbox.width / 72.0
    bbox_height_inches = bbox.height / 72.0

    # Calculate DPI
    dpi_x = image_width / bbox_width_inches if bbox_width_inches > 0 else 0
    dpi_y = image_height / bbox_height_inches if bbox_height_inches > 0 else 0

    return dpi_x, dpi_y


def suggest_scaling(
    bbox: BBox,
    image_width: int,
    image_height: int,
    target_dpi: float = 300.0,
) -> Tuple[float, float]:
    """Suggest scaling factors to achieve target DPI.

    Args:
        bbox: Asset bbox in PDF points
        image_width: Image width in pixels
        image_height: Image height in pixels
        target_dpi: Target DPI (default: 300)

    Returns:
        Tuple of (scale_x, scale_y) as percentages
    """
    current_dpi_x, current_dpi_y = calculate_dpi(bbox, image_width, image_height)

    if current_dpi_x == 0 or current_dpi_y == 0:
        return 100.0, 100.0

    # Calculate scale factors to achieve target DPI
    scale_x = (current_dpi_x / target_dpi) * 100.0
    scale_y = (current_dpi_y / target_dpi) * 100.0

    return scale_x, scale_y


# ============================================================================
# Batch Operations
# ============================================================================


def batch_calculate_placements(
    assets: List[dict],
    columns: List[Column],
    page_height: float,
) -> List[PlacementSpec]:
    """Calculate placement specs for multiple assets.

    Args:
        assets: List of asset dicts with normalized_bbox and other properties
        columns: List of columns
        page_height: Page height in points

    Returns:
        List of PlacementSpec objects
    """
    placement_specs = []

    for asset in assets:
        # Extract asset properties
        asset_id = asset["asset_id"]
        page_number = asset["page_number"]
        normalized_bbox = NormalizedBBox(**asset["normalized_bbox"])
        file_path = asset.get("file_path")
        ctm = tuple(asset["ctm"]) if "ctm" in asset else None

        # Find asset's column
        # First try to use column_id if available
        column = None
        if "column_id" in asset:
            column_id = asset["column_id"]
            column = next((c for c in columns if c.column_id == column_id), None)

        # If no column found, try to find by bbox
        if column is None and "bbox" in asset:
            bbox = BBox(**asset["bbox"])
            column = find_asset_column(bbox, columns)

        # Skip if no column found
        if column is None:
            continue

        # Calculate placement spec
        spec = calculate_placement_spec(
            asset_id=asset_id,
            page_number=page_number,
            normalized_bbox=normalized_bbox,
            column=column,
            page_height=page_height,
            file_path=file_path,
            ctm=ctm,
        )

        placement_specs.append(spec)

    return placement_specs
