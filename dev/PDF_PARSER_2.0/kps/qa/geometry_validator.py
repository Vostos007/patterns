"""Geometry validation for rendered assets.

The geometry validator compares expected asset bounding boxes against placement
metadata emitted by the InDesign automation layer. It enforces the ±2 pt / 1 %
dual tolerance rule documented in the master plan and provides actionable
reports when placements drift out of bounds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from kps.core import Asset, AssetLedger, BBox


def _label_to_bbox(label: dict) -> Optional[BBox]:
    """Convert placement metadata into a ``BBox`` instance."""

    if not isinstance(label, dict):
        return None

    if "bbox_placed" in label and isinstance(label["bbox_placed"], (list, tuple)):
        coords = label["bbox_placed"]
        if len(coords) == 4:
            return BBox(float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3]))

    if {"x", "y", "width", "height"}.issubset(label):
        x = float(label["x"])
        y = float(label["y"])
        width = float(label["width"])
        height = float(label["height"])
        return BBox(x, y, x + width, y + height)

    return None


@dataclass
class PlacementError:
    """Details of a placement error for a single asset."""

    asset_id: str
    expected_bbox: BBox
    actual_bbox: BBox
    absolute_error: float
    relative_error: float
    passed: bool
    error_type: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "asset_id": self.asset_id,
            "expected_bbox": str(self.expected_bbox),
            "actual_bbox": str(self.actual_bbox),
            "absolute_error": self.absolute_error,
            "relative_error": self.relative_error,
            "passed": self.passed,
            "error_type": self.error_type,
        }


@dataclass
class GeometryReport:
    """Summary of geometry validation results."""

    passed: bool
    tolerance_pt: float
    tolerance_pct: float
    total_assets: int
    evaluated_assets: int
    passed_assets: int
    failed_assets: int
    errors: List[PlacementError] = field(default_factory=list)
    systematic_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    pass_rate: float = 0.0
    max_error: float = 0.0
    mean_error: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "passed": self.passed,
            "tolerance_pt": self.tolerance_pt,
            "tolerance_pct": self.tolerance_pct,
            "total_assets": self.total_assets,
            "evaluated_assets": self.evaluated_assets,
            "passed_assets": self.passed_assets,
            "failed_assets": self.failed_assets,
            "pass_rate": self.pass_rate,
            "max_error": self.max_error,
            "mean_error": self.mean_error,
            "errors": [error.to_dict() for error in self.errors],
            "systematic_errors": list(self.systematic_errors),
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
        }


class ErrorAnalyzer:
    """Analyse per-asset placement deviations."""

    def calculate_error(
        self,
        *,
        asset_id: str,
        expected: BBox,
        actual: BBox,
        tolerance_pt: float,
        tolerance_pct: float,
    ) -> PlacementError:
        dx0 = abs(actual.x0 - expected.x0)
        dy0 = abs(actual.y0 - expected.y0)
        dx1 = abs(actual.x1 - expected.x1)
        dy1 = abs(actual.y1 - expected.y1)

        absolute_error = max(dx0, dy0, dx1, dy1)

        width_expected = expected.x1 - expected.x0
        height_expected = expected.y1 - expected.y0

        relative_components: List[float] = []
        if width_expected > 0:
            relative_components.append((dx0 / width_expected) * 100.0)
            relative_components.append((dx1 / width_expected) * 100.0)
        if height_expected > 0:
            relative_components.append((dy0 / height_expected) * 100.0)
            relative_components.append((dy1 / height_expected) * 100.0)

        relative_error = max(relative_components) if relative_components else 0.0

        if absolute_error == max(dx0, dx1):
            error_type = "x"
        elif absolute_error == max(dy0, dy1):
            error_type = "y"
        else:
            error_type = "combined"

        passed = (absolute_error <= tolerance_pt) or (relative_error <= tolerance_pct)

        return PlacementError(
            asset_id=asset_id,
            expected_bbox=expected,
            actual_bbox=actual,
            absolute_error=absolute_error,
            relative_error=relative_error,
            passed=passed,
            error_type=error_type,
        )

    def detect_systematic_errors(self, errors: Sequence[PlacementError]) -> List[str]:
        if not errors:
            return []

        x_offsets: List[float] = []
        y_offsets: List[float] = []
        for error in errors:
            if error.error_type in {"x", "combined"}:
                x_offsets.append(error.actual_bbox.x0 - error.expected_bbox.x0)
            if error.error_type in {"y", "combined"}:
                y_offsets.append(error.actual_bbox.y0 - error.expected_bbox.y0)

        findings: List[str] = []
        if len(x_offsets) >= 4:
            avg = mean(x_offsets)
            if abs(avg) > 2.0:
                findings.append(
                    f"Systematic X offset detected: {avg:.2f}pt (affects {len(x_offsets)} assets)"
                )

        if len(y_offsets) >= 4:
            avg = mean(y_offsets)
            if abs(avg) > 2.0:
                findings.append(
                    f"Systematic Y offset detected: {avg:.2f}pt (affects {len(y_offsets)} assets)"
                )

        return findings


class GeometryValidator:
    """Validate placement accuracy of rendered assets."""

    def __init__(
        self,
        *,
        tolerance_pt: float = 2.0,
        tolerance_pct: float = 1.0,
        min_pass_rate: float = 98.0,
        error_analyzer: Optional[ErrorAnalyzer] = None,
    ) -> None:
        if tolerance_pt <= 0:
            raise ValueError("tolerance_pt must be positive")
        if tolerance_pct < 0:
            raise ValueError("tolerance_pct must be non-negative")
        if not (0 <= min_pass_rate <= 100):
            raise ValueError("min_pass_rate must be between 0 and 100")

        self.tolerance_pt = tolerance_pt
        self.tolerance_pct = tolerance_pct
        self.min_pass_rate = min_pass_rate
        self.error_analyzer = error_analyzer or ErrorAnalyzer()

    def validate_geometry(
        self,
        *,
        source_ledger: AssetLedger,
        placed_labels: Sequence[dict],
    ) -> GeometryReport:
        lookup = {
            label.get("asset_id"): _label_to_bbox(label)
            for label in placed_labels
            if label.get("asset_id")
        }

        total_assets = len(source_ledger.assets)
        evaluated_assets = 0
        errors: List[PlacementError] = []

        for asset in source_ledger.assets:
            actual_bbox = lookup.get(asset.asset_id)
            if actual_bbox is None:
                continue

            evaluated_assets += 1
            placement_error = self.error_analyzer.calculate_error(
                asset_id=asset.asset_id,
                expected=asset.bbox,
                actual=actual_bbox,
                tolerance_pt=self.tolerance_pt,
                tolerance_pct=self.tolerance_pct,
            )

            if not placement_error.passed:
                errors.append(placement_error)

        failed_assets = len(errors)
        passed_assets = evaluated_assets - failed_assets
        pass_rate = (passed_assets / evaluated_assets * 100.0) if evaluated_assets else 100.0

        max_error = max((error.absolute_error for error in errors), default=0.0)
        mean_error = mean([e.absolute_error for e in errors]) if errors else 0.0

        systematic = self.error_analyzer.detect_systematic_errors(errors)

        warnings: List[str] = []
        recommendations: List[str] = []

        if pass_rate < self.min_pass_rate:
            warnings.append(
                f"Pass rate {pass_rate:.1f}% below threshold {self.min_pass_rate:.1f}%"
            )
            recommendations.append("Review InDesign placement accuracy for affected assets")

        if systematic:
            warnings.extend(systematic)
            recommendations.append("Investigate systematic placement offsets in placement script")

        if max_error > self.tolerance_pt * 3:
            warnings.append(f"Maximum error {max_error:.2f}pt exceeds 3x tolerance")
            recommendations.append("Inspect coordinate conversions for large deviations")

        passed = failed_assets == 0 and pass_rate >= self.min_pass_rate

        return GeometryReport(
            passed=passed,
            tolerance_pt=self.tolerance_pt,
            tolerance_pct=self.tolerance_pct,
            total_assets=total_assets,
            evaluated_assets=evaluated_assets,
            passed_assets=passed_assets,
            failed_assets=failed_assets,
            errors=errors,
            systematic_errors=systematic,
            warnings=warnings,
            recommendations=recommendations,
            pass_rate=pass_rate,
            max_error=max_error,
            mean_error=mean_error,
        )

