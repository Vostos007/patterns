"""Unit tests for the visual diff module."""

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
from PIL import Image

from kps.core import Asset, AssetLedger, AssetType, BBox
from kps.qa.visual_diff import VisualDiffer


def _solid_image(color: Tuple[int, int, int], size: Tuple[int, int]) -> Image.Image:
    return Image.new("RGB", size, color=color)


def _make_asset(idx: int, bbox: Tuple[float, float, float, float]) -> Asset:
    return Asset(
        asset_id=f"img-{idx:03d}",
        asset_type=AssetType.IMAGE,
        sha256=("%064x" % idx)[:64],
        page_number=0,
        bbox=BBox(*bbox),
        ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        file_path=Path("asset.png"),
        occurrence=1,
        anchor_to="p.test.001",
        image_width=int(bbox[2] - bbox[0]),
        image_height=int(bbox[3] - bbox[1]),
    )


class StubRasterizer:
    """Minimal stub that returns pre-baked images."""

    def __init__(self, pages: Dict[Tuple[str, int], Image.Image]):
        self._pages = pages

    def rasterize_page(self, pdf_path: Path, page_index: int) -> Image.Image:
        key = (pdf_path.name, page_index)
        return self._pages[key]


def test_compare_images_identical_mask_full():
    size = (40, 40)
    red = _solid_image((220, 10, 10), size)
    mask = np.ones(size[::-1], dtype=np.uint8) * 255

    differ = VisualDiffer(pixel_threshold=5, diff_threshold=0.02)
    metrics, diff_image = differ.compare_images(red, red, mask, generate_diff_image=True)

    assert metrics.diff_ratio == 0.0
    assert metrics.differing_pixels == 0
    assert diff_image is not None


def test_compare_images_detects_change_inside_mask():
    size = (30, 30)
    base = _solid_image((0, 0, 0), size)
    modified = base.copy()
    modified_pixels = modified.load()
    for x in range(10):
        for y in range(10):
            modified_pixels[x, y] = (200, 0, 0)

    mask = np.zeros(size[::-1], dtype=np.uint8)
    mask[:10, :10] = 255

    differ = VisualDiffer(pixel_threshold=10, diff_threshold=0.02)
    metrics, _ = differ.compare_images(base, modified, mask)

    assert metrics.differing_pixels == 100
    assert metrics.diff_ratio == 1.0


def test_compare_images_ignores_changes_outside_mask():
    size = (20, 20)
    base = _solid_image((20, 20, 20), size)
    modified = base.copy()
    modified_pixels = modified.load()
    for x in range(5, 10):
        for y in range(5, 10):
            modified_pixels[x, y] = (255, 255, 255)

    mask = np.zeros(size[::-1], dtype=np.uint8)
    mask[:5, :5] = 255  # Mask different region

    differ = VisualDiffer(pixel_threshold=10, diff_threshold=0.02)
    metrics, _ = differ.compare_images(base, modified, mask)

    assert metrics.differing_pixels == 0
    assert metrics.diff_ratio == 0.0


def test_compare_pdf_pages_uses_mask_and_threshold(tmp_path):
    page_size = (100.0, 100.0)
    size = (100, 100)
    source_image = _solid_image((0, 0, 0), size)
    target_image = source_image.copy()
    tgt_pixels = target_image.load()
    for x in range(20, 40):
        for y in range(20, 40):
            tgt_pixels[x, y] = (255, 255, 255)

    source_pdf = tmp_path / "source.pdf"
    target_pdf = tmp_path / "target.pdf"
    source_pdf.write_text("dummy")
    target_pdf.write_text("dummy")

    assets = [_make_asset(0, (20, 20, 40, 40))]

    pages = {
        (source_pdf.name, 0): source_image,
        (target_pdf.name, 0): target_image,
    }

    differ = VisualDiffer(
        pixel_threshold=10,
        diff_threshold=0.1,
        rasterizer=StubRasterizer(pages),
    )

    report = differ.compare_pdf_pages(
        source_pdf,
        target_pdf,
        page_index=0,
        assets=assets,
        page_size=page_size,
        return_diff_image=True,
    )

    assert not report.passed
    assert report.metrics.differing_pixels > 0
    assert report.diff_image is not None
    assert report.recommendations


def test_compare_documents_aggregates_results(tmp_path):
    size = (80, 80)
    src_img = _solid_image((0, 0, 0), size)
    tgt_img = _solid_image((0, 0, 0), size)

    source_pdf = tmp_path / "source2.pdf"
    target_pdf = tmp_path / "target2.pdf"
    source_pdf.write_text("dummy")
    target_pdf.write_text("dummy")

    assets = [_make_asset(0, (0, 0, 80, 80))]
    ledger = AssetLedger(assets=assets, source_pdf=source_pdf, total_pages=1)
    pages = {
        (source_pdf.name, 0): src_img,
        (target_pdf.name, 0): tgt_img,
    }

    differ = VisualDiffer(rasterizer=StubRasterizer(pages))
    passed, reports = differ.compare_documents(
        source_pdf,
        target_pdf,
        ledger,
        page_dimensions=[(80.0, 80.0)],
    )

    assert passed
    assert len(reports) == 1
    assert reports[0].metrics.diff_ratio == 0.0
