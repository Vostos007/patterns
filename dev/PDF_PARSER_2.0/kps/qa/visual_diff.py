"""Visual difference checking for translated PDFs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from kps.core import Asset, AssetLedger

from .constants import (
    RECOMMEND_VISUAL_REVIEW,
    VISUAL_DIFF_MAX_RATIO,
    VISUAL_DIFF_MIN_COVERAGE,
    VISUAL_DIFF_PIXEL_THRESHOLD,
    WARNING_LOW_MASK_COVERAGE,
)
from .mask_generator import MaskGenerator
from .rasterizer import PDFRasterizer
from . import image_utils


@dataclass(frozen=True)
class VisualDiffMetrics:
    """Quantitative metrics produced by a visual diff."""

    diff_ratio: float
    differing_pixels: int
    total_mask_pixels: int
    pixel_threshold: int
    mean_difference: float
    max_difference: float


@dataclass
class VisualDiffReport:
    """Result of comparing a single page."""

    passed: bool
    metrics: VisualDiffMetrics
    warnings: List[str]
    recommendations: List[str]
    diff_image: Optional[Image.Image] = None


class VisualDiffer:
    """Compare rendered PDF pages while focusing on asset regions."""

    def __init__(
        self,
        *,
        pixel_threshold: int = VISUAL_DIFF_PIXEL_THRESHOLD,
        diff_threshold: float = VISUAL_DIFF_MAX_RATIO,
        min_mask_coverage: float = VISUAL_DIFF_MIN_COVERAGE,
        rasterizer: Optional[PDFRasterizer] = None,
        mask_generator: Optional[MaskGenerator] = None,
    ) -> None:
        self.pixel_threshold = pixel_threshold
        self.diff_threshold = diff_threshold
        self.min_mask_coverage = min_mask_coverage
        self.rasterizer = rasterizer or PDFRasterizer(dpi=200, colorspace="RGB")
        self.mask_generator = mask_generator or MaskGenerator()

    def compare_images(
        self,
        source_image: Image.Image,
        target_image: Image.Image,
        mask: np.ndarray,
        *,
        generate_diff_image: bool = False,
    ) -> Tuple[VisualDiffMetrics, Optional[Image.Image]]:
        """Compare two already-rasterized images using a supplied mask."""

        aligned_source, aligned_target = image_utils.align_images(
            source_image, target_image
        )

        mask_array = self._prepare_mask(mask, aligned_source.size)
        mask_bool = mask_array > 0
        total_mask_pixels = int(mask_bool.sum())

        if total_mask_pixels == 0:
            metrics = VisualDiffMetrics(
                diff_ratio=0.0,
                differing_pixels=0,
                total_mask_pixels=0,
                pixel_threshold=self.pixel_threshold,
                mean_difference=0.0,
                max_difference=0.0,
            )
            diff_image = self._generate_diff_image(
                aligned_target, mask_bool, np.zeros(mask_bool.shape), generate=False
            )
            return metrics, diff_image

        src_arr = np.array(aligned_source.convert("RGB"), dtype=np.float32)
        tgt_arr = np.array(aligned_target.convert("RGB"), dtype=np.float32)

        pixel_deltas = np.abs(src_arr - tgt_arr)
        channel_max = pixel_deltas.max(axis=2)

        masked_deltas = channel_max[mask_bool]
        differing_pixels = int(
            np.count_nonzero(masked_deltas > self.pixel_threshold)
        )

        diff_ratio = differing_pixels / total_mask_pixels
        mean_difference = float(masked_deltas.mean()) if masked_deltas.size else 0.0
        max_difference = float(masked_deltas.max()) if masked_deltas.size else 0.0

        metrics = VisualDiffMetrics(
            diff_ratio=diff_ratio,
            differing_pixels=differing_pixels,
            total_mask_pixels=total_mask_pixels,
            pixel_threshold=self.pixel_threshold,
            mean_difference=mean_difference,
            max_difference=max_difference,
        )

        diff_image = self._generate_diff_image(
            aligned_target, mask_bool, channel_max, generate=generate_diff_image
        )

        return metrics, diff_image

    def compare_pdf_pages(
        self,
        source_pdf: Path,
        target_pdf: Path,
        page_index: int,
        assets: Sequence[Asset],
        page_size: Tuple[float, float],
        *,
        return_diff_image: bool = False,
        mask_dilation: Optional[int] = None,
    ) -> VisualDiffReport:
        """Rasterize and compare a single page from two PDFs."""

        source_image = self.rasterizer.rasterize_page(source_pdf, page_index)
        target_image = self.rasterizer.rasterize_page(target_pdf, page_index)

        mask = self.mask_generator.generate_page_mask(
            list(assets),
            source_image.size,
            page_size,
            dilation=mask_dilation,
        )

        metrics, diff_image = self.compare_images(
            source_image,
            target_image,
            mask,
            generate_diff_image=return_diff_image,
        )

        warnings: List[str] = []
        recommendations: List[str] = []

        if metrics.total_mask_pixels == 0:
            warnings.append("Mask contained no pixels; diff ratio set to 0.0")
        else:
            coverage = metrics.total_mask_pixels / (
                source_image.size[0] * source_image.size[1]
            )
            if coverage < self.min_mask_coverage:
                warnings.append(
                    f"{WARNING_LOW_MASK_COVERAGE}: {coverage:.4f} (min {self.min_mask_coverage:.4f})"
                )

        passed = metrics.diff_ratio <= self.diff_threshold
        if not passed:
            recommendations.append(RECOMMEND_VISUAL_REVIEW)

        return VisualDiffReport(
            passed=passed,
            metrics=metrics,
            warnings=warnings,
            recommendations=recommendations,
            diff_image=diff_image if return_diff_image else None,
        )

    def compare_documents(
        self,
        source_pdf: Path,
        target_pdf: Path,
        ledger: AssetLedger,
        page_dimensions: Sequence[Tuple[float, float]],
        *,
        return_diff_images: bool = False,
        mask_dilation: Optional[int] = None,
    ) -> Tuple[bool, List[VisualDiffReport]]:
        """Run the visual diff across all pages described by a ledger."""

        reports: List[VisualDiffReport] = []

        for page_index, page_size in enumerate(page_dimensions):
            page_assets = ledger.by_page(page_index)
            report = self.compare_pdf_pages(
                source_pdf,
                target_pdf,
                page_index,
                page_assets,
                page_size,
                return_diff_image=return_diff_images,
                mask_dilation=mask_dilation,
            )
            reports.append(report)

        overall_passed = all(report.passed for report in reports)
        return overall_passed, reports

    @staticmethod
    def _prepare_mask(mask: np.ndarray, image_size: Tuple[int, int]) -> np.ndarray:
        if mask.dtype != np.uint8:
            mask = mask.astype(np.uint8)

        target_width, target_height = image_size
        if mask.shape[1] != target_width or mask.shape[0] != target_height:
            mask_image = Image.fromarray(mask, mode="L").resize(
                (target_width, target_height), Image.Resampling.NEAREST
            )
            mask = np.array(mask_image, dtype=np.uint8)

        return mask

    def _generate_diff_image(
        self,
        base_image: Image.Image,
        mask_bool: np.ndarray,
        channel_max: np.ndarray,
        *,
        generate: bool,
    ) -> Optional[Image.Image]:
        if not generate:
            return None

        overlay = np.array(base_image.convert("RGB"), dtype=np.uint8)
        highlight_mask = mask_bool & (channel_max > self.pixel_threshold)

        overlay[highlight_mask] = np.array([255, 0, 255], dtype=np.uint8)

        return Image.fromarray(overlay, mode="RGB")
