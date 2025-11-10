"""Tolerance calculations and validation for geometry preservation.

This module provides utilities for calculating acceptable tolerances
for geometry preservation validation in the KPS QA suite.

Tolerance Strategy:
    - Absolute tolerance: ±2pt (physical precision)
    - Relative tolerance: ±1% of asset size (scale-independent)
    - Whichever is MORE strict applies

Author: KPS v2.0 QA Suite
Last Modified: 2025-11-06
"""

from dataclasses import dataclass
from typing import Tuple
from ..core.bbox import BBox


@dataclass
class ToleranceSpec:
    """Tolerance specification for geometry validation.

    Attributes:
        absolute_pt: Absolute tolerance in PDF points
        relative_pct: Relative tolerance as percentage (0-1)
        apply_strict: If True, use stricter of absolute/relative (default)
    """

    absolute_pt: float = 2.0
    relative_pct: float = 0.01  # 1%
    apply_strict: bool = True


class ToleranceCalculator:
    """Calculate effective tolerances for geometry validation."""

    def __init__(self, spec: ToleranceSpec = None):
        """Initialize calculator with tolerance specification.

        Args:
            spec: ToleranceSpec, defaults to standard (2pt, 1%)
        """
        self.spec = spec or ToleranceSpec()

    def calculate_effective_tolerance(
        self,
        bbox: BBox,
        dimension: str = "both"
    ) -> float:
        """Calculate effective tolerance for a given bbox.

        Args:
            bbox: BBox to calculate tolerance for
            dimension: "width", "height", or "both" (uses max)

        Returns:
            Effective tolerance in points
        """
        # Calculate relative tolerance based on bbox size
        if dimension == "width":
            size = bbox.width
        elif dimension == "height":
            size = bbox.height
        else:  # "both"
            size = max(bbox.width, bbox.height)

        relative_tolerance_pt = size * self.spec.relative_pct

        # Apply strict or lenient rule
        if self.spec.apply_strict:
            # Stricter of absolute or relative
            return min(self.spec.absolute_pt, relative_tolerance_pt)
        else:
            # Lenient: more generous tolerance
            return max(self.spec.absolute_pt, relative_tolerance_pt)

    def is_within_tolerance(
        self,
        error: float,
        bbox: BBox,
        dimension: str = "both"
    ) -> bool:
        """Check if error is within tolerance.

        Args:
            error: Error value in points (absolute)
            bbox: BBox for calculating relative tolerance
            dimension: "width", "height", or "both"

        Returns:
            True if error is within tolerance
        """
        tolerance = self.calculate_effective_tolerance(bbox, dimension)
        return abs(error) <= tolerance

    def calculate_tolerance_for_error(
        self,
        error_x: float,
        error_y: float,
        bbox: BBox
    ) -> Tuple[float, float, bool]:
        """Calculate tolerance and check if errors are acceptable.

        Args:
            error_x: X-axis error in points
            error_y: Y-axis error in points
            bbox: BBox for calculating relative tolerance

        Returns:
            Tuple of (tolerance_x, tolerance_y, passed)
        """
        tolerance_x = self.calculate_effective_tolerance(bbox, "width")
        tolerance_y = self.calculate_effective_tolerance(bbox, "height")

        passed_x = abs(error_x) <= tolerance_x
        passed_y = abs(error_y) <= tolerance_y

        return tolerance_x, tolerance_y, (passed_x and passed_y)

    def calculate_tolerance_breakdown(
        self,
        bbox: BBox
    ) -> dict:
        """Get detailed tolerance breakdown for debugging.

        Args:
            bbox: BBox to analyze

        Returns:
            Dict with tolerance details
        """
        absolute_tol = self.spec.absolute_pt
        relative_tol_x = bbox.width * self.spec.relative_pct
        relative_tol_y = bbox.height * self.spec.relative_pct

        effective_x = self.calculate_effective_tolerance(bbox, "width")
        effective_y = self.calculate_effective_tolerance(bbox, "height")

        return {
            "absolute_tolerance_pt": absolute_tol,
            "relative_tolerance_pct": self.spec.relative_pct * 100,
            "bbox_width": bbox.width,
            "bbox_height": bbox.height,
            "relative_tolerance_x_pt": relative_tol_x,
            "relative_tolerance_y_pt": relative_tol_y,
            "effective_tolerance_x_pt": effective_x,
            "effective_tolerance_y_pt": effective_y,
            "stricter_rule_applied": self.spec.apply_strict
        }


def calculate_scale_tolerance(
    expected_size: float,
    relative_pct: float = 0.02  # 2% for scale
) -> float:
    """Calculate tolerance for scale/size preservation.

    Scale errors are typically more lenient than position errors.

    Args:
        expected_size: Expected dimension in points
        relative_pct: Relative tolerance (default: 2%)

    Returns:
        Scale tolerance in points
    """
    return expected_size * relative_pct


def calculate_aspect_ratio_tolerance(
    width: float,
    height: float,
    tolerance_pct: float = 0.01  # 1%
) -> float:
    """Calculate tolerance for aspect ratio preservation.

    Args:
        width: Original width
        height: Original height
        tolerance_pct: Tolerance percentage (default: 1%)

    Returns:
        Acceptable aspect ratio deviation
    """
    if height == 0:
        return 0.0

    aspect_ratio = width / height
    return aspect_ratio * tolerance_pct


def is_aspect_ratio_preserved(
    expected_bbox: BBox,
    actual_bbox: BBox,
    tolerance_pct: float = 0.01
) -> Tuple[bool, float]:
    """Check if aspect ratio is preserved within tolerance.

    Args:
        expected_bbox: Expected bbox
        actual_bbox: Actual bbox
        tolerance_pct: Tolerance percentage (default: 1%)

    Returns:
        Tuple of (preserved, actual_deviation)
    """
    if expected_bbox.height == 0 or actual_bbox.height == 0:
        return False, float('inf')

    expected_ratio = expected_bbox.width / expected_bbox.height
    actual_ratio = actual_bbox.width / actual_bbox.height

    # Calculate relative deviation
    deviation = abs(actual_ratio - expected_ratio) / expected_ratio

    return (deviation <= tolerance_pct), deviation


def summarize_tolerance_results(
    passed_count: int,
    failed_count: int,
    tolerance_spec: ToleranceSpec
) -> dict:
    """Summarize tolerance validation results.

    Args:
        passed_count: Number of assets within tolerance
        failed_count: Number of assets outside tolerance
        tolerance_spec: Tolerance specification used

    Returns:
        Summary dict
    """
    total = passed_count + failed_count
    pass_rate = (passed_count / total * 100) if total > 0 else 0.0

    return {
        "total_assets": total,
        "passed": passed_count,
        "failed": failed_count,
        "pass_rate_pct": pass_rate,
        "tolerance_absolute_pt": tolerance_spec.absolute_pt,
        "tolerance_relative_pct": tolerance_spec.relative_pct * 100,
        "strict_mode": tolerance_spec.apply_strict
    }
