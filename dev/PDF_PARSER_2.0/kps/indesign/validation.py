"""Metadata validation functions for InDesign placement.

This module provides comprehensive validation for:
1. Normalized coordinates (0-1 range)
2. CTM matrix validity (non-singular, reasonable values)
3. BBox consistency (original vs normalized vs placed)
4. Placement accuracy verification

All validation functions return lists of error messages:
- Empty list = validation passed
- Non-empty list = validation failed with specific errors

This design allows for accumulating multiple errors in a single pass,
rather than failing on the first error.
"""

from typing import List, Tuple, Optional
import math
import re

from ..core.bbox import BBox, NormalizedBBox
from ..anchoring.columns import Column


# Validation thresholds
TOLERANCE_POINTS = 2.0  # ±2pt tolerance for placement
TOLERANCE_PERCENT = 0.01  # ±1% tolerance for relative errors
CTM_DETERMINANT_MIN = 1e-10  # Minimum determinant for non-singular matrix
CTM_SCALE_MAX = 100.0  # Maximum reasonable scale factor
CTM_SCALE_MIN = 0.001  # Minimum reasonable scale factor

# Asset ID validation pattern: (img|vec|tbl|vecpng|tbllive|unk)-[alphanumeric hash]-p[page]-occ[occurrence]
# The hash can be hexadecimal (production) or descriptive (tests), minimum 4 characters
ASSET_ID_PATTERN = re.compile(r'^(img|vec|tbl|vecpng|tbllive|unk)-[a-z0-9]{4,}-p\d+-occ\d+$')


def validate_normalized_coords(bbox: NormalizedBBox) -> List[str]:
    """
    Validate normalized bbox coordinates are in [0, 1] range.

    Normalized coordinates represent positions relative to column boundaries:
    - x, y: position of top-left corner (0 = left/top, 1 = right/bottom)
    - w, h: width/height (0 = zero size, 1 = full column width/height)

    Args:
        bbox: NormalizedBBox to validate

    Returns:
        List of error messages (empty if valid)

    Example:
        >>> bbox = NormalizedBBox(0.5, 0.2, 0.4, 0.3)
        >>> errors = validate_normalized_coords(bbox)
        >>> assert not errors  # Should be valid
        >>>
        >>> bad_bbox = NormalizedBBox(1.5, -0.1, 0.5, 0.3)
        >>> errors = validate_normalized_coords(bad_bbox)
        >>> print(errors)
        ['x=1.5 out of range [0, 1]', 'y=-0.1 out of range [0, 1]']
    """
    errors = []

    # Check each coordinate
    if not (0 <= bbox.x <= 1):
        errors.append(f"x={bbox.x:.4f} out of range [0, 1]")

    if not (0 <= bbox.y <= 1):
        errors.append(f"y={bbox.y:.4f} out of range [0, 1]")

    if not (0 <= bbox.w <= 1):
        errors.append(f"w={bbox.w:.4f} out of range [0, 1]")

    if not (0 <= bbox.h <= 1):
        errors.append(f"h={bbox.h:.4f} out of range [0, 1]")

    # Check that x + w <= 1 (doesn't extend beyond column)
    if bbox.x + bbox.w > 1.0 + 1e-6:  # Small epsilon for floating point
        errors.append(
            f"x + w = {bbox.x:.4f} + {bbox.w:.4f} = {bbox.x + bbox.w:.4f} > 1.0 "
            "(extends beyond column right edge)"
        )

    # Check that y + h <= 1 (doesn't extend beyond column)
    if bbox.y + bbox.h > 1.0 + 1e-6:
        errors.append(
            f"y + h = {bbox.y:.4f} + {bbox.h:.4f} = {bbox.y + bbox.h:.4f} > 1.0 "
            "(extends beyond column bottom edge)"
        )

    return errors


def validate_asset_id(asset_id: str) -> List[str]:
    """
    Validate asset ID format.

    Asset IDs must follow the pattern:
    (img|vec|tbl)-[hexadecimal hash]-p[page]-occ[occurrence]

    Examples:
        - img-abc12345-p0-occ1
        - vec-def67890-p2-occ3
        - tbl-abcdef01-p5-occ1

    Args:
        asset_id: Asset ID string to validate

    Returns:
        List of error messages (empty if valid)

    Example:
        >>> errors = validate_asset_id("img-abc12345-p0-occ1")
        >>> assert not errors  # Should be valid
        >>>
        >>> errors = validate_asset_id("invalid-id")
        >>> assert errors  # Should have error
    """
    errors = []

    if not ASSET_ID_PATTERN.match(asset_id):
        errors.append(f"Invalid asset_id format: {asset_id}")

    return errors


def validate_ctm(ctm: Tuple[float, ...]) -> List[str]:
    """
    Validate Current Transformation Matrix (CTM).

    CTM format: [a, b, c, d, e, f] where:
    - [a, b, c, d] = 2x2 transformation matrix
    - [e, f] = translation vector

    The matrix performs: [x', y'] = [a*x + c*y + e, b*x + d*y + f]

    Checks:
    1. Exactly 6 elements
    2. Non-singular (determinant != 0)
    3. Reasonable scale factors (not too large/small)
    4. All values are finite (not NaN/Inf)

    Args:
        ctm: CTM tuple with 6 elements

    Returns:
        List of error messages (empty if valid)

    Example:
        >>> ctm = (1.0, 0.0, 0.0, 1.0, 100.0, 200.0)  # Identity + translation
        >>> errors = validate_ctm(ctm)
        >>> assert not errors
        >>>
        >>> bad_ctm = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)  # Singular matrix
        >>> errors = validate_ctm(bad_ctm)
        >>> print(errors[0])
        'CTM matrix is singular (determinant ≈ 0)'
    """
    errors = []

    # Check length
    if len(ctm) != 6:
        return [f"CTM must have 6 elements, got {len(ctm)}"]

    a, b, c, d, e, f = ctm

    # Check for finite values
    for i, value in enumerate(ctm):
        if not math.isfinite(value):
            errors.append(f"CTM[{i}] = {value} is not finite (NaN or Inf)")

    if errors:  # Don't continue if we have non-finite values
        return errors

    # Check determinant (det = a*d - b*c)
    determinant = a * d - b * c

    if abs(determinant) < CTM_DETERMINANT_MIN:
        errors.append(
            f"CTM matrix is singular (determinant ≈ 0): det = {determinant:.2e}"
        )

    # Calculate scale factors
    # Scale X = sqrt(a² + b²)
    # Scale Y = sqrt(c² + d²)
    scale_x = math.sqrt(a**2 + b**2)
    scale_y = math.sqrt(c**2 + d**2)

    # Check scale factors are reasonable
    if scale_x > CTM_SCALE_MAX:
        errors.append(
            f"CTM X-scale factor too large: {scale_x:.2f} (max: {CTM_SCALE_MAX})"
        )

    if scale_x < CTM_SCALE_MIN:
        errors.append(
            f"CTM X-scale factor too small: {scale_x:.6f} (min: {CTM_SCALE_MIN})"
        )

    if scale_y > CTM_SCALE_MAX:
        errors.append(
            f"CTM Y-scale factor too large: {scale_y:.2f} (max: {CTM_SCALE_MAX})"
        )

    if scale_y < CTM_SCALE_MIN:
        errors.append(
            f"CTM Y-scale factor too small: {scale_y:.6f} (min: {CTM_SCALE_MIN})"
        )

    # Check translation values are reasonable (< 10000 pt = ~138 inches)
    if abs(e) > 10000:
        errors.append(f"CTM X-translation too large: {e:.2f} pt")

    if abs(f) > 10000:
        errors.append(f"CTM Y-translation too large: {f:.2f} pt")

    return errors


def validate_bbox_consistency(
    original_bbox: BBox,
    normalized_bbox: NormalizedBBox,
    column_bbox: BBox,
) -> List[str]:
    """
    Validate consistency between original bbox and normalized bbox.

    This function reconstructs the original bbox from normalized coordinates
    and compares it to the actual original bbox. Small discrepancies are
    acceptable due to floating point precision and rounding.

    Args:
        original_bbox: Original bbox from PDF extraction
        normalized_bbox: Normalized bbox relative to column
        column_bbox: Column boundaries for reconstruction

    Returns:
        List of error messages (empty if valid)

    Tolerance:
        - Absolute: ±2pt (TOLERANCE_POINTS)
        - Relative: ±1% (TOLERANCE_PERCENT)

    Example:
        >>> original = BBox(150.0, 200.0, 350.0, 400.0)
        >>> normalized = NormalizedBBox(0.25, 0.5, 0.5, 0.5)
        >>> column = BBox(100.0, 100.0, 500.0, 500.0)
        >>> errors = validate_bbox_consistency(original, normalized, column)
    """
    errors = []

    # Reconstruct bbox from normalized coordinates
    reconstructed = BBox(
        x0=column_bbox.x0 + normalized_bbox.x * column_bbox.width,
        y0=column_bbox.y0 + normalized_bbox.y * column_bbox.height,
        x1=column_bbox.x0 + (normalized_bbox.x + normalized_bbox.w) * column_bbox.width,
        y1=column_bbox.y0 + (normalized_bbox.y + normalized_bbox.h) * column_bbox.height,
    )

    # Compare each coordinate
    coords = [
        ("x0", original_bbox.x0, reconstructed.x0),
        ("y0", original_bbox.y0, reconstructed.y0),
        ("x1", original_bbox.x1, reconstructed.x1),
        ("y1", original_bbox.y1, reconstructed.y1),
    ]

    for name, original, reconstructed_val in coords:
        # Calculate absolute and relative errors
        abs_error = abs(original - reconstructed_val)

        # Avoid division by zero for relative error
        if abs(original) > 1e-6:
            rel_error = abs_error / abs(original)
        else:
            rel_error = 0.0

        # Check tolerances
        if abs_error > TOLERANCE_POINTS and rel_error > TOLERANCE_PERCENT:
            errors.append(
                f"BBox {name} mismatch: original={original:.2f}, "
                f"reconstructed={reconstructed_val:.2f} "
                f"(Δ={abs_error:.2f} pt, {rel_error*100:.2f}%)"
            )

    return errors


def validate_placement_accuracy(
    expected_bbox: BBox,
    actual_bbox: BBox,
    tolerance_pt: float = TOLERANCE_POINTS,
) -> List[str]:
    """
    Validate InDesign placement accuracy.

    Compares expected placement (calculated from normalized coords) with
    actual placement (extracted from InDesign).

    Args:
        expected_bbox: Expected bbox calculated from normalized coords
        actual_bbox: Actual bbox from InDesign geometric bounds
        tolerance_pt: Maximum acceptable deviation in points

    Returns:
        List of error messages (empty if within tolerance)

    Example:
        >>> expected = BBox(100.0, 200.0, 300.0, 400.0)
        >>> actual = BBox(100.5, 200.2, 300.1, 400.3)
        >>> errors = validate_placement_accuracy(expected, actual, tolerance_pt=2.0)
        >>> assert not errors  # All deviations < 2pt
    """
    errors = []

    # Calculate deviations for each coordinate
    deviations = {
        "x0": abs(expected_bbox.x0 - actual_bbox.x0),
        "y0": abs(expected_bbox.y0 - actual_bbox.y0),
        "x1": abs(expected_bbox.x1 - actual_bbox.x1),
        "y1": abs(expected_bbox.y1 - actual_bbox.y1),
    }

    # Check each deviation
    for coord, deviation in deviations.items():
        if deviation > tolerance_pt:
            errors.append(
                f"Placement error at {coord}: expected={getattr(expected_bbox, coord):.2f}, "
                f"actual={getattr(actual_bbox, coord):.2f} "
                f"(Δ={deviation:.2f} pt, tolerance={tolerance_pt:.2f} pt)"
            )

    # Calculate dimension errors
    width_error = abs(expected_bbox.width - actual_bbox.width)
    height_error = abs(expected_bbox.height - actual_bbox.height)

    if width_error > tolerance_pt:
        errors.append(
            f"Width mismatch: expected={expected_bbox.width:.2f}, "
            f"actual={actual_bbox.width:.2f} (Δ={width_error:.2f} pt)"
        )

    if height_error > tolerance_pt:
        errors.append(
            f"Height mismatch: expected={expected_bbox.height:.2f}, "
            f"actual={actual_bbox.height:.2f} (Δ={height_error:.2f} pt)"
        )

    return errors


def validate_column_assignment(
    bbox: BBox,
    column: Column,
    threshold: float = 0.5,
) -> List[str]:
    """
    Validate that a bbox is correctly assigned to a column.

    Checks that the bbox has sufficient horizontal overlap with the column.

    Args:
        bbox: BBox to validate
        column: Column it's assigned to
        threshold: Minimum overlap ratio (0-1)

    Returns:
        List of error messages (empty if valid)

    Example:
        >>> bbox = BBox(150, 200, 350, 400)
        >>> column = Column(column_id=0, x_min=100, x_max=400, y_min=100, y_max=500)
        >>> errors = validate_column_assignment(bbox, column)
    """
    errors = []

    # Calculate horizontal overlap
    overlap_left = max(column.x_min, bbox.x0)
    overlap_right = min(column.x_max, bbox.x1)
    overlap_width = max(0, overlap_right - overlap_left)

    # Calculate overlap ratio
    if bbox.width > 0:
        overlap_ratio = overlap_width / bbox.width
    else:
        return ["BBox has zero width"]

    # Check threshold
    if overlap_ratio < threshold:
        errors.append(
            f"Insufficient column overlap: {overlap_ratio*100:.1f}% "
            f"(threshold: {threshold*100:.1f}%). "
            f"BBox x-range: [{bbox.x0:.1f}, {bbox.x1:.1f}], "
            f"Column x-range: [{column.x_min:.1f}, {column.x_max:.1f}]"
        )

    return errors


def validate_aspect_ratio(
    original_bbox: BBox,
    placed_bbox: BBox,
    tolerance: float = 0.05,
) -> List[str]:
    """
    Validate that aspect ratio is preserved during placement.

    Checks that the placed asset maintains the same aspect ratio as the
    original (within tolerance). Large deviations suggest improper scaling.

    Args:
        original_bbox: Original bbox from PDF
        placed_bbox: Placed bbox in InDesign
        tolerance: Maximum acceptable aspect ratio deviation (as fraction)

    Returns:
        List of error messages (empty if valid)

    Example:
        >>> original = BBox(0, 0, 200, 100)  # 2:1 aspect ratio
        >>> placed = BBox(0, 0, 400, 200)    # Still 2:1
        >>> errors = validate_aspect_ratio(original, placed)
        >>> assert not errors
    """
    errors = []

    # Calculate aspect ratios
    if original_bbox.height > 0:
        original_aspect = original_bbox.width / original_bbox.height
    else:
        return ["Original bbox has zero height"]

    if placed_bbox.height > 0:
        placed_aspect = placed_bbox.width / placed_bbox.height
    else:
        return ["Placed bbox has zero height"]

    # Calculate relative deviation
    if original_aspect > 0:
        aspect_deviation = abs(placed_aspect - original_aspect) / original_aspect
    else:
        return ["Original bbox has zero aspect ratio"]

    # Check tolerance
    if aspect_deviation > tolerance:
        errors.append(
            f"Aspect ratio mismatch: original={original_aspect:.3f}, "
            f"placed={placed_aspect:.3f} "
            f"(deviation={aspect_deviation*100:.1f}%, tolerance={tolerance*100:.1f}%)"
        )

    return errors


def validate_dpi(
    image_dimensions: Tuple[int, int],
    placed_bbox: BBox,
    min_dpi: float = 200.0,
    max_dpi: float = 600.0,
) -> List[str]:
    """
    Validate image DPI at placed size.

    Calculates effective DPI and checks if it's within acceptable range
    for print quality (typically 200-600 DPI).

    Args:
        image_dimensions: (width, height) in pixels
        placed_bbox: Placed bbox in points (72 DPI)
        min_dpi: Minimum acceptable DPI
        max_dpi: Maximum acceptable DPI (too high wastes space)

    Returns:
        List of error messages and warnings

    Example:
        >>> image_dims = (1200, 800)  # pixels
        >>> placed = BBox(0, 0, 300, 200)  # 4.17 x 2.78 inches at 72 DPI
        >>> errors = validate_dpi(image_dims, placed)
        >>> # 1200 / 4.17 = 288 DPI (acceptable)
    """
    errors = []

    pixel_width, pixel_height = image_dimensions

    # Convert placed size from points to inches (72 pt = 1 inch)
    placed_width_inches = placed_bbox.width / 72.0
    placed_height_inches = placed_bbox.height / 72.0

    # Calculate DPI
    if placed_width_inches > 0:
        dpi_x = pixel_width / placed_width_inches
    else:
        return ["Placed width is zero"]

    if placed_height_inches > 0:
        dpi_y = pixel_height / placed_height_inches
    else:
        return ["Placed height is zero"]

    # Use average DPI
    dpi_avg = (dpi_x + dpi_y) / 2

    # Check minimum DPI
    if dpi_avg < min_dpi:
        errors.append(
            f"WARNING: Low DPI: {dpi_avg:.1f} DPI "
            f"(min recommended: {min_dpi:.1f} DPI). "
            f"Image may appear pixelated in print."
        )

    # Check maximum DPI (informational)
    if dpi_avg > max_dpi:
        errors.append(
            f"INFO: High DPI: {dpi_avg:.1f} DPI "
            f"(max typical: {max_dpi:.1f} DPI). "
            f"File size could be reduced without quality loss."
        )

    # Check DPI consistency between X and Y
    dpi_diff = abs(dpi_x - dpi_y)
    if dpi_diff > 10.0:  # More than 10 DPI difference
        errors.append(
            f"WARNING: Inconsistent DPI: X={dpi_x:.1f}, Y={dpi_y:.1f} "
            f"(difference: {dpi_diff:.1f}). "
            f"Image may be distorted."
        )

    return errors
