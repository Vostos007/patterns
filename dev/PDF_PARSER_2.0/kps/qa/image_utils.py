"""Image processing utilities for visual comparison.

Common image operations used throughout the visual diff system.
"""

import numpy as np
from PIL import Image, ImageFilter, ImageOps
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def ensure_same_size(
    img1: Image.Image,
    img2: Image.Image,
    resize_mode: str = "fit"
) -> Tuple[Image.Image, Image.Image]:
    """Ensure two images have the same dimensions.

    Args:
        img1: First image
        img2: Second image
        resize_mode: How to resize:
            - "fit": Resize both to smaller dimensions
            - "expand": Resize both to larger dimensions
            - "first": Resize second to match first
            - "second": Resize first to match second

    Returns:
        Tuple of (img1, img2) with matching dimensions
    """
    if img1.size == img2.size:
        return img1, img2

    if resize_mode == "fit":
        target_width = min(img1.size[0], img2.size[0])
        target_height = min(img1.size[1], img2.size[1])
    elif resize_mode == "expand":
        target_width = max(img1.size[0], img2.size[0])
        target_height = max(img1.size[1], img2.size[1])
    elif resize_mode == "first":
        target_width, target_height = img1.size
    elif resize_mode == "second":
        target_width, target_height = img2.size
    else:
        raise ValueError(f"Unknown resize_mode: {resize_mode}")

    target_size = (target_width, target_height)

    if img1.size != target_size:
        img1 = img1.resize(target_size, Image.Resampling.LANCZOS)
        logger.debug(f"Resized img1 to {target_size}")

    if img2.size != target_size:
        img2 = img2.resize(target_size, Image.Resampling.LANCZOS)
        logger.debug(f"Resized img2 to {target_size}")

    return img1, img2


def ensure_same_mode(
    img1: Image.Image,
    img2: Image.Image,
    target_mode: Optional[str] = None
) -> Tuple[Image.Image, Image.Image]:
    """Ensure two images have the same color mode.

    Args:
        img1: First image
        img2: Second image
        target_mode: Target color mode. If None, uses img1's mode.

    Returns:
        Tuple of (img1, img2) with matching modes
    """
    if target_mode is None:
        target_mode = img1.mode

    if img1.mode != target_mode:
        img1 = img1.convert(target_mode)

    if img2.mode != target_mode:
        img2 = img2.convert(target_mode)

    return img1, img2


def align_images(
    img1: Image.Image,
    img2: Image.Image
) -> Tuple[Image.Image, Image.Image]:
    """Align two images (size and mode).

    Args:
        img1: First image
        img2: Second image

    Returns:
        Aligned images
    """
    # First align size
    img1, img2 = ensure_same_size(img1, img2, resize_mode="fit")

    # Then align mode
    img1, img2 = ensure_same_mode(img1, img2)

    return img1, img2


def crop_to_bbox(
    image: Image.Image,
    bbox: Tuple[float, float, float, float]
) -> Image.Image:
    """Crop image to bounding box.

    Args:
        image: Source image
        bbox: Bounding box (x0, y0, x1, y1)

    Returns:
        Cropped image
    """
    # Ensure coordinates are within image bounds
    x0 = max(0, int(bbox[0]))
    y0 = max(0, int(bbox[1]))
    x1 = min(image.size[0], int(bbox[2]))
    y1 = min(image.size[1], int(bbox[3]))

    return image.crop((x0, y0, x1, y1))


def normalize_image(image: Image.Image) -> np.ndarray:
    """Normalize image to 0-1 float array.

    Args:
        image: PIL Image

    Returns:
        Normalized numpy array (0-1 float)
    """
    arr = np.array(image.convert('RGB'), dtype=np.float32)
    return arr / 255.0


def denormalize_image(arr: np.ndarray) -> Image.Image:
    """Convert normalized array back to PIL Image.

    Args:
        arr: Normalized array (0-1 float)

    Returns:
        PIL Image
    """
    arr_uint8 = (arr * 255).astype(np.uint8)
    return Image.fromarray(arr_uint8)


def compute_histogram(image: Image.Image, bins: int = 256) -> np.ndarray:
    """Compute color histogram for image.

    Args:
        image: PIL Image
        bins: Number of histogram bins per channel

    Returns:
        Histogram array (shape depends on image mode)
    """
    arr = np.array(image)

    if len(arr.shape) == 2:
        # Grayscale
        hist, _ = np.histogram(arr, bins=bins, range=(0, 256))
        return hist
    else:
        # Color - concatenate channel histograms
        hists = []
        for channel in range(arr.shape[2]):
            hist, _ = np.histogram(arr[:, :, channel], bins=bins, range=(0, 256))
            hists.append(hist)
        return np.concatenate(hists)


def apply_gaussian_blur(
    image: Image.Image,
    radius: float = 2.0
) -> Image.Image:
    """Apply Gaussian blur to image.

    Args:
        image: PIL Image
        radius: Blur radius

    Returns:
        Blurred image
    """
    return image.filter(ImageFilter.GaussianBlur(radius=radius))


def compute_gradient(image: Image.Image) -> Tuple[np.ndarray, np.ndarray]:
    """Compute image gradients (Sobel-like).

    Args:
        image: PIL Image (will be converted to grayscale)

    Returns:
        Tuple of (gradient_x, gradient_y) as numpy arrays
    """
    # Convert to grayscale
    gray = np.array(image.convert('L'), dtype=np.float32)

    # Compute gradients using numpy
    gradient_y = np.diff(gray, axis=0, prepend=gray[0:1, :])
    gradient_x = np.diff(gray, axis=1, prepend=gray[:, 0:1])

    return gradient_x, gradient_y


def compute_gradient_magnitude(image: Image.Image) -> np.ndarray:
    """Compute gradient magnitude.

    Args:
        image: PIL Image

    Returns:
        Gradient magnitude array
    """
    gx, gy = compute_gradient(image)
    magnitude = np.sqrt(gx ** 2 + gy ** 2)
    return magnitude


def threshold_image(
    image: Image.Image,
    threshold: int = 128,
    invert: bool = False
) -> Image.Image:
    """Apply threshold to image.

    Args:
        image: PIL Image (will be converted to grayscale)
        threshold: Threshold value (0-255)
        invert: Invert result

    Returns:
        Binary image
    """
    gray = image.convert('L')

    if invert:
        return gray.point(lambda x: 0 if x > threshold else 255)
    else:
        return gray.point(lambda x: 255 if x > threshold else 0)


def compute_image_statistics(image: Image.Image) -> dict:
    """Compute basic image statistics.

    Args:
        image: PIL Image

    Returns:
        Dictionary with statistics (mean, std, min, max per channel)
    """
    arr = np.array(image)

    if len(arr.shape) == 2:
        # Grayscale
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": int(np.min(arr)),
            "max": int(np.max(arr))
        }
    else:
        # Color
        stats = {}
        for i, channel in enumerate(['R', 'G', 'B'][:arr.shape[2]]):
            stats[channel] = {
                "mean": float(np.mean(arr[:, :, i])),
                "std": float(np.std(arr[:, :, i])),
                "min": int(np.min(arr[:, :, i])),
                "max": int(np.max(arr[:, :, i]))
            }
        return stats


def pad_to_size(
    image: Image.Image,
    target_size: Tuple[int, int],
    fill_color: Tuple[int, int, int] = (255, 255, 255)
) -> Image.Image:
    """Pad image to target size.

    Args:
        image: Source image
        target_size: Target (width, height)
        fill_color: Color for padding

    Returns:
        Padded image
    """
    if image.size == target_size:
        return image

    # Create new image with target size
    padded = Image.new('RGB', target_size, fill_color)

    # Paste original image centered
    x_offset = (target_size[0] - image.size[0]) // 2
    y_offset = (target_size[1] - image.size[1]) // 2

    padded.paste(image, (x_offset, y_offset))

    return padded


def scale_to_fit(
    image: Image.Image,
    max_size: Tuple[int, int],
    maintain_aspect: bool = True
) -> Image.Image:
    """Scale image to fit within max size.

    Args:
        image: Source image
        max_size: Maximum (width, height)
        maintain_aspect: Maintain aspect ratio

    Returns:
        Scaled image
    """
    if maintain_aspect:
        # Calculate scaling factor
        scale_w = max_size[0] / image.size[0]
        scale_h = max_size[1] / image.size[1]
        scale = min(scale_w, scale_h)

        new_size = (
            int(image.size[0] * scale),
            int(image.size[1] * scale)
        )
    else:
        new_size = max_size

    return image.resize(new_size, Image.Resampling.LANCZOS)
