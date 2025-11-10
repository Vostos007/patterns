"""Asset completeness validation for the KPS v2.0 QA suite.

This module implements the first fail-closed QA guardrail: verifying that every
asset extracted from the source document is present in the rendered output. The
checker produces rich coverage metrics, actionable warnings, and
recommendations so pipeline operators can quickly diagnose missing or
misplaced assets.

Typical workflow::

    checker = CompletenessChecker()
    report = checker.check_completeness(ledger, output_pdf, placed_labels)
    if not report.passed:
        print(report.summary())

The checker intentionally accepts lightweight metadata (a list of dictionaries
with ``asset_id`` fields) so it can run on top of either the InDesign label
export or a bespoke placement manifest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from kps.core import Asset, AssetLedger

from .constants import (
    MAX_MISSING_DETAILS,
    RECOMMEND_CHECK_INDESIGN,
    RECOMMEND_CHECK_FORMAT,
    RECOMMEND_MANUAL_REVIEW,
    RECOMMEND_CHECK_ANCHORING,
    WARNING_LOW_COVERAGE,
    WARNING_MISSING_CRITICAL,
    WARNING_ORPHAN_ASSETS,
)
from .coverage_analyzer import CoverageAnalyzer, CoverageMetrics


def _extract_asset_ids(label_records: Sequence[dict]) -> List[str]:
    """Safely extract asset IDs from placement metadata.

    The placement metadata is expected to contain an ``asset_id`` key, but some
    pipelines may emit auxiliary rows (for example, text frames) without it. We
    drop those entries rather than failing the entire check.
    """

    ids: List[str] = []
    for record in label_records:
        asset_id = record.get("asset_id") if isinstance(record, dict) else None
        if asset_id:
            ids.append(str(asset_id))
    return ids


@dataclass(frozen=True)
class CompletenessReport:
    """Result of the asset completeness check."""

    passed: bool
    coverage_percentage: float
    total_assets: int
    placed_assets: int
    missing_assets: List[str] = field(default_factory=list)
    extra_assets: List[str] = field(default_factory=list)
    by_type: Dict[str, float] = field(default_factory=dict)
    by_page: Dict[int, float] = field(default_factory=dict)
    weighted_coverage: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Serialise the report for JSON logging."""

        return {
            "passed": self.passed,
            "coverage_percentage": round(self.coverage_percentage, 4),
            "weighted_coverage": None
            if self.weighted_coverage is None
            else round(self.weighted_coverage, 4),
            "total_assets": self.total_assets,
            "placed_assets": self.placed_assets,
            "missing_assets": list(self.missing_assets),
            "extra_assets": list(self.extra_assets),
            "by_type": dict(self.by_type),
            "by_page": dict(self.by_page),
            "warnings": list(self.warnings),
            "recommendations": list(self.recommendations),
        }

    def summary(self) -> str:
        """Return a concise human-readable summary."""

        header = "✓ Asset coverage 100%" if self.passed else "✗ Asset coverage incomplete"
        lines = [header, f"Coverage: {self.coverage_percentage:.1f}%"]

        if self.weighted_coverage is not None:
            lines.append(f"Weighted coverage: {self.weighted_coverage:.1f}%")

        if self.missing_assets:
            preview = ", ".join(self.missing_assets[: MAX_MISSING_DETAILS])
            lines.append(f"Missing assets ({len(self.missing_assets)}): {preview}")

        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"  - {warning}" for warning in self.warnings)

        if self.recommendations:
            lines.append("Recommendations:")
            lines.extend(f"  - {rec}" for rec in self.recommendations)

        return "\n".join(lines)


class CompletenessChecker:
    """Validate that every asset reaches the output document."""

    def __init__(
        self,
        require_perfect: bool = True,
        min_coverage: float = 100.0,
        coverage_analyzer: Optional[CoverageAnalyzer] = None,
    ) -> None:
        if min_coverage < 0 or min_coverage > 100:
            raise ValueError("min_coverage must be between 0 and 100")

        self.require_perfect = require_perfect
        self.min_coverage = min_coverage
        self._coverage_analyzer = coverage_analyzer or CoverageAnalyzer()

    def check_completeness(
        self,
        source_ledger: AssetLedger,
        output_pdf: Optional[Path],
        placed_labels: Sequence[dict],
    ) -> CompletenessReport:
        """Evaluate asset coverage for a rendered document.

        Args:
            source_ledger: Ledger describing every asset extracted from the
                source PDF.
            output_pdf: Path to the translated PDF (optional for this check).
            placed_labels: Placement metadata exported by InDesign automation.
        """

        placed_ids = set(_extract_asset_ids(placed_labels))
        source_assets = list(source_ledger.assets)
        source_ids = {asset.asset_id for asset in source_assets}

        matched_assets = [asset for asset in source_assets if asset.asset_id in placed_ids]
        missing_ids = sorted(source_ids - placed_ids)
        extra_ids = sorted(placed_ids - source_ids)

        metrics = self._analyze_coverage(source_ledger, matched_assets)
        coverage = metrics.overall_coverage if metrics else 0.0
        weighted_coverage = metrics.weighted_coverage if metrics else None

        total_assets = len(source_assets)
        placed_assets = len(matched_assets)

        passed = self._determine_pass_state(total_assets, coverage)

        warnings, recommendations = self._build_feedback(
            metrics=metrics,
            missing_ids=missing_ids,
            extra_ids=extra_ids,
            coverage=coverage,
        )

        return CompletenessReport(
            passed=passed,
            coverage_percentage=coverage,
            total_assets=total_assets,
            placed_assets=placed_assets,
            missing_assets=missing_ids,
            extra_assets=extra_ids,
            by_type=metrics.by_type if metrics else {},
            by_page=metrics.by_page if metrics else {},
            weighted_coverage=weighted_coverage,
            warnings=warnings,
            recommendations=recommendations,
        )

    def generate_missing_report(
        self,
        source_ledger: AssetLedger,
        missing_ids: Iterable[str],
    ) -> str:
        """Produce a detailed report listing the missing assets."""

        missing_lookup = {asset.asset_id: asset for asset in source_ledger.assets}
        lines: List[str] = ["Missing Assets Report", "=" * 50, ""]

        for asset_id in sorted(set(missing_ids)):
            asset = missing_lookup.get(asset_id)
            if not asset:
                continue

            lines.append(f"Asset ID: {asset.asset_id}")
            lines.append(f"  Type: {asset.asset_type.value}")
            lines.append(f"  Page: {asset.page_number}")
            lines.append(f"  Anchor: {asset.anchor_to or 'unanchored'}")
            lines.append(f"  BBox: {asset.bbox}")
            lines.append("")

        if len(lines) == 3:
            lines.append("No missing assets identified.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _analyze_coverage(
        self,
        source_ledger: AssetLedger,
        matched_assets: List[Asset],
    ) -> Optional[CoverageMetrics]:
        if not source_ledger.assets:
            # No assets -> nothing to analyse
            return None
        return self._coverage_analyzer.analyze(source_ledger, matched_assets)

    def _determine_pass_state(self, total_assets: int, coverage: float) -> bool:
        if total_assets == 0:
            return True

        if self.require_perfect:
            return round(coverage, 4) >= 100.0

        return coverage >= self.min_coverage

    def _build_feedback(
        self,
        *,
        metrics: Optional[CoverageMetrics],
        missing_ids: Sequence[str],
        extra_ids: Sequence[str],
        coverage: float,
    ) -> tuple[List[str], List[str]]:
        warnings: List[str] = []
        recommendations: List[str] = []

        if missing_ids:
            warnings.append(f"{len(missing_ids)} assets missing from output PDF")
            recommendations.extend(
                [
                    RECOMMEND_CHECK_ANCHORING,
                    RECOMMEND_CHECK_INDESIGN,
                    RECOMMEND_MANUAL_REVIEW,
                ]
            )

        if metrics:
            if coverage < self.min_coverage and not self.require_perfect:
                warnings.append(
                    f"{WARNING_LOW_COVERAGE}: {coverage:.1f}% (threshold {self.min_coverage:.1f}%)"
                )

            # Highlight systematic gaps by type
            low_types = [name for name, pct in metrics.by_type.items() if pct < 100.0]
            if low_types:
                recommendations.append(
                    f"Investigate asset types with partial coverage: {', '.join(sorted(low_types))}"
                )

            # Highlight pages with missing assets
            low_pages = [page for page, pct in metrics.by_page.items() if pct < 100.0]
            if low_pages:
                warnings.append(
                    f"Pages with incomplete coverage: {', '.join(map(str, sorted(low_pages)))}"
                )
                recommendations.append("Verify InDesign placement on affected pages")

            if metrics.critical_missing:
                warnings.append(WARNING_MISSING_CRITICAL)
                recommendations.append(RECOMMEND_MANUAL_REVIEW)

        if extra_ids:
            warnings.append(f"{WARNING_ORPHAN_ASSETS}: {len(extra_ids)} extra assets detected")
            recommendations.append(RECOMMEND_CHECK_FORMAT)

        # De-duplicate while preserving order
        seen = set()
        warnings = [w for w in warnings if not (w in seen or seen.add(w))]
        seen.clear()
        recommendations = [r for r in recommendations if not (r in seen or seen.add(r))]

        return warnings, recommendations
