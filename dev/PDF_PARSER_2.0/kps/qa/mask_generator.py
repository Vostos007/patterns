"""Mask generation from asset bounding boxes.

This module creates binary masks from asset bounding boxes for focused
visual comparison in the QA pipeline.
"""

import numpy as np
from PIL import Image, ImageDraw
from typing import List, Tuple, Optional
from pathlib import Path
import logging

from kps.core import Asset, BBox

logger = logging.getLogger(__name__)


class MaskGenerator:
    """Generate binary masks from asset bounding boxes.

    Creates masks that isolate specific regions of a page for focused
    visual comparison. Supports dilation to add margins around assets.

    Attributes:
        default_dilation: Default dilation in pixels (default: 5)
    """

    def __init__(self, default_dilation: int = 5):
        """Initialize mask generator.

        Args:
            default_dilation: Default margin to add around asset bboxes (pixels)
        """
        self.default_dilation = default_dilation

    def generate_page_mask(
        self,
        assets: List[Asset],
        image_size: Tuple[int, int],
        page_size: Tuple[float, float],
        dilation: Optional[int] = None
    ) -> np.ndarray:
        """Generate binary mask for all assets on a page.

        Creates a composite mask where asset regions are white (255)
        and background is black (0).

        Args:
            assets: Assets on this page
            image_size: Rasterized image size in pixels (width, height)
            page_size: PDF page size in points (width, height)
            dilation: Pixels to expand mask around each asset.
                     If None, uses default_dilation.

        Returns:
            Binary mask as numpy array (0=background, 255=asset regions)
        """
        if dilation is None:
            dilation = self.default_dilation

        # Create blank mask
        mask = Image.new('L', image_size, 0)
        draw = ImageDraw.Draw(mask)

        # Calculate scale factor from PDF points to pixels
        scale_x = image_size[0] / page_size[0]
        scale_y = image_size[1] / page_size[1]

        logger.debug(
            f"Generating mask for {len(assets)} assets. "
            f"Image: {image_size}, Page: {page_size}, Scale: {scale_x:.2f}x{scale_y:.2f}"
        )

        for asset in assets:
            # Convert bbox from PDF points to pixel coordinates
            x0 = int(asset.bbox.x0 * scale_x)
            y0 = int(asset.bbox.y0 * scale_y)
            x1 = int(asset.bbox.x1 * scale_x)
            y1 = int(asset.bbox.y1 * scale_y)

            # Apply dilation (add margin)
            x0 = max(0, x0 - dilation)
            y0 = max(0, y0 - dilation)
            x1 = min(image_size[0], x1 + dilation)
            y1 = min(image_size[1], y1 + dilation)

            # Draw rectangle on mask
            draw.rectangle([x0, y0, x1, y1], fill=255)

            logger.debug(
                f"Asset {asset.asset_id}: bbox ({x0}, {y0}, {x1}, {y1})"
            )

        return np.array(mask)

    def generate_asset_mask(
        self,
        asset: Asset,
        image_size: Tuple[int, int],
        page_size: Tuple[float, float],
        dilation: Optional[int] = None
    ) -> np.ndarray:
        """Generate mask for a single asset.

        Args:
            asset: Asset to create mask for
            image_size: Rasterized image size in pixels
            page_size: PDF page size in points
            dilation: Pixels to expand mask

        Returns:
            Binary mask for this asset only
        """
        return self.generate_page_mask(
            [asset],
            image_size,
            page_size,
            dilation
        )

    def generate_asset_masks_separate(
        self,
        assets: List[Asset],
        image_size: Tuple[int, int],
        page_size: Tuple[float, float],
        dilation: Optional[int] = None
    ) -> List[Tuple[Asset, np.ndarray]]:
        """Generate individual masks for each asset.

        Args:
            assets: Assets on this page
            image_size: Rasterized image size in pixels
            page_size: PDF page size in points
            dilation: Pixels to expand masks

        Returns:
            List of (asset, mask) tuples
        """
        masks = []

        for asset in assets:
            mask = self.generate_asset_mask(
                asset,
                image_size,
                page_size,
                dilation
            )
            masks.append((asset, mask))

        return masks

    def apply_mask(
        self,
        image: Image.Image,
        mask: np.ndarray,
        fill_color: Tuple[int, int, int] = (128, 128, 128)
    ) -> Image.Image:
        """Apply mask to image, filling masked regions.

        Args:
            image: Source image
            mask: Binary mask (0=mask out, 255=keep)
            fill_color: Color to fill masked-out regions (RGB)

        Returns:
            Image with mask applied
        """
        # Convert to numpy
        img_array = np.array(image.convert('RGB'))

        # Create fill image
        fill_array = np.full_like(img_array, fill_color)

        # Apply mask (where mask=255, keep original; where mask=0, use fill)
        mask_3d = np.stack([mask, mask, mask], axis=2) / 255.0
        result = (img_array * mask_3d + fill_array * (1 - mask_3d)).astype(np.uint8)

        return Image.fromarray(result)

    def invert_mask(self, mask: np.ndarray) -> np.ndarray:
        """Invert binary mask.

        Args:
            mask: Binary mask

        Returns:
            Inverted mask
        """
        return 255 - mask

    def save_mask(self, mask: np.ndarray, output_path: Path):
        """Save mask as image file.

        Args:
            mask: Binary mask
            output_path: Path to save mask image
        """
        mask_img = Image.fromarray(mask, mode='L')
        mask_img.save(output_path)
        logger.debug(f"Saved mask to {output_path}")

    def visualize_mask_overlay(
        self,
        image: Image.Image,
        mask: np.ndarray,
        color: Tuple[int, int, int] = (255, 0, 0),
        alpha: float = 0.3
    ) -> Image.Image:
        """Create visualization of mask overlaid on image.

        Args:
            image: Background image
            mask: Binary mask to overlay
            color: Color for mask overlay (RGB)
            alpha: Transparency of overlay (0-1)

        Returns:
            Image with colored mask overlay
        """
        # Convert image to RGBA
        img_rgba = image.convert('RGBA')
        img_array = np.array(img_rgba)

        # Create overlay
        overlay = np.zeros_like(img_array)
        overlay[:, :, 0] = color[0]
        overlay[:, :, 1] = color[1]
        overlay[:, :, 2] = color[2]
        overlay[:, :, 3] = (mask * alpha).astype(np.uint8)

        # Composite
        overlay_img = Image.fromarray(overlay, 'RGBA')
        result = Image.alpha_composite(img_rgba, overlay_img)

        return result.convert('RGB')


class MaskType:
    """Predefined mask types for different comparison scenarios."""

    @staticmethod
    def full_page(image_size: Tuple[int, int]) -> np.ndarray:
        """Create mask covering entire page.

        Args:
            image_size: Image size (width, height)

        Returns:
            Full white mask
        """
        return np.full((image_size[1], image_size[0]), 255, dtype=np.uint8)

    @staticmethod
    def border_exclude(
        image_size: Tuple[int, int],
        border_width: int = 20
    ) -> np.ndarray:
        """Create mask excluding page borders.

        Useful for ignoring edge artifacts or crop marks.

        Args:
            image_size: Image size (width, height)
            border_width: Width of border to exclude (pixels)

        Returns:
            Mask with borders blacked out
        """
        mask = np.full((image_size[1], image_size[0]), 255, dtype=np.uint8)

        # Black out borders
        mask[:border_width, :] = 0  # Top
        mask[-border_width:, :] = 0  # Bottom
        mask[:, :border_width] = 0  # Left
        mask[:, -border_width:] = 0  # Right

        return mask

    @staticmethod
    def checkerboard(
        image_size: Tuple[int, int],
        square_size: int = 50
    ) -> np.ndarray:
        """Create checkerboard pattern mask.

        Useful for sampling-based comparison.

        Args:
            image_size: Image size (width, height)
            square_size: Size of checkerboard squares

        Returns:
            Checkerboard mask
        """
        mask = np.zeros((image_size[1], image_size[0]), dtype=np.uint8)

        for y in range(0, image_size[1], square_size):
            for x in range(0, image_size[0], square_size):
                # Alternate squares
                if ((x // square_size) + (y // square_size)) % 2 == 0:
                    y_end = min(y + square_size, image_size[1])
                    x_end = min(x + square_size, image_size[0])
                    mask[y:y_end, x:x_end] = 255

        return mask
