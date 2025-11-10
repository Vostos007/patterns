"""PDF rasterization module for visual comparison.

This module handles conversion of PDF pages to raster images at configurable DPI
for pixel-level comparison in the visual diff pipeline.
"""

try:  # pragma: no cover - optional dependency
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - exercised when dependency missing
    fitz = None
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class RasterizationError(Exception):
    """Raised when PDF rasterization fails."""
    pass


class PDFRasterizer:
    """Rasterize PDF pages to high-quality images for visual comparison.

    This class handles conversion of PDF pages to raster images using PyMuPDF,
    with configurable DPI and color space settings.

    Attributes:
        dpi: Dots per inch for rasterization (default: 150)
        colorspace: Color space for output images (default: RGB)
        alpha: Whether to include alpha channel (default: False)
    """

    def __init__(
        self,
        dpi: int = 150,
        colorspace: str = "RGB",
        alpha: bool = False
    ):
        """Initialize PDF rasterizer.

        Args:
            dpi: Resolution for rasterization. Higher DPI = better quality but larger images.
                 Recommended: 150 for general use, 300 for high-quality comparison
            colorspace: PIL colorspace ('RGB', 'L' for grayscale, 'RGBA')
            alpha: Include alpha channel in output
        """
        self.dpi = dpi
        self.colorspace = colorspace
        self.alpha = alpha
        self.zoom = dpi / 72.0  # PDF uses 72 DPI as base

        logger.info(f"Initialized PDFRasterizer: DPI={dpi}, colorspace={colorspace}")

    def rasterize_pdf(
        self,
        pdf_path: Path,
        page_range: Optional[Tuple[int, int]] = None
    ) -> List[Image.Image]:
        """Rasterize all pages (or range) of PDF to images.

        Args:
            pdf_path: Path to PDF file
            page_range: Optional (start, end) page indices (0-based, inclusive)

        Returns:
            List of PIL Images, one per page

        Raises:
            RasterizationError: If PDF cannot be opened or rasterized
        """
        if fitz is None:
            raise RasterizationError(
                "PyMuPDF (fitz) is required for rasterization but is not installed."
            )
        if not pdf_path.exists():
            raise RasterizationError(f"PDF not found: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
            logger.info(f"Opened PDF: {pdf_path.name} ({len(doc)} pages)")
        except Exception as e:
            raise RasterizationError(f"Failed to open PDF {pdf_path}: {e}")

        images = []

        # Determine page range
        start_page = page_range[0] if page_range else 0
        end_page = page_range[1] + 1 if page_range else len(doc)

        # Create transformation matrix for zoom
        mat = fitz.Matrix(self.zoom, self.zoom)

        try:
            for page_num in range(start_page, end_page):
                if page_num >= len(doc):
                    logger.warning(f"Page {page_num} out of range, stopping")
                    break

                page = doc[page_num]

                # Render page to pixmap
                pix = page.get_pixmap(
                    matrix=mat,
                    alpha=self.alpha
                )

                # Convert to PIL Image
                img = Image.frombytes(
                    "RGBA" if self.alpha else "RGB",
                    [pix.width, pix.height],
                    pix.samples
                )

                # Convert to target colorspace if needed
                if self.colorspace != img.mode:
                    img = img.convert(self.colorspace)

                images.append(img)

                logger.debug(
                    f"Rasterized page {page_num}: {img.size[0]}x{img.size[1]} "
                    f"({img.mode})"
                )

        except Exception as e:
            raise RasterizationError(f"Failed to rasterize page {page_num}: {e}")

        finally:
            doc.close()

        logger.info(f"Rasterized {len(images)} pages from {pdf_path.name}")
        return images

    def rasterize_page(
        self,
        pdf_path: Path,
        page_num: int
    ) -> Image.Image:
        """Rasterize a single page.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (0-based)

        Returns:
            PIL Image of the page
        """
        images = self.rasterize_pdf(pdf_path, page_range=(page_num, page_num))

        if not images:
            raise RasterizationError(f"Failed to rasterize page {page_num}")

        return images[0]

    def get_page_dimensions(self, pdf_path: Path) -> List[Tuple[float, float]]:
        """Get dimensions of all pages in PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of (width, height) tuples in PDF points (72 DPI)
        """
        if fitz is None:
            raise RasterizationError(
                "PyMuPDF (fitz) is required for rasterization but is not installed."
            )
        try:
            doc = fitz.open(pdf_path)
            dimensions = []

            for page in doc:
                rect = page.rect
                dimensions.append((rect.width, rect.height))

            doc.close()
            return dimensions

        except Exception as e:
            raise RasterizationError(f"Failed to get page dimensions: {e}")

    def get_page_count(self, pdf_path: Path) -> int:
        """Get number of pages in PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Number of pages
        """
        if fitz is None:
            raise RasterizationError(
                "PyMuPDF (fitz) is required for rasterization but is not installed."
            )
        try:
            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            return count
        except Exception as e:
            raise RasterizationError(f"Failed to get page count: {e}")


class RasterizationCache:
    """Cache for rasterized PDF pages to avoid repeated rendering.

    Useful when comparing the same PDF multiple times or when doing
    incremental comparisons.
    """

    def __init__(self, max_cache_size_mb: int = 500):
        """Initialize cache.

        Args:
            max_cache_size_mb: Maximum cache size in megabytes
        """
        self._cache = {}
        self._cache_size = 0
        self.max_cache_size = max_cache_size_mb * 1024 * 1024

    def get(
        self,
        pdf_path: Path,
        page_num: int,
        dpi: int
    ) -> Optional[Image.Image]:
        """Get cached image if available.

        Args:
            pdf_path: Path to PDF
            page_num: Page number
            dpi: DPI used for rasterization

        Returns:
            Cached image or None
        """
        key = (str(pdf_path), page_num, dpi)
        return self._cache.get(key)

    def put(
        self,
        pdf_path: Path,
        page_num: int,
        dpi: int,
        image: Image.Image
    ):
        """Add image to cache.

        Args:
            pdf_path: Path to PDF
            page_num: Page number
            dpi: DPI used for rasterization
            image: Rasterized image
        """
        key = (str(pdf_path), page_num, dpi)

        # Estimate image size in bytes
        image_size = image.size[0] * image.size[1] * len(image.mode)

        # Check if adding would exceed cache size
        if self._cache_size + image_size > self.max_cache_size:
            self.clear()

        self._cache[key] = image
        self._cache_size += image_size

    def clear(self):
        """Clear entire cache."""
        self._cache.clear()
        self._cache_size = 0
        logger.debug("Rasterization cache cleared")
