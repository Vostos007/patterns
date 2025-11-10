"""Unit tests for the QA geometry validator."""

import math
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pytest

from kps.core import Asset, AssetLedger, AssetType, BBox
from kps.qa.geometry_validator import (
    GeometryReport,
    GeometryValidator,
    PlacementError,
)


def _make_asset(
    *,
    idx: int,
    page: int = 0,
    width: int = 100,
    height: int = 80,
    anchor_suffix: str = "materials",
) -> Asset:
    asset_id = f"img-{idx:04d}-p{page}-occ1"
    sha256 = f"{idx:064x}"[:64]
    bbox = BBox(50 + idx, 100 + idx, 50 + idx + width, 100 + idx + height)
    return Asset(
        asset_id=asset_id,
        asset_type=AssetType.IMAGE,
        sha256=sha256,
        page_number=page,
        bbox=bbox,
        ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        file_path=Path(f"/tmp/{asset_id}.png"),
        occurrence=1,
        anchor_to=f"p.{anchor_suffix}.{idx:03d}",
        image_width=width,
        image_height=height,
    )


def _make_ledger(assets: Iterable[Asset], total_pages: int = 1) -> AssetLedger:
    return AssetLedger(
        assets=list(assets),
        source_pdf=Path("source.pdf"),
        total_pages=total_pages,
    )


def _placed_label(asset: Asset, *, offset: Tuple[float, float] = (0.0, 0.0)) -> Dict:
    dx, dy = offset
    bbox = asset.bbox
    placed = BBox(bbox.x0 + dx, bbox.y0 + dy, bbox.x1 + dx, bbox.y1 + dy)
    return {
        "asset_id": asset.asset_id,
        "page": asset.page_number,
        "bbox_placed": [
            placed.x0,
            placed.y0,
            placed.x1,
            placed.y1,
        ],
    }


@pytest.fixture
def geometry_ledger() -> AssetLedger:
    assets = [_make_asset(idx=i, page=i % 3) for i in range(12)]
    return _make_ledger(assets, total_pages=3)


@pytest.fixture
def perfect_labels(geometry_ledger: AssetLedger) -> List[Dict]:
    return [_placed_label(asset) for asset in geometry_ledger.assets]


class TestErrorAnalysis:
    def test_to_dict_roundtrip(self):
        expected = BBox(0, 0, 100, 100)
        actual = BBox(1, 2, 101, 102)
        error = PlacementError(
            asset_id="img-0001",
            expected_bbox=expected,
            actual_bbox=actual,
            absolute_error=2.0,
            relative_error=1.2,
            passed=False,
            error_type="combined",
        )

        result = error.to_dict()

        assert result["asset_id"] == "img-0001"
        assert "expected_bbox" in result
        assert math.isclose(result["absolute_error"], 2.0)


class TestGeometryValidator:
    def test_perfect_alignment_passes(
        self, geometry_ledger: AssetLedger, perfect_labels: List[Dict]
    ):
        validator = GeometryValidator()

        report = validator.validate_geometry(
            source_ledger=geometry_ledger,
            placed_labels=perfect_labels,
        )

        assert isinstance(report, GeometryReport)
        assert report.passed
        assert report.failed_assets == 0
        assert report.pass_rate == pytest.approx(100.0)

    def test_detects_out_of_tolerance(self, geometry_ledger: AssetLedger):
        validator = GeometryValidator()

        labels = []
        for idx, asset in enumerate(geometry_ledger.assets):
            if idx == 0:
                labels.append(_placed_label(asset, offset=(5.5, 0.0)))
            else:
                labels.append(_placed_label(asset))

        report = validator.validate_geometry(
            source_ledger=geometry_ledger,
            placed_labels=labels,
        )

        assert not report.passed
        assert report.failed_assets == 1
        assert report.errors[0].asset_id == geometry_ledger.assets[0].asset_id
        assert report.errors[0].absolute_error == pytest.approx(5.5)
        assert any("Pass rate" in w for w in report.warnings)

    def test_relative_tolerance(self, geometry_ledger: AssetLedger):
        validator = GeometryValidator(tolerance_pt=0.5, tolerance_pct=5.0)

        tiny_asset = geometry_ledger.assets[0]
        small_bbox = BBox(tiny_asset.bbox.x0, tiny_asset.bbox.y0,
                          tiny_asset.bbox.x0 + 10, tiny_asset.bbox.y0 + 10)
        geometry_ledger.assets[0] = Asset(
            asset_id=tiny_asset.asset_id,
            asset_type=tiny_asset.asset_type,
            sha256=tiny_asset.sha256,
            page_number=tiny_asset.page_number,
            bbox=small_bbox,
            ctm=tiny_asset.ctm,
            file_path=tiny_asset.file_path,
            occurrence=1,
            anchor_to=tiny_asset.anchor_to,
            image_width=10,
            image_height=10,
        )

        labels = [_placed_label(asset) for asset in geometry_ledger.assets]
        labels[0] = _placed_label(geometry_ledger.assets[0], offset=(0.6, 0.6))

        report = validator.validate_geometry(
            source_ledger=geometry_ledger,
            placed_labels=labels,
        )

        assert report.errors[0].relative_error > report.errors[0].absolute_error
        assert not report.passed

    def test_systematic_offset_detection(self, geometry_ledger: AssetLedger):
        validator = GeometryValidator(min_pass_rate=90.0)

        labels = []
        for asset in geometry_ledger.assets:
            if asset.page_number == 1:
                labels.append(_placed_label(asset, offset=(3.5, 0.0)))
            else:
                labels.append(_placed_label(asset))

        report = validator.validate_geometry(
            source_ledger=geometry_ledger,
            placed_labels=labels,
        )

        assert not report.passed
        assert any("Systematic" in warning for warning in report.warnings)
        assert any("systematic" in rec.lower() for rec in report.recommendations)

    def test_missing_assets_are_ignored(self, geometry_ledger: AssetLedger):
        validator = GeometryValidator()

        labels = [_placed_label(asset) for asset in geometry_ledger.assets[5:]]

        report = validator.validate_geometry(
            source_ledger=geometry_ledger,
            placed_labels=labels,
        )

        assert report.total_assets == len(geometry_ledger.assets)
        assert report.passed_assets == len(labels)
        assert report.failed_assets == 0

    def test_serialization(self, geometry_ledger: AssetLedger, perfect_labels: List[Dict]):
        validator = GeometryValidator()
        report = validator.validate_geometry(
            source_ledger=geometry_ledger,
            placed_labels=perfect_labels,
        )

        payload = report.to_dict()

        assert isinstance(payload, dict)
        assert payload["passed"] is True
        assert "errors" in payload
