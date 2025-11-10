"""Placement error analysis for geometry preservation validation.

This module analyzes placement errors between expected and actual
asset positions, providing detailed metrics and diagnostics.

Error Types:
    - Translation errors: X/Y offset from expected position
    - Scale errors: Width/height differences
    - Rotation errors: Angular deviations (if applicable)
    - Aspect ratio errors: Shape distortion

Author: KPS v2.0 QA Suite
Last Modified: 2025-11-06
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple
import statistics

from ..core.bbox import BBox
from .tolerance import ToleranceCalculator, ToleranceSpec


@dataclass
class PlacementError:
    """Placement error for a single asset.

    Attributes:
        asset_id: Asset identifier
        expected_bbox: Expected placement bbox
        actual_bbox: Actual placement bbox
        translation_error: (dx, dy) offset in points
        scale_error: (width_ratio, height_ratio)
        absolute_error: Maximum of |dx|, |dy| in points
        relative_error: Error as fraction of asset size
        passed: True if within tolerance
        tolerance_used: Tolerance value applied (in points)
    """

    asset_id: str
    expected_bbox: BBox
    actual_bbox: BBox
    translation_error: Tuple[float, float]
    scale_error: Tuple[float, float]
    absolute_error: float
    relative_error: float
    passed: bool
    tolerance_used: Optional[float] = None

    @property
    def translation_magnitude(self) -> float:
        """Calculate magnitude of translation error vector."""
        dx, dy = self.translation_error
        return math.sqrt(dx**2 + dy**2)

    @property
    def scale_deviation(self) -> float:
        """Calculate maximum scale deviation from 1.0."""
        width_ratio, height_ratio = self.scale_error
        return max(abs(width_ratio - 1.0), abs(height_ratio - 1.0))

    @property
    def aspect_ratio_error(self) -> float:
        """Calculate aspect ratio preservation error."""
        if self.expected_bbox.height == 0 or self.actual_bbox.height == 0:
            return float('inf')

        expected_ratio = self.expected_bbox.width / self.expected_bbox.height
        actual_ratio = self.actual_bbox.width / self.actual_bbox.height

        if expected_ratio == 0:
            return float('inf')

        return abs(actual_ratio - expected_ratio) / expected_ratio

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "asset_id": self.asset_id,
            "expected": [
                self.expected_bbox.x0,
                self.expected_bbox.y0,
                self.expected_bbox.x1,
                self.expected_bbox.y1
            ],
            "actual": [
                self.actual_bbox.x0,
                self.actual_bbox.y0,
                self.actual_bbox.x1,
                self.actual_bbox.y1
            ],
            "translation_error_pt": {
                "dx": self.translation_error[0],
                "dy": self.translation_error[1],
                "magnitude": self.translation_magnitude
            },
            "scale_error_ratio": {
                "width": self.scale_error[0],
                "height": self.scale_error[1],
                "max_deviation": self.scale_deviation
            },
            "absolute_error_pt": self.absolute_error,
            "relative_error_pct": self.relative_error * 100,
            "aspect_ratio_error_pct": self.aspect_ratio_error * 100,
            "tolerance_pt": self.tolerance_used,
            "passed": self.passed
        }


class ErrorAnalyzer:
    """Analyze placement errors for geometry validation."""

    def __init__(
        self,
        tolerance_spec: Optional[ToleranceSpec] = None
    ):
        """Initialize error analyzer.

        Args:
            tolerance_spec: Tolerance specification for validation
        """
        self.tolerance_calc = ToleranceCalculator(tolerance_spec)
        self.tolerance_spec = tolerance_spec or ToleranceSpec()

    def calculate_error(
        self,
        asset_id: str,
        expected: BBox,
        actual: BBox
    ) -> PlacementError:
        """Calculate placement error between expected and actual.

        Args:
            asset_id: Asset identifier
            expected: Expected placement bbox
            actual: Actual placement bbox

        Returns:
            PlacementError with detailed metrics
        """
        # Translation error (center point offset)
        expected_center = expected.center
        actual_center = actual.center

        dx = actual_center[0] - expected_center[0]
        dy = actual_center[1] - expected_center[1]

        # Scale error (size differences)
        width_ratio = actual.width / expected.width if expected.width > 0 else 1.0
        height_ratio = actual.height / expected.height if expected.height > 0 else 1.0

        # Absolute error (max offset)
        absolute_error = max(abs(dx), abs(dy))

        # Relative error (as fraction of expected size)
        expected_size = max(expected.width, expected.height)
        relative_error = absolute_error / expected_size if expected_size > 0 else 0.0

        # Check tolerance
        tolerance = self.tolerance_calc.calculate_effective_tolerance(expected)
        passed = absolute_error <= tolerance

        return PlacementError(
            asset_id=asset_id,
            expected_bbox=expected,
            actual_bbox=actual,
            translation_error=(dx, dy),
            scale_error=(width_ratio, height_ratio),
            absolute_error=absolute_error,
            relative_error=relative_error,
            passed=passed,
            tolerance_used=tolerance
        )

    def analyze_systematic_errors(
        self,
        errors: List[PlacementError]
    ) -> dict:
        """Analyze for systematic errors across all assets.

        Systematic errors indicate issues with coordinate conversion,
        page setup, or alignment algorithms.

        Args:
            errors: List of placement errors

        Returns:
            Dict with systematic error analysis
        """
        if not errors:
            return {
                "has_systematic_x": False,
                "has_systematic_y": False,
                "mean_x_offset": 0.0,
                "mean_y_offset": 0.0
            }

        # Calculate mean offsets
        x_errors = [e.translation_error[0] for e in errors]
        y_errors = [e.translation_error[1] for e in errors]

        mean_x = statistics.mean(x_errors)
        mean_y = statistics.mean(y_errors)

        # Calculate standard deviations
        stdev_x = statistics.stdev(x_errors) if len(x_errors) > 1 else 0.0
        stdev_y = statistics.stdev(y_errors) if len(y_errors) > 1 else 0.0

        # Systematic error threshold: mean > 1pt and stdev < 2pt
        # (most errors clustered around same offset)
        has_systematic_x = abs(mean_x) > 1.0 and stdev_x < 2.0
        has_systematic_y = abs(mean_y) > 1.0 and stdev_y < 2.0

        return {
            "has_systematic_x": has_systematic_x,
            "has_systematic_y": has_systematic_y,
            "mean_x_offset": mean_x,
            "mean_y_offset": mean_y,
            "stdev_x": stdev_x,
            "stdev_y": stdev_y,
            "count": len(errors)
        }

    def analyze_scale_errors(
        self,
        errors: List[PlacementError]
    ) -> dict:
        """Analyze scale/size preservation errors.

        Args:
            errors: List of placement errors

        Returns:
            Dict with scale error analysis
        """
        if not errors:
            return {
                "has_scale_issues": False,
                "mean_width_ratio": 1.0,
                "mean_height_ratio": 1.0
            }

        width_ratios = [e.scale_error[0] for e in errors]
        height_ratios = [e.scale_error[1] for e in errors]

        mean_width = statistics.mean(width_ratios)
        mean_height = statistics.mean(height_ratios)

        # Scale issue threshold: mean deviation > 2% from 1.0
        width_deviation = abs(mean_width - 1.0)
        height_deviation = abs(mean_height - 1.0)

        has_scale_issues = (width_deviation > 0.02 or height_deviation > 0.02)

        return {
            "has_scale_issues": has_scale_issues,
            "mean_width_ratio": mean_width,
            "mean_height_ratio": mean_height,
            "width_deviation_pct": width_deviation * 100,
            "height_deviation_pct": height_deviation * 100
        }

    def identify_worst_offenders(
        self,
        errors: List[PlacementError],
        count: int = 10
    ) -> List[PlacementError]:
        """Identify worst placement errors.

        Args:
            errors: List of placement errors
            count: Number of worst offenders to return

        Returns:
            List of worst errors, sorted by absolute error
        """
        sorted_errors = sorted(
            errors,
            key=lambda e: e.absolute_error,
            reverse=True
        )
        return sorted_errors[:count]

    def calculate_error_statistics(
        self,
        errors: List[PlacementError]
    ) -> dict:
        """Calculate statistical summary of errors.

        Args:
            errors: List of placement errors

        Returns:
            Dict with error statistics
        """
        if not errors:
            return {
                "count": 0,
                "mean": 0.0,
                "median": 0.0,
                "max": 0.0,
                "min": 0.0,
                "stdev": 0.0
            }

        absolute_errors = [e.absolute_error for e in errors]

        return {
            "count": len(absolute_errors),
            "mean": statistics.mean(absolute_errors),
            "median": statistics.median(absolute_errors),
            "max": max(absolute_errors),
            "min": min(absolute_errors),
            "stdev": statistics.stdev(absolute_errors) if len(absolute_errors) > 1 else 0.0,
            "p95": statistics.quantiles(absolute_errors, n=20)[18] if len(absolute_errors) >= 20 else max(absolute_errors)
        }

    def categorize_errors(
        self,
        errors: List[PlacementError]
    ) -> dict:
        """Categorize errors by severity.

        Args:
            errors: List of placement errors

        Returns:
            Dict with error categories
        """
        within_tolerance = [e for e in errors if e.passed]
        outside_tolerance = [e for e in errors if not e.passed]

        # Further categorize outside tolerance
        minor = [e for e in outside_tolerance if e.absolute_error <= 5.0]
        moderate = [e for e in outside_tolerance if 5.0 < e.absolute_error <= 10.0]
        severe = [e for e in outside_tolerance if e.absolute_error > 10.0]

        return {
            "within_tolerance": len(within_tolerance),
            "outside_tolerance": len(outside_tolerance),
            "minor_errors": len(minor),  # 2-5pt
            "moderate_errors": len(moderate),  # 5-10pt
            "severe_errors": len(severe),  # >10pt
            "total": len(errors)
        }

    def generate_error_histogram(
        self,
        errors: List[PlacementError],
        bins: int = 10
    ) -> dict:
        """Generate histogram of error distribution.

        Args:
            errors: List of placement errors
            bins: Number of histogram bins

        Returns:
            Dict with histogram data
        """
        if not errors:
            return {"bins": [], "counts": []}

        absolute_errors = [e.absolute_error for e in errors]
        max_error = max(absolute_errors)
        min_error = min(absolute_errors)

        bin_width = (max_error - min_error) / bins if bins > 0 else 1.0
        bin_edges = [min_error + i * bin_width for i in range(bins + 1)]

        # Count errors in each bin
        counts = [0] * bins
        for error in absolute_errors:
            bin_idx = min(int((error - min_error) / bin_width), bins - 1)
            counts[bin_idx] += 1

        return {
            "bins": bin_edges,
            "counts": counts,
            "bin_width": bin_width
        }


def analyze_error_patterns(
    errors: List[PlacementError]
) -> dict:
    """Convenience function to run full error analysis.

    Args:
        errors: List of placement errors

    Returns:
        Dict with complete error analysis
    """
    analyzer = ErrorAnalyzer()

    return {
        "statistics": analyzer.calculate_error_statistics(errors),
        "systematic": analyzer.analyze_systematic_errors(errors),
        "scale": analyzer.analyze_scale_errors(errors),
        "categories": analyzer.categorize_errors(errors),
        "worst_offenders": [e.to_dict() for e in analyzer.identify_worst_offenders(errors, 10)]
    }
