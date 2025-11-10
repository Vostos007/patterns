"""Unit tests for the DPI validator."""

from pathlib import Path
from typing import List

import pytest

from kps.core import Asset, AssetLedger, AssetType, BBox
from kps.qa.dpi_validator import DPIValidator


def _make_asset(
    asset_id: str,
    *,
    width_px: int,
    height_px: int,
    bbox: BBox,
    page: int = 0,
) -> Asset:
    hex_seed = (asset_id.encode("utf-8").hex() * 32)[:64]
    return Asset(
        asset_id=asset_id,
        asset_type=AssetType.IMAGE,
        sha256=hex_seed,
        page_number=page,
        bbox=bbox,
        ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        file_path=Path("assets") / f"{asset_id}.png",
        occurrence=1,
        anchor_to=f"p.test.{asset_id}",
        image_width=width_px,
        image_height=height_px,
    )


def _ledger(assets: List[Asset]) -> AssetLedger:
    return AssetLedger(
        assets=assets,
        source_pdf=Path("source.pdf"),
        total_pages=max((a.page_number for a in assets), default=0) + 1,
    )


def test_validate_dpi_all_images_pass(tmp_path: Path):
    bbox = BBox(0, 0, 100, 100)  # 100 pt = 1.39 in
    # 600 px on 100 pt => (600/100)*72 = 432 DPI
    asset = _make_asset("img-001", width_px=600, height_px=600, bbox=bbox)
    ledger = _ledger([asset])

    placed_labels = [
        {
            "asset_id": asset.asset_id,
            "bbox_placed": [bbox.x0, bbox.y0, bbox.x1, bbox.y1],
        }
    ]

    validator = DPIValidator()
    report = validator.validate_dpi(
        pdf_path=tmp_path / "output.pdf",
        source_ledger=ledger,
        placed_labels=placed_labels,
    )

    assert report.passed
    assert report.images_with_errors == 0
    assert any("meet or exceed" in rec for rec in report.recommendations)


def test_validate_dpi_detects_low_quality(tmp_path: Path):
    bbox = BBox(0, 0, 200, 200)  # Larger placement
    # 400 px over 200 pt => (400/200)*72 = 144 DPI
    asset = _make_asset("img-002", width_px=400, height_px=400, bbox=bbox)
    ledger = _ledger([asset])

    placed_labels = [
        {
            "asset_id": asset.asset_id,
            "bbox_placed": [bbox.x0, bbox.y0, bbox.x1, bbox.y1],
        }
    ]

    validator = DPIValidator()
    report = validator.validate_dpi(
        pdf_path=tmp_path / "output.pdf",
        source_ledger=ledger,
        placed_labels=placed_labels,
    )

    assert not report.passed
    assert report.images_with_errors == 1
    assert any("low" in issue.issue_type for issue in report.issues)
    assert report.errors


def test_validate_dpi_flags_upscaled_assets(tmp_path: Path):
    bbox_source = BBox(0, 0, 100, 100)
    asset = _make_asset("img-003", width_px=1000, height_px=1000, bbox=bbox_source)
    ledger = _ledger([asset])

    placed_labels = [
        {
            "asset_id": asset.asset_id,
            "bbox_placed": [
                bbox_source.x0,
                bbox_source.y0,
                bbox_source.x1 * 1.5,
                bbox_source.y1 * 1.5,
            ],
        }
    ]

    validator = DPIValidator(max_upscale=1.2)
    report = validator.validate_dpi(
        pdf_path=tmp_path / "output.pdf",
        source_ledger=ledger,
        placed_labels=placed_labels,
    )

    assert report.upscaled_images
    assert any("upscaled" in warning for warning in report.warnings)
