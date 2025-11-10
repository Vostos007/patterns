"""
Unit tests for QA completeness checker.

Tests the asset completeness validation system that ensures 100% of assets
from the source ledger are placed in the output PDF.
"""

import pytest
from pathlib import Path
from typing import Any, Dict, List

from kps.core import Asset, AssetLedger, AssetType, BBox
from kps.qa.completeness_checker import CompletenessChecker, CompletenessReport


def _make_asset(
    *,
    idx: int,
    asset_type: AssetType = AssetType.IMAGE,
    page: int = 0,
    occurrence: int = 1,
    width: int = 600,
    height: int = 400,
    anchor_suffix: str = "materials",
) -> Asset:
    asset_id = f"{asset_type.value[:3]}-{idx:04d}-p{page}-occ{occurrence}"
    sha256 = f"{idx:064x}"[:64]
    bbox = BBox(50 + idx, 100 + idx, 150 + idx, 200 + idx)
    file_path = Path(f"/tmp/{asset_id}.png")

    return Asset(
        asset_id=asset_id,
        asset_type=asset_type,
        sha256=sha256,
        page_number=page,
        bbox=bbox,
        ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        file_path=file_path,
        occurrence=occurrence,
        anchor_to=f"p.{anchor_suffix}.{idx:03d}",
        image_width=width if asset_type == AssetType.IMAGE else width,
        image_height=height if asset_type == AssetType.IMAGE else height,
    )


def _make_ledger(assets: List[Asset], total_pages: int = 1) -> AssetLedger:
    return AssetLedger(assets=assets, source_pdf=Path("source.pdf"), total_pages=total_pages)


@pytest.fixture
def sample_output_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "output.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\n% Dummy output for QA tests\n")
    return pdf_path


@pytest.fixture
def sample_ledger() -> AssetLedger:
    assets = [_make_asset(idx=i) for i in range(10)]
    return _make_ledger(assets, total_pages=3)


@pytest.fixture
def empty_ledger() -> AssetLedger:
    return _make_ledger([], total_pages=0)


@pytest.fixture
def sample_ledger_mixed_types() -> AssetLedger:
    assets: List[Asset] = []
    for i in range(4):
        assets.append(_make_asset(idx=i, asset_type=AssetType.IMAGE, page=0))
    for i in range(4, 6):
        assets.append(_make_asset(idx=i, asset_type=AssetType.VECTOR_PDF, page=1))
    for i in range(6, 8):
        assets.append(_make_asset(idx=i, asset_type=AssetType.TABLE_SNAP, page=2))
    return _make_ledger(assets, total_pages=3)


@pytest.fixture
def sample_ledger_multipage() -> AssetLedger:
    assets: List[Asset] = []
    idx = 0
    for page in range(4):
        for _ in range(3):
            assets.append(_make_asset(idx=idx, page=page))
            idx += 1
    return _make_ledger(assets, total_pages=4)


@pytest.fixture
def sample_ledger_multi_occurrence() -> AssetLedger:
    assets: List[Asset] = []
    base_sha = "a" * 64
    for occ in range(1, 3):
        asset = Asset(
            asset_id=f"img-shared-p0-occ{occ}",
            asset_type=AssetType.IMAGE,
            sha256=base_sha,
            page_number=0,
            bbox=BBox(10 * occ, 20 * occ, 60 * occ, 120 * occ),
            ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            file_path=Path(f"/tmp/img-shared-{occ}.png"),
            occurrence=occ,
            anchor_to=f"p.instructions.{occ:03d}",
            image_width=400,
            image_height=300,
        )
        assets.append(asset)
    assets.extend(_make_asset(idx=10 + i) for i in range(3))
    return _make_ledger(assets, total_pages=2)


@pytest.fixture
def large_ledger() -> AssetLedger:
    assets = [_make_asset(idx=i, page=i % 5) for i in range(120)]
    return _make_ledger(assets, total_pages=5)


@pytest.fixture
def sample_ledger_50_pages() -> AssetLedger:
    assets: List[Asset] = []
    idx = 0
    for page in range(50):
        for _ in range(2):
            assets.append(_make_asset(idx=idx, page=page))
            idx += 1
    return _make_ledger(assets, total_pages=50)


class TestCompletenessChecker:
    """Unit tests for CompletenessChecker."""

    def test_perfect_coverage(self, sample_ledger, sample_output_pdf):
        """Test detection of 100% asset coverage."""
        checker = CompletenessChecker(require_perfect=True)

        # Mock all assets placed
        placed_labels = [
            {"asset_id": asset.asset_id, "page": asset.page_number}
            for asset in sample_ledger.assets
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        assert report.passed
        assert report.coverage_percentage == 100.0
        assert report.total_assets == len(sample_ledger.assets)
        assert report.placed_assets == len(sample_ledger.assets)
        assert len(report.missing_assets) == 0
        assert not report.warnings

    def test_missing_assets_detected(self, sample_ledger, sample_output_pdf):
        """Test detection of missing assets."""
        checker = CompletenessChecker()

        # Mock only 5 assets placed (out of 10)
        placed_labels = [
            {"asset_id": asset.asset_id, "page": asset.page_number}
            for asset in sample_ledger.assets[:5]
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        assert not report.passed
        assert len(report.missing_assets) == 5
        assert report.coverage_percentage == 50.0
        assert report.total_assets == 10
        assert report.placed_assets == 5
        assert any("missing" in w.lower() for w in report.warnings)

    def test_coverage_by_type(self, sample_ledger_mixed_types, sample_output_pdf):
        """Test coverage calculation by asset type."""
        checker = CompletenessChecker()

        # Place only images (not vectors or tables)
        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger_mixed_types.assets
            if asset.asset_type.value == "image"
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger_mixed_types,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        # Image coverage should be 100%
        assert report.by_type.get("image", 0) == 100.0
        # Other types should be 0%
        assert report.by_type.get("vector_pdf", 100) == 0.0
        assert report.by_type.get("table_snap", 100) == 0.0

    def test_coverage_by_page(self, sample_ledger_multipage, sample_output_pdf):
        """Test coverage calculation by page."""
        checker = CompletenessChecker()

        # Place assets only from page 0
        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger_multipage.assets
            if asset.page_number == 0
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger_multipage,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        # Page 0 should have 100% coverage
        assert report.by_page[0] == 100.0
        # Other pages should have 0% coverage
        assert all(pct == 0.0 for page, pct in report.by_page.items() if page != 0)

    def test_partial_coverage_with_threshold(self, sample_ledger, sample_output_pdf):
        """Test partial coverage with configurable threshold."""
        # Allow 90% coverage to pass
        checker = CompletenessChecker(require_perfect=False, min_coverage=90.0)

        # Place 95% of assets (9 out of 10)
        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger.assets[:9]
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        assert report.passed  # 90% ≤ 95%
        assert report.coverage_percentage == 90.0
        assert len(report.missing_assets) == 1

    def test_empty_ledger(self, empty_ledger, sample_output_pdf):
        """Test handling of empty asset ledger."""
        checker = CompletenessChecker()

        report = checker.check_completeness(
            source_ledger=empty_ledger,
            output_pdf=sample_output_pdf,
            placed_labels=[]
        )

        # Edge case: empty ledger should pass with 0% coverage (no assets to check)
        assert report.coverage_percentage == 0.0
        assert report.total_assets == 0
        assert report.placed_assets == 0

    def test_no_placed_assets(self, sample_ledger, sample_output_pdf):
        """Test case where no assets were placed."""
        checker = CompletenessChecker()

        report = checker.check_completeness(
            source_ledger=sample_ledger,
            output_pdf=sample_output_pdf,
            placed_labels=[]
        )

        assert not report.passed
        assert report.coverage_percentage == 0.0
        assert len(report.missing_assets) == len(sample_ledger.assets)
        assert report.placed_assets == 0

    def test_duplicate_placed_assets(self, sample_ledger, sample_output_pdf):
        """Test handling of duplicate placed asset IDs."""
        checker = CompletenessChecker()

        # Mock duplicate placements (should be handled correctly)
        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger.assets
        ] + [
            {"asset_id": sample_ledger.assets[0].asset_id}  # Duplicate first asset
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        # Should still show 100% (duplicates don't affect coverage)
        assert report.passed
        assert report.coverage_percentage == 100.0

    def test_extra_placed_assets(self, sample_ledger, sample_output_pdf):
        """Test case with assets placed that aren't in source ledger."""
        checker = CompletenessChecker()

        # Include all source assets + extra unknown asset
        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger.assets
        ] + [
            {"asset_id": "img-unknown-p0-occ1"}
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        # Should still pass (extra assets don't fail the check)
        assert report.passed
        assert report.coverage_percentage == 100.0
        # Could add warning about unknown assets

    def test_systematic_type_failure(self, sample_ledger_mixed_types, sample_output_pdf):
        """Test detection of systematic failures by asset type."""
        checker = CompletenessChecker()

        # Place everything except vectors
        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger_mixed_types.assets
            if asset.asset_type.value != "vector_pdf"
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger_mixed_types,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        assert not report.passed
        assert report.by_type["vector_pdf"] == 0.0
        assert any("vector_pdf" in str(r).lower() for r in report.recommendations)

    def test_systematic_page_failure(self, sample_ledger_multipage, sample_output_pdf):
        """Test detection of systematic failures by page."""
        checker = CompletenessChecker()

        # Skip page 2 entirely
        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger_multipage.assets
            if asset.page_number != 2
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger_multipage,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        assert not report.passed
        assert report.by_page[2] == 0.0
        assert any("page" in str(w).lower() for w in report.warnings)

    def test_report_serialization(self, sample_ledger, sample_output_pdf):
        """Test report can be serialized to dict."""
        checker = CompletenessChecker()

        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger.assets[:5]
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        report_dict = report.to_dict()

        assert isinstance(report_dict, dict)
        assert "passed" in report_dict
        assert "coverage_percentage" in report_dict
        assert "missing_assets" in report_dict
        assert report_dict["passed"] == False
        assert report_dict["coverage_percentage"] == 50.0

    def test_missing_report_generation(self, sample_ledger):
        """Test generation of detailed missing asset report."""
        checker = CompletenessChecker()

        missing_ids = [sample_ledger.assets[0].asset_id, sample_ledger.assets[1].asset_id]

        report_text = checker.generate_missing_report(
            source_ledger=sample_ledger,
            missing_ids=missing_ids
        )

        assert "Missing Assets Report" in report_text
        assert sample_ledger.assets[0].asset_id in report_text
        assert sample_ledger.assets[1].asset_id in report_text
        assert "Type:" in report_text
        assert "Page:" in report_text

    def test_multi_occurrence_assets(self, sample_ledger_multi_occurrence, sample_output_pdf):
        """Test handling of assets with multiple occurrences."""
        checker = CompletenessChecker()

        # Place all occurrences
        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger_multi_occurrence.assets
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger_multi_occurrence,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        assert report.passed
        # Each occurrence is tracked separately
        assert report.coverage_percentage == 100.0

    def test_missing_second_occurrence(self, sample_ledger_multi_occurrence, sample_output_pdf):
        """Test detection when second occurrence is missing."""
        checker = CompletenessChecker()

        # Place only first occurrence of duplicate asset
        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger_multi_occurrence.assets
            if asset.occurrence == 1
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger_multi_occurrence,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        assert not report.passed
        # Should detect missing second occurrences
        assert len(report.missing_assets) > 0

    def test_coverage_warnings_threshold(self, sample_ledger, sample_output_pdf):
        """Test that warnings are generated at appropriate thresholds."""
        checker = CompletenessChecker(require_perfect=False, min_coverage=80.0)

        # Place 85% of assets (8.5 → 8 out of 10)
        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger.assets[:8]
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        assert report.passed  # 80% ≤ 80%
        assert len(report.missing_assets) == 2
        assert len(report.warnings) > 0  # Should warn even if passing

    def test_recommendations_generated(self, sample_ledger, sample_output_pdf):
        """Test that actionable recommendations are generated."""
        checker = CompletenessChecker()

        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger.assets[:3]
        ]

        report = checker.check_completeness(
            source_ledger=sample_ledger,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )

        assert not report.passed
        assert len(report.recommendations) > 0
        # Recommendations should be actionable
        assert any("review" in r.lower() or "check" in r.lower() for r in report.recommendations)


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestCompletenessCheckerPerformance:
    """Performance tests for completeness checker."""

    def test_large_ledger_performance(self, large_ledger, sample_output_pdf):
        """Test performance with large asset ledger (100+ assets)."""
        import time

        checker = CompletenessChecker()

        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in large_ledger.assets
        ]

        start = time.time()
        report = checker.check_completeness(
            source_ledger=large_ledger,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )
        duration = time.time() - start

        assert report.passed
        assert duration < 1.0  # Should complete in under 1 second

    def test_multipage_performance(self, sample_ledger_50_pages, sample_output_pdf):
        """Test performance with multi-page document (50 pages)."""
        import time

        checker = CompletenessChecker()

        placed_labels = [
            {"asset_id": asset.asset_id}
            for asset in sample_ledger_50_pages.assets
        ]

        start = time.time()
        report = checker.check_completeness(
            source_ledger=sample_ledger_50_pages,
            output_pdf=sample_output_pdf,
            placed_labels=placed_labels
        )
        duration = time.time() - start

        assert report.passed
        assert duration < 2.0  # Should scale well
