"""
Marker injection for asset anchoring in KPS v2.0.

After assets are anchored to blocks, this module injects [[asset_id]] markers
into the ContentBlock.content text to ensure assets stay with their text during
translation.

Strategy:
- PARAGRAPH blocks: Inject at start of text (before first sentence)
- HEADING blocks: Inject after heading text
- CAPTION blocks: Inject before caption text (asset first, then caption)
- TABLE blocks: Inject at start of table
- LIST blocks: Inject at start of list

Markers are placed on their own line for proper translation handling.
Multiple assets anchored to same block are ordered by y-coordinate (top to bottom).
"""

import re
from typing import List, Set, Tuple

from ..core.assets import Asset, AssetLedger
from ..core.document import BlockType, ContentBlock, KPSDocument
from ..core.placeholders import ASSET_MARKER_PATTERN


class MarkerInjectionError(Exception):
    """Raised when marker injection fails validation."""

    pass


def format_marker(asset_id: str) -> str:
    """
    Format an asset marker with newline.

    Args:
        asset_id: Asset identifier (e.g., "img-abc123-p3-occ1")

    Returns:
        Formatted marker: "[[asset_id]]\n"
    """
    return f"[[{asset_id}]]\n"


def validate_marker(marker: str) -> bool:
    """
    Validate that a marker matches the expected pattern.

    Args:
        marker: Marker string to validate (e.g., "[[asset_id]]")

    Returns:
        True if valid, False otherwise
    """
    return bool(ASSET_MARKER_PATTERN.match(marker))


def find_injection_position(block: ContentBlock) -> int:
    """
    Find the character index where marker should be injected.

    Strategy by block type:
    - PARAGRAPH: Start of text (index 0)
    - HEADING: After heading text (end of content)
    - TABLE: Start of table (index 0)
    - LIST: Start of list (index 0)
    - FIGURE: Not applicable (figures don't contain text)

    Args:
        block: ContentBlock to analyze

    Returns:
        Character index for insertion
    """
    if block.block_type == BlockType.PARAGRAPH:
        # Inject at start, before first sentence
        return 0

    elif block.block_type == BlockType.HEADING:
        # Inject after heading text
        # Ensure we append with newline if not already present
        content = block.content.rstrip()
        return len(content) + 1  # After heading, with newline

    elif block.block_type == BlockType.TABLE:
        # Inject at start of table
        return 0

    elif block.block_type == BlockType.LIST:
        # Inject at start of list
        return 0

    elif block.block_type == BlockType.FIGURE:
        # Figure blocks don't have text content
        # Marker replaces entire content
        return 0

    else:
        # Default: start of content
        return 0


def extract_existing_markers(content: str) -> Set[str]:
    """
    Extract all existing [[asset_id]] markers from content.

    Args:
        content: Text content to scan

    Returns:
        Set of asset IDs found in markers
    """
    markers = set()
    for match in ASSET_MARKER_PATTERN.finditer(content):
        asset_id = match.group(1)
        markers.add(asset_id)
    return markers


def inject_markers_into_block(
    block: ContentBlock, assets: List[Asset]
) -> ContentBlock:
    """
    Inject markers for multiple assets into a single block.

    Assets are ordered by y-coordinate (top to bottom on page).
    Markers are placed at strategic position based on block type.

    Args:
        block: ContentBlock to modify
        assets: List of assets anchored to this block (ordered)

    Returns:
        Modified ContentBlock with markers injected
    """
    if not assets:
        return block

    # Sort assets by y-coordinate (top to bottom)
    # Lower y0 = higher on page (PDF coordinates)
    sorted_assets = sorted(assets, key=lambda a: a.bbox.y0)

    # Check for existing markers
    existing_markers = extract_existing_markers(block.content)

    # Filter out assets that already have markers
    assets_to_inject = [
        asset for asset in sorted_assets if asset.asset_id not in existing_markers
    ]

    if not assets_to_inject:
        # All markers already present
        return block

    # Build marker block
    marker_text = ""
    for asset in assets_to_inject:
        marker = format_marker(asset.asset_id)

        # Validate marker format
        marker_stripped = marker.rstrip("\n")
        if not validate_marker(marker_stripped):
            raise MarkerInjectionError(
                f"Invalid marker format for asset {asset.asset_id}: {marker_stripped}"
            )

        marker_text += marker

    # Find injection position
    injection_pos = find_injection_position(block)

    # Handle different block types
    if block.block_type == BlockType.HEADING:
        # For headings: append after heading text with newline
        content = block.content.rstrip()
        if content:
            # Ensure newline after heading
            block.content = content + "\n" + marker_text
        else:
            block.content = marker_text

    elif block.block_type == BlockType.FIGURE:
        # For figure blocks: marker replaces content
        block.content = marker_text.rstrip("\n")

    else:
        # For PARAGRAPH, TABLE, LIST: inject at start
        if injection_pos == 0:
            block.content = marker_text + block.content
        else:
            # Insert at specific position
            block.content = (
                block.content[:injection_pos]
                + marker_text
                + block.content[injection_pos:]
            )

    return block


def inject_markers(document: KPSDocument, ledger: AssetLedger) -> KPSDocument:
    """
    Inject [[asset_id]] markers into all blocks with anchored assets.

    This is the main entry point for marker injection phase.

    Process:
    1. Group assets by anchor_to block ID
    2. For each block with assets, inject markers
    3. Validate: every anchored asset has exactly one marker
    4. Validate: no duplicate markers
    5. Validate: all markers are valid format

    Args:
        document: KPSDocument with content blocks
        ledger: AssetLedger with anchored assets (anchor_to field set)

    Returns:
        Modified KPSDocument with markers injected

    Raises:
        MarkerInjectionError: If validation fails
    """
    # Group assets by anchor_to block ID
    assets_by_block = {}
    for asset in ledger.assets:
        if not asset.anchor_to:
            continue  # Skip unanchored assets

        if asset.anchor_to not in assets_by_block:
            assets_by_block[asset.anchor_to] = []
        assets_by_block[asset.anchor_to].append(asset)

    # Track injected markers for validation
    injected_markers: Set[str] = set()

    # Inject markers into each block
    for section in document.sections:
        for i, block in enumerate(section.blocks):
            if block.block_id in assets_by_block:
                assets = assets_by_block[block.block_id]

                # Inject markers
                modified_block = inject_markers_into_block(block, assets)
                section.blocks[i] = modified_block

                # Track injected markers
                for asset in assets:
                    injected_markers.add(asset.asset_id)

    # Validation: Count all markers in document
    all_markers_in_document = set()
    for section in document.sections:
        for block in section.blocks:
            markers = extract_existing_markers(block.content)

            # Check for duplicates
            duplicates = all_markers_in_document.intersection(markers)
            if duplicates:
                raise MarkerInjectionError(
                    f"Duplicate markers found: {duplicates}"
                )

            all_markers_in_document.update(markers)

    # Validation: Every anchored asset must have exactly one marker
    anchored_asset_ids = {
        asset.asset_id for asset in ledger.assets if asset.anchor_to
    }

    missing_markers = anchored_asset_ids - all_markers_in_document
    if missing_markers:
        raise MarkerInjectionError(
            f"Assets missing markers: {missing_markers}"
        )

    extra_markers = all_markers_in_document - anchored_asset_ids
    if extra_markers:
        raise MarkerInjectionError(
            f"Unknown markers found (no matching anchored asset): {extra_markers}"
        )

    return document


def count_markers(document: KPSDocument) -> dict:
    """
    Count markers in document for debugging/validation.

    Args:
        document: KPSDocument to analyze

    Returns:
        Dict with marker statistics:
        - total_markers: Total number of markers
        - markers_by_block: Dict of block_id -> list of asset_ids
        - markers_by_section: Dict of section_type -> count
    """
    stats = {
        "total_markers": 0,
        "markers_by_block": {},
        "markers_by_section": {},
    }

    for section in document.sections:
        section_count = 0

        for block in section.blocks:
            markers = extract_existing_markers(block.content)

            if markers:
                stats["markers_by_block"][block.block_id] = list(markers)
                section_count += len(markers)

        if section_count > 0:
            stats["markers_by_section"][section.section_type.value] = section_count

        stats["total_markers"] += section_count

    return stats


__all__ = [
    "inject_markers",
    "inject_markers_into_block",
    "find_injection_position",
    "format_marker",
    "validate_marker",
    "extract_existing_markers",
    "count_markers",
    "MarkerInjectionError",
]
