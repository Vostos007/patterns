"""Utility functions for QA operations."""

import hashlib
from pathlib import Path
from typing import Optional, List, Tuple
from PIL import Image
import io

from kps.core import Asset


def calculate_hash(data: bytes) -> str:
    """
    Calculate SHA256 hash of binary data.

    Args:
        data: Binary data to hash

    Returns:
        Hex string of SHA256 hash
    """
    return hashlib.sha256(data).hexdigest()


def load_image(path: Path) -> Optional[Image.Image]:
    """
    Load image from file path.

    Args:
        path: Path to image file

    Returns:
        PIL Image or None if load fails
    """
    try:
        return Image.open(path)
    except Exception:
        return None


def bytes_to_image(data: bytes) -> Optional[Image.Image]:
    """
    Convert bytes to PIL Image.

    Args:
        data: Image binary data

    Returns:
        PIL Image or None if conversion fails
    """
    try:
        return Image.open(io.BytesIO(data))
    except Exception:
        return None


def image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """
    Convert PIL Image to bytes.

    Args:
        image: PIL Image
        format: Output format (PNG, JPEG, etc.)

    Returns:
        Image binary data
    """
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


def calculate_asset_area(asset: Asset) -> float:
    """
    Calculate asset area in square pixels.

    Args:
        asset: Asset to measure

    Returns:
        Area in square pixels
    """
    if asset.image_width and asset.image_height:
        return asset.image_width * asset.image_height
    return 0.0


def is_large_asset(asset: Asset, threshold: int = 500) -> bool:
    """
    Check if asset is large (exceeds threshold on any dimension).

    Args:
        asset: Asset to check
        threshold: Size threshold in pixels

    Returns:
        True if asset is large
    """
    if asset.image_width and asset.image_width > threshold:
        return True
    if asset.image_height and asset.image_height > threshold:
        return True
    return False


def is_prominent_asset(asset: Asset, area_threshold: int = 250000) -> bool:
    """
    Check if asset is prominent (large area).

    Args:
        asset: Asset to check
        area_threshold: Area threshold in square pixels

    Returns:
        True if asset is prominent
    """
    return calculate_asset_area(asset) > area_threshold


def extract_section_from_anchor(anchor_to: str) -> str:
    """
    Extract section name from anchor_to block ID.

    Args:
        anchor_to: Block ID like "paragraph.materials.001"

    Returns:
        Section name (e.g., "materials") or "unknown"
    """
    if not anchor_to:
        return "unknown"

    parts = anchor_to.split(".")
    if len(parts) >= 2:
        return parts[1]
    return "unknown"


def format_percentage(value: float, decimal_places: int = 1) -> str:
    """
    Format percentage value for display.

    Args:
        value: Percentage value (0-100)
        decimal_places: Number of decimal places

    Returns:
        Formatted string like "98.5%"
    """
    return f"{value:.{decimal_places}f}%"


def format_coverage_status(coverage: float) -> str:
    """
    Format coverage with color-coded status.

    Args:
        coverage: Coverage percentage

    Returns:
        Status string (EXCELLENT, GOOD, ACCEPTABLE, POOR)
    """
    if coverage >= 100.0:
        return "EXCELLENT"
    elif coverage >= 98.0:
        return "GOOD"
    elif coverage >= 95.0:
        return "ACCEPTABLE"
    elif coverage >= 90.0:
        return "POOR"
    else:
        return "CRITICAL"


def group_by_page(assets: List[Asset]) -> dict:
    """
    Group assets by page number.

    Args:
        assets: List of assets

    Returns:
        Dict mapping page_number -> list of assets
    """
    by_page = {}
    for asset in assets:
        if asset.page_number not in by_page:
            by_page[asset.page_number] = []
        by_page[asset.page_number].append(asset)
    return by_page


def group_by_type(assets: List[Asset]) -> dict:
    """
    Group assets by type.

    Args:
        assets: List of assets

    Returns:
        Dict mapping asset_type.value -> list of assets
    """
    by_type = {}
    for asset in assets:
        type_key = asset.asset_type.value
        if type_key not in by_type:
            by_type[type_key] = []
        by_type[type_key].append(asset)
    return by_type


def group_by_section(assets: List[Asset]) -> dict:
    """
    Group assets by section (extracted from anchor_to).

    Args:
        assets: List of assets

    Returns:
        Dict mapping section_name -> list of assets
    """
    by_section = {}
    for asset in assets:
        section = extract_section_from_anchor(asset.anchor_to)
        if section not in by_section:
            by_section[section] = []
        by_section[section].append(asset)
    return by_section


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if denominator is zero.

    Args:
        numerator: Numerator
        denominator: Denominator
        default: Default value if division by zero

    Returns:
        Result of division or default
    """
    if denominator == 0:
        return default
    return numerator / denominator


def truncate_list(items: List, max_items: int, ellipsis: bool = True) -> Tuple[List, bool]:
    """
    Truncate list to maximum number of items.

    Args:
        items: List to truncate
        max_items: Maximum number of items
        ellipsis: Whether there are more items

    Returns:
        Tuple of (truncated_list, was_truncated)
    """
    if len(items) <= max_items:
        return items, False
    return items[:max_items], True


def find_asset_by_id(assets: List[Asset], asset_id: str) -> Optional[Asset]:
    """
    Find asset by ID in list.

    Args:
        assets: List of assets
        asset_id: Asset ID to find

    Returns:
        Asset if found, None otherwise
    """
    for asset in assets:
        if asset.asset_id == asset_id:
            return asset
    return None


def find_assets_by_hash(assets: List[Asset], sha256: str) -> List[Asset]:
    """
    Find all assets with matching hash.

    Args:
        assets: List of assets
        sha256: SHA256 hash to match

    Returns:
        List of matching assets
    """
    return [a for a in assets if a.sha256 == sha256]


def asset_summary(asset: Asset) -> str:
    """
    Generate short summary string for asset.

    Args:
        asset: Asset to summarize

    Returns:
        Summary string like "img-abc123 (p3, 800x600, image)"
    """
    dimensions = ""
    if asset.image_width and asset.image_height:
        dimensions = f"{asset.image_width}x{asset.image_height}"

    return f"{asset.asset_id[:16]}... (p{asset.page_number}, {dimensions}, {asset.asset_type.value})"
