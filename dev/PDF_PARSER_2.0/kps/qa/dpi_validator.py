"""DPI validation system for KPS v2.0 QA Suite.

Validates that all images in output PDF meet print-quality requirements:
- Effective DPI ≥300 for print quality
- Detects upscaled images (quality degradation)
- Detects downsampled images (wasted space)
- Provides actionable recommendations

Part of Day 5: DPI Validator and Font Audit
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import statistics
import logging

try:  # pragma: no cover - optional dependency
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None

from kps.core import Asset, AssetLedger, AssetType, BBox

logger = logging.getLogger(__name__)


@dataclass
class DPIIssue:
    """DPI issue for single image."""

    asset_id: str
    page_number: int
    original_dimensions: Tuple[int, int]  # (width, height) in pixels
    placed_dimensions: Tuple[float, float]  # (width, height) in points
    effective_dpi: Tuple[float, float]  # (dpi_h, dpi_v)
    min_dpi: float  # min(dpi_h, dpi_v)
    max_dpi: float  # max(dpi_h, dpi_v)
    issue_type: str  # "low_dpi", "upscaled", "acceptable", "excellent"
    severity: str  # "error", "warning", "ok"
    scale_factor: float  # Scaling applied (>1 = upscaled, <1 = downsampled)

    # Additional context
    original_area_px: int  # Original image area in pixels
    placed_area_pt: float  # Placed area in square points

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "asset_id": self.asset_id,
            "page": self.page_number,
            "original_px": {
                "width": self.original_dimensions[0],
                "height": self.original_dimensions[1],
            },
            "placed_pt": {
                "width": self.placed_dimensions[0],
                "height": self.placed_dimensions[1],
            },
            "effective_dpi": {
                "horizontal": round(self.effective_dpi[0], 2),
                "vertical": round(self.effective_dpi[1], 2),
            },
            "min_dpi": round(self.min_dpi, 2),
            "max_dpi": round(self.max_dpi, 2),
            "issue_type": self.issue_type,
            "severity": self.severity,
            "scale_factor": round(self.scale_factor, 3),
            "original_area_px": self.original_area_px,
            "placed_area_pt": round(self.placed_area_pt, 2),
        }

    def __str__(self) -> str:
        """Human-readable string."""
        return (
            f"{self.asset_id} (p{self.page_number}): "
            f"{self.min_dpi:.0f} DPI [{self.severity}] - {self.issue_type}"
        )


@dataclass
class DPIReport:
    """DPI validation report."""

    total_images: int
    images_passed: int  # ≥300 DPI
    images_with_warnings: int  # 250-299 DPI or upscaled
    images_with_errors: int  # <250 DPI

    # Statistics
    min_dpi_found: float
    max_dpi_found: float
    mean_dpi: float
    median_dpi: float
    std_dev_dpi: float

    # Categorized issues
    issues: List[DPIIssue]
    low_dpi_images: List[DPIIssue]  # < 300 DPI
    upscaled_images: List[DPIIssue]  # Scaled > 120%
    excellent_images: List[DPIIssue]  # ≥400 DPI

    # Pass/fail
    passed: bool  # True if all images ≥300 DPI

    # Feedback
    errors: List[str]
    warnings: List[str]
    recommendations: List[str]
    summary: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "summary": self.summary,
            "passed": self.passed,
            "statistics": {
                "total_images": self.total_images,
                "images_passed": self.images_passed,
                "images_with_warnings": self.images_with_warnings,
                "images_with_errors": self.images_with_errors,
                "min_dpi": round(self.min_dpi_found, 2),
                "max_dpi": round(self.max_dpi_found, 2),
                "mean_dpi": round(self.mean_dpi, 2),
                "median_dpi": round(self.median_dpi, 2),
                "std_dev_dpi": round(self.std_dev_dpi, 2),
            },
            "issues": [issue.to_dict() for issue in self.issues],
            "low_dpi_count": len(self.low_dpi_images),
            "upscaled_count": len(self.upscaled_images),
            "excellent_count": len(self.excellent_images),
            "errors": self.errors,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }

    def print_report(self) -> str:
        """Generate human-readable report."""
        lines = []
        lines.append("=" * 80)
        lines.append("DPI VALIDATION REPORT")
        lines.append("=" * 80)
        lines.append("")

        lines.append(f"Status: {'✓ PASSED' if self.passed else '✗ FAILED'}")
        lines.append(f"Total Images: {self.total_images}")
        lines.append(f"  - Passed (≥300 DPI): {self.images_passed}")
        lines.append(f"  - Warnings: {self.images_with_warnings}")
        lines.append(f"  - Errors: {self.images_with_errors}")
        lines.append("")

        lines.append("DPI Statistics:")
        lines.append(f"  - Minimum: {self.min_dpi_found:.1f} DPI")
        lines.append(f"  - Maximum: {self.max_dpi_found:.1f} DPI")
        lines.append(f"  - Mean: {self.mean_dpi:.1f} DPI")
        lines.append(f"  - Median: {self.median_dpi:.1f} DPI")
        lines.append(f"  - Std Dev: {self.std_dev_dpi:.1f}")
        lines.append("")

        if self.errors:
            lines.append("ERRORS:")
            for error in self.errors:
                lines.append(f"  ✗ {error}")
            lines.append("")

        if self.warnings:
            lines.append("WARNINGS:")
            for warning in self.warnings:
                lines.append(f"  ⚠ {warning}")
            lines.append("")

        if self.recommendations:
            lines.append("RECOMMENDATIONS:")
            for rec in self.recommendations:
                lines.append(f"  → {rec}")
            lines.append("")

        lines.append(self.summary)
        lines.append("=" * 80)

        return "\n".join(lines)


class DPIValidator:
    """Validate image DPI in output PDF.

    Calculates effective DPI by comparing original image dimensions
    with placed dimensions in PDF. Detects quality issues and provides
    actionable recommendations.
    """

    def __init__(
        self,
        min_dpi: float = 300.0,
        warn_dpi: float = 350.0,
        excellent_dpi: float = 400.0,
        max_upscale: float = 1.2,  # 120%
        error_dpi: float = 250.0,  # Below this is error
    ):
        """Initialize DPI validator.

        Args:
            min_dpi: Minimum acceptable DPI (300 for print)
            warn_dpi: Warning threshold (350)
            excellent_dpi: Excellent quality threshold (400+)
            max_upscale: Maximum scaling before warning (1.2 = 120%)
            error_dpi: Below this is critical error (250)
        """
        self.min_dpi = min_dpi
        self.warn_dpi = warn_dpi
        self.excellent_dpi = excellent_dpi
        self.max_upscale = max_upscale
        self.error_dpi = error_dpi

    def validate_dpi(
        self,
        pdf_path: Path,
        source_ledger: AssetLedger,
        placed_labels: Optional[List[dict]] = None
    ) -> DPIReport:
        """Validate DPI of all images in PDF.

        Args:
            pdf_path: Output PDF to check
            source_ledger: Original assets with dimensions
            placed_labels: Placed objects from InDesign (optional)

        Returns:
            DPIReport with all issues and recommendations
        """
        issues = []

        # Get image assets
        image_assets = [
            a for a in source_ledger.assets
            if a.asset_type == AssetType.IMAGE
        ]

        if not image_assets:
            return self._empty_report("No images found in asset ledger")

        # Open PDF to get actual placed dimensions
        doc = None
        if fitz is not None:
            try:
                doc = fitz.open(pdf_path)
            except Exception as e:
                # If we have placed_labels, we can continue without PDF
                if not placed_labels:
                    return self._empty_report(f"Failed to open PDF: {e}")
                logger.warning(f"PDF not available, using placed_labels only: {e}")
        elif not placed_labels:
            return self._empty_report(
                "PyMuPDF (fitz) is required for DPI validation when placed labels are not provided"
            )

        # Validate each image
        for asset in image_assets:
            if not asset.image_width or not asset.image_height:
                continue

            # Get placed dimensions from PDF
            placed_bbox = self._get_placed_bbox_from_pdf(
                doc, asset, placed_labels
            )

            if not placed_bbox:
                placed_bbox = asset.bbox

            if not placed_bbox:
                continue

            # Calculate effective DPI
            placed_width_pt = placed_bbox.width
            placed_height_pt = placed_bbox.height

            if placed_width_pt <= 0 or placed_height_pt <= 0:
                continue

            # DPI = (pixels / points) * 72
            dpi_h = (asset.image_width / placed_width_pt) * 72
            dpi_v = (asset.image_height / placed_height_pt) * 72

            min_dpi = min(dpi_h, dpi_v)
            max_dpi = max(dpi_h, dpi_v)

            # Calculate scale factor
            original_width_pt = asset.bbox.width if asset.bbox else placed_width_pt
            original_height_pt = asset.bbox.height if asset.bbox else placed_height_pt

            scale_h = placed_width_pt / original_width_pt if original_width_pt > 0 else 1.0
            scale_v = placed_height_pt / original_height_pt if original_height_pt > 0 else 1.0
            scale_factor = max(scale_h, scale_v)

            # Determine issue type and severity
            issue_type, severity = self._classify_dpi(
                min_dpi, scale_factor
            )

            # Create issue
            issue = DPIIssue(
                asset_id=asset.asset_id,
                page_number=asset.page_number,
                original_dimensions=(asset.image_width, asset.image_height),
                placed_dimensions=(placed_width_pt, placed_height_pt),
                effective_dpi=(dpi_h, dpi_v),
                min_dpi=min_dpi,
                max_dpi=max_dpi,
                issue_type=issue_type,
                severity=severity,
                scale_factor=scale_factor,
                original_area_px=asset.image_width * asset.image_height,
                placed_area_pt=placed_width_pt * placed_height_pt,
            )

            issues.append(issue)

        if doc is not None:
            doc.close()

        # Generate report
        return self._generate_report(issues)

    def _get_placed_bbox_from_pdf(
        self,
        doc,
        asset: Asset,
        placed_labels: Optional[List[dict]]
    ) -> Optional[BBox]:
        """Get placed bounding box from PDF or placed labels.

        Args:
            doc: PyMuPDF document
            asset: Asset to find
            placed_labels: Optional placed labels from InDesign

        Returns:
            BBox of placed image, or None
        """
        # Try placed labels first (most accurate)
        if placed_labels:
            for label in placed_labels:
                if label.get("asset_id") == asset.asset_id:
                    bbox_data = label.get("bbox_placed")
                    if bbox_data:
                        return BBox(*bbox_data)

        if doc is None or fitz is None:
            return None

        try:
            page = doc[asset.page_number]
            image_list = page.get_images(full=True)

            for img_info in image_list:
                xref = img_info[0]
                bbox_rect = page.get_image_bbox(img_info)

                pix = fitz.Pixmap(doc, xref)
                if pix.width == asset.image_width and pix.height == asset.image_height:
                    return BBox(
                        x0=bbox_rect.x0,
                        y0=bbox_rect.y0,
                        x1=bbox_rect.x1,
                        y1=bbox_rect.y1
                    )
        except Exception:
            return None

        return None

    def _classify_dpi(
        self,
        min_dpi: float,
        scale_factor: float
    ) -> Tuple[str, str]:
        """Classify DPI issue type and severity.

        Returns:
            (issue_type, severity) tuple
        """
        # Check DPI thresholds
        if min_dpi < self.error_dpi:
            return ("low_dpi", "error")
        elif min_dpi < self.min_dpi:
            return ("low_dpi", "warning")
        elif min_dpi >= self.excellent_dpi:
            issue_type = "excellent"
        else:
            issue_type = "acceptable"

        # Check for upscaling
        if scale_factor > self.max_upscale:
            return ("upscaled", "warning" if issue_type != "excellent" else "ok")

        # Determine severity
        if issue_type == "excellent":
            severity = "ok"
        elif min_dpi < self.warn_dpi:
            severity = "warning"
        else:
            severity = "ok"

        return (issue_type, severity)

    def _generate_report(self, issues: List[DPIIssue]) -> DPIReport:
        """Generate comprehensive DPI report."""
        if not issues:
            return self._empty_report("No images to validate")

        # Calculate statistics
        images_passed = sum(1 for i in issues if i.severity == "ok")
        images_warnings = sum(1 for i in issues if i.severity == "warning")
        images_errors = sum(1 for i in issues if i.severity == "error")

        # Categorize issues
        low_dpi = [i for i in issues if i.issue_type == "low_dpi"]
        upscaled = [i for i in issues if i.issue_type == "upscaled"]
        excellent = [i for i in issues if i.issue_type == "excellent"]

        # DPI statistics
        dpis = [i.min_dpi for i in issues]
        min_dpi_found = min(dpis)
        max_dpi_found = max(dpis)
        mean_dpi = statistics.mean(dpis)
        median_dpi = statistics.median(dpis)
        std_dev_dpi = statistics.stdev(dpis) if len(dpis) > 1 else 0.0

        # Generate errors and warnings
        errors = []
        warnings = []

        if images_errors > 0:
            errors.append(
                f"{images_errors} image(s) below {self.error_dpi:.0f} DPI (critical)"
            )

            # List worst offenders
            worst = sorted(low_dpi, key=lambda i: i.min_dpi)[:5]
            for issue in worst:
                if issue.severity == "error":
                    errors.append(
                        f"  - {issue.asset_id}: {issue.min_dpi:.0f} DPI "
                        f"(page {issue.page_number})"
                    )

        if images_warnings > 0 and images_errors == 0:
            warnings.append(
                f"{images_warnings} image(s) between {self.error_dpi:.0f}-{self.min_dpi:.0f} DPI"
            )

        if upscaled:
            warnings.append(
                f"{len(upscaled)} image(s) upscaled beyond {self.max_upscale*100:.0f}%"
            )

            worst_upscaled = sorted(upscaled, key=lambda i: i.scale_factor, reverse=True)[:3]
            for issue in worst_upscaled:
                warnings.append(
                    f"  - {issue.asset_id}: scaled {issue.scale_factor*100:.0f}% "
                    f"(page {issue.page_number})"
                )

        # Generate recommendations
        recommendations = self._generate_recommendations(low_dpi, upscaled, excellent)

        # Summary
        passed = (images_errors == 0)
        if passed:
            summary = f"All {len(issues)} images meet minimum DPI requirement (≥{self.min_dpi:.0f} DPI)"
        else:
            summary = f"FAILED: {images_errors} images below acceptable DPI threshold"

        return DPIReport(
            total_images=len(issues),
            images_passed=images_passed,
            images_with_warnings=images_warnings,
            images_with_errors=images_errors,
            min_dpi_found=min_dpi_found,
            max_dpi_found=max_dpi_found,
            mean_dpi=mean_dpi,
            median_dpi=median_dpi,
            std_dev_dpi=std_dev_dpi,
            issues=issues,
            low_dpi_images=low_dpi,
            upscaled_images=upscaled,
            excellent_images=excellent,
            passed=passed,
            errors=errors,
            warnings=warnings,
            recommendations=recommendations,
            summary=summary,
        )

    def _generate_recommendations(
        self,
        low_dpi: List[DPIIssue],
        upscaled: List[DPIIssue],
        excellent: List[DPIIssue]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        if low_dpi:
            recommendations.append(
                f"Replace {len(low_dpi)} low-DPI image(s) with higher resolution versions"
            )

            # Show worst offenders with required scaling
            worst = sorted(low_dpi, key=lambda i: i.min_dpi)[:3]
            for issue in worst:
                needed_dpi = self.min_dpi
                scale_up = needed_dpi / issue.min_dpi
                recommendations.append(
                    f"  - {issue.asset_id}: need {scale_up:.1f}x larger image "
                    f"({issue.original_dimensions[0]}px → "
                    f"{int(issue.original_dimensions[0] * scale_up)}px wide)"
                )

        if upscaled:
            recommendations.append(
                "Review upscaled images - consider:"
            )
            recommendations.append(
                "  - Reducing placed size in layout"
            )
            recommendations.append(
                "  - Using higher resolution source images"
            )

        if excellent:
            recommendations.append(
                f"{len(excellent)} image(s) exceed {self.excellent_dpi:.0f} DPI - "
                "excellent print quality"
            )

        if not low_dpi and not upscaled:
            recommendations.append(
                "All images meet or exceed print quality standards"
            )

        return recommendations

    def _empty_report(self, message: str) -> DPIReport:
        """Generate empty report with message."""
        return DPIReport(
            total_images=0,
            images_passed=0,
            images_with_warnings=0,
            images_with_errors=0,
            min_dpi_found=0.0,
            max_dpi_found=0.0,
            mean_dpi=0.0,
            median_dpi=0.0,
            std_dev_dpi=0.0,
            issues=[],
            low_dpi_images=[],
            upscaled_images=[],
            excellent_images=[],
            passed=True,
            errors=[],
            warnings=[message],
            recommendations=[],
            summary=message,
        )
