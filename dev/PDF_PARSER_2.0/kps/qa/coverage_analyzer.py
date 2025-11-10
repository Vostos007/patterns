"""Coverage analysis for asset completeness validation."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict

from kps.core import Asset, AssetLedger, AssetType
from .qa_utils import (
    calculate_asset_area,
    is_large_asset,
    is_prominent_asset,
    extract_section_from_anchor,
    safe_divide,
    group_by_page,
    group_by_type,
    group_by_section,
)
from .constants import (
    CRITICAL_SIZE_THRESHOLD,
    PROMINENT_AREA_THRESHOLD,
    ASSET_TYPE_WEIGHTS,
)


@dataclass
class CoverageMetrics:
    """
    Detailed coverage metrics for asset completeness.

    Tracks coverage at multiple levels:
    - Overall coverage
    - By asset type (image, vector, table)
    - By page number
    - By section (materials, instructions, etc.)
    """

    overall_coverage: float
    by_type: Dict[str, float] = field(default_factory=dict)
    by_page: Dict[int, float] = field(default_factory=dict)
    by_section: Dict[str, float] = field(default_factory=dict)

    # Detailed breakdowns
    total_source_assets: int = 0
    total_matched_assets: int = 0
    critical_missing: List[Asset] = field(default_factory=list)
    large_missing: List[Asset] = field(default_factory=list)
    prominent_missing: List[Asset] = field(default_factory=list)

    # Weighted coverage (considers asset importance)
    weighted_coverage: float = 0.0

    # Pages with issues
    pages_with_missing: List[int] = field(default_factory=list)
    pages_perfect: List[int] = field(default_factory=list)

    # Sections with issues
    sections_with_missing: List[str] = field(default_factory=list)
    sections_perfect: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "overall_coverage": self.overall_coverage,
            "weighted_coverage": self.weighted_coverage,
            "total_source_assets": self.total_source_assets,
            "total_matched_assets": self.total_matched_assets,
            "by_type": self.by_type,
            "by_page": self.by_page,
            "by_section": self.by_section,
            "critical_missing_count": len(self.critical_missing),
            "large_missing_count": len(self.large_missing),
            "prominent_missing_count": len(self.prominent_missing),
            "pages_with_missing": self.pages_with_missing,
            "pages_perfect": self.pages_perfect,
            "sections_with_missing": self.sections_with_missing,
            "sections_perfect": self.sections_perfect,
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Overall Coverage: {self.overall_coverage:.1f}%",
            f"Weighted Coverage: {self.weighted_coverage:.1f}%",
            f"Total Assets: {self.total_source_assets}",
            f"Matched Assets: {self.total_matched_assets}",
            f"Missing Assets: {self.total_source_assets - self.total_matched_assets}",
        ]

        if self.critical_missing:
            lines.append(f"Critical Missing: {len(self.critical_missing)}")

        if self.pages_with_missing:
            lines.append(f"Pages with Issues: {len(self.pages_with_missing)}")

        if self.sections_with_missing:
            lines.append(f"Sections with Issues: {len(self.sections_with_missing)}")

        return "\n".join(lines)


class CoverageAnalyzer:
    """
    Analyze asset coverage with multiple dimensions.

    Provides detailed coverage metrics including:
    - Overall and weighted coverage
    - Coverage by type, page, and section
    - Identification of critical missing assets
    - Problem area identification
    """

    def __init__(self, use_weighted: bool = True):
        """
        Initialize coverage analyzer.

        Args:
            use_weighted: Use weighted coverage (considers asset importance)
        """
        self.use_weighted = use_weighted

    def analyze(
        self, source_ledger: AssetLedger, matched_assets: List[Asset]
    ) -> CoverageMetrics:
        """
        Comprehensive coverage analysis.

        Args:
            source_ledger: Source asset ledger
            matched_assets: List of successfully matched assets

        Returns:
            CoverageMetrics with detailed analysis
        """
        total_source = len(source_ledger.assets)
        total_matched = len(matched_assets)

        # Calculate overall coverage
        overall = safe_divide(total_matched, total_source, default=0.0) * 100

        # Calculate weighted coverage (if enabled)
        weighted = (
            self._calculate_weighted_coverage(source_ledger.assets, matched_assets)
            if self.use_weighted
            else overall
        )

        # Coverage by dimensions
        by_type = self._coverage_by_type(source_ledger, matched_assets)
        by_page = self._coverage_by_page(source_ledger, matched_assets)
        by_section = self._coverage_by_section(source_ledger, matched_assets)

        # Identify missing assets
        all_missing = [a for a in source_ledger.assets if a not in matched_assets]

        critical_missing = [a for a in all_missing if self._is_critical(a)]
        large_missing = [
            a for a in all_missing if is_large_asset(a, CRITICAL_SIZE_THRESHOLD)
        ]
        prominent_missing = [
            a for a in all_missing if is_prominent_asset(a, PROMINENT_AREA_THRESHOLD)
        ]

        # Identify problem areas
        pages_with_missing = [
            page for page, coverage in by_page.items() if coverage < 100.0
        ]
        pages_perfect = [page for page, coverage in by_page.items() if coverage >= 100.0]

        sections_with_missing = [
            section for section, coverage in by_section.items() if coverage < 100.0
        ]
        sections_perfect = [
            section for section, coverage in by_section.items() if coverage >= 100.0
        ]

        return CoverageMetrics(
            overall_coverage=overall,
            weighted_coverage=weighted,
            total_source_assets=total_source,
            total_matched_assets=total_matched,
            by_type=by_type,
            by_page=by_page,
            by_section=by_section,
            critical_missing=critical_missing,
            large_missing=large_missing,
            prominent_missing=prominent_missing,
            pages_with_missing=pages_with_missing,
            pages_perfect=pages_perfect,
            sections_with_missing=sections_with_missing,
            sections_perfect=sections_perfect,
        )

    def _coverage_by_type(
        self, ledger: AssetLedger, matched: List[Asset]
    ) -> Dict[str, float]:
        """
        Calculate coverage percentage by asset type.

        Args:
            ledger: Source asset ledger
            matched: Matched assets

        Returns:
            Dict mapping asset_type -> coverage percentage
        """
        coverage = {}

        for asset_type in AssetType:
            source_of_type = ledger.by_type(asset_type)
            matched_of_type = [a for a in matched if a.asset_type == asset_type]

            if source_of_type:
                coverage[asset_type.value] = (
                    len(matched_of_type) / len(source_of_type) * 100
                )
            else:
                coverage[asset_type.value] = 100.0

        return coverage

    def _coverage_by_page(
        self, ledger: AssetLedger, matched: List[Asset]
    ) -> Dict[int, float]:
        """
        Calculate coverage percentage by page.

        Args:
            ledger: Source asset ledger
            matched: Matched assets

        Returns:
            Dict mapping page_number -> coverage percentage
        """
        coverage = {}

        for page_num in range(ledger.total_pages):
            source_on_page = ledger.by_page(page_num)
            matched_on_page = [a for a in matched if a.page_number == page_num]

            if source_on_page:
                coverage[page_num] = len(matched_on_page) / len(source_on_page) * 100
            else:
                coverage[page_num] = 100.0

        return coverage

    def _coverage_by_section(
        self, ledger: AssetLedger, matched: List[Asset]
    ) -> Dict[str, float]:
        """
        Calculate coverage percentage by section.

        Sections are extracted from anchor_to block IDs
        (e.g., "paragraph.materials.001" -> "materials")

        Args:
            ledger: Source asset ledger
            matched: Matched assets

        Returns:
            Dict mapping section_name -> coverage percentage
        """
        # Group source assets by section
        source_by_section = group_by_section(ledger.assets)

        # Group matched assets by section
        matched_by_section = group_by_section(matched)

        # Calculate coverage for each section
        coverage = {}
        for section, source_assets in source_by_section.items():
            matched_in_section = matched_by_section.get(section, [])
            coverage[section] = (
                safe_divide(len(matched_in_section), len(source_assets), default=0.0)
                * 100
            )

        return coverage

    def _calculate_weighted_coverage(
        self, source_assets: List[Asset], matched_assets: List[Asset]
    ) -> float:
        """
        Calculate weighted coverage (considers asset importance).

        Weights are based on:
        - Asset type (tables > vectors > images)
        - Asset size (larger assets are more important)
        - Asset prominence (area)

        Args:
            source_assets: All source assets
            matched_assets: Matched assets

        Returns:
            Weighted coverage percentage
        """
        total_weight = 0.0
        matched_weight = 0.0

        for asset in source_assets:
            weight = self._calculate_asset_weight(asset)
            total_weight += weight

            if asset in matched_assets:
                matched_weight += weight

        return safe_divide(matched_weight, total_weight, default=0.0) * 100

    def _calculate_asset_weight(self, asset: Asset) -> float:
        """
        Calculate weight for an asset based on importance.

        Args:
            asset: Asset to weight

        Returns:
            Weight value (higher = more important)
        """
        # Base weight from asset type
        base_weight = ASSET_TYPE_WEIGHTS.get(asset.asset_type.value, 1.0)

        # Adjust for size
        size_multiplier = 1.0
        if is_large_asset(asset, CRITICAL_SIZE_THRESHOLD):
            size_multiplier = 1.5

        if is_prominent_asset(asset, PROMINENT_AREA_THRESHOLD):
            size_multiplier = 2.0

        return base_weight * size_multiplier

    def _is_critical(self, asset: Asset) -> bool:
        """
        Determine if asset is critical.

        Critical assets include:
        - Large images (> threshold)
        - All tables (live and snapshots)
        - Vector graphics
        - Prominent assets (large area)

        Args:
            asset: Asset to check

        Returns:
            True if critical
        """
        # Large images
        if is_large_asset(asset, CRITICAL_SIZE_THRESHOLD):
            return True

        # Prominent assets
        if is_prominent_asset(asset, PROMINENT_AREA_THRESHOLD):
            return True

        # Tables are always critical
        if asset.asset_type in [AssetType.TABLE_LIVE, AssetType.TABLE_SNAP]:
            return True

        # Vectors are critical
        if asset.asset_type == AssetType.VECTOR_PDF:
            return True

        return False

    def compare_ledgers(
        self, source_ledger: AssetLedger, output_ledger: AssetLedger
    ) -> dict:
        """
        Compare two asset ledgers and identify differences.

        Args:
            source_ledger: Source asset ledger
            output_ledger: Output asset ledger

        Returns:
            Dictionary of comparison results
        """
        # Compare totals
        source_total = len(source_ledger.assets)
        output_total = len(output_ledger.assets)

        # Compare by type
        type_comparison = {}
        for asset_type in AssetType:
            source_count = len(source_ledger.by_type(asset_type))
            output_count = len(output_ledger.by_type(asset_type))
            type_comparison[asset_type.value] = {
                "source": source_count,
                "output": output_count,
                "difference": output_count - source_count,
            }

        # Compare by page
        page_comparison = {}
        max_pages = max(source_ledger.total_pages, output_ledger.total_pages)
        for page_num in range(max_pages):
            source_count = len(source_ledger.by_page(page_num))
            output_count = len(output_ledger.by_page(page_num))
            page_comparison[page_num] = {
                "source": source_count,
                "output": output_count,
                "difference": output_count - source_count,
            }

        return {
            "total": {
                "source": source_total,
                "output": output_total,
                "difference": output_total - source_total,
            },
            "by_type": type_comparison,
            "by_page": page_comparison,
        }
