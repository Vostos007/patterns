"""
Placeholder encoding utilities for protecting fragile tokens during translation.

Enhanced from PDF_parser with [[asset_id]] marker support for KPS v2.0.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, Tuple

# Original placeholder pattern for URLs, emails, numbers
PLACEHOLDER_PATTERN = re.compile(
    r"("  # start capture group
    r"https?://[^\s<>\"]+"  # URLs
    r"|"  # or
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"  # emails
    r"|"  # or
    r"\b\d+[\d,.]*\b"  # numbers with optional separators
    r")"
)

# NEW: Asset marker pattern for [[asset_id]]
ASSET_MARKER_PATTERN = re.compile(r"\[\[([a-z0-9\-_]+)\]\]")

PLACEHOLDER_TEMPLATE = '<ph id="{id}" />'


def encode_placeholders(text: str, *, start_index: int = 1) -> Tuple[str, Dict[str, str]]:
    """
    Replace fragile tokens with deterministic placeholders.

    Encodes:
    - URLs (http://..., https://...)
    - Email addresses (user@example.com)
    - Numbers with separators (123,456.78)
    - [[asset_id]] markers (NEW for KPS v2.0)

    Returns:
        Tuple of (encoded_text, mapping) where mapping is {placeholder_id: original_value}
    """
    mapping: Dict[str, str] = {}
    if not text:
        return text, mapping

    counter = start_index

    # First, encode asset markers [[asset_id]]
    def _asset_replacement(match: re.Match[str]) -> str:
        nonlocal counter
        marker = match.group(0)  # Full [[asset_id]]
        asset_id = match.group(1)  # Just asset_id
        placeholder_id = f"ASSET_{asset_id.upper()}"
        mapping[placeholder_id] = marker
        counter += 1
        return PLACEHOLDER_TEMPLATE.format(id=placeholder_id)

    encoded = ASSET_MARKER_PATTERN.sub(_asset_replacement, text)

    # Then, encode URLs/emails/numbers
    def _standard_replacement(match: re.Match[str]) -> str:
        nonlocal counter
        token = match.group(0)
        placeholder_id = f"PH{counter:03d}"
        mapping[placeholder_id] = token
        counter += 1
        return PLACEHOLDER_TEMPLATE.format(id=placeholder_id)

    encoded = PLACEHOLDER_PATTERN.sub(_standard_replacement, encoded)

    return encoded, mapping


def decode_placeholders(text: str, mapping: Dict[str, str]) -> str:
    """
    Restore placeholders back to their original values.

    Handles both standard placeholders (PH###) and asset markers (ASSET_*).
    """
    if not mapping or PLACEHOLDER_TEMPLATE.split("{id}")[0] not in text:
        return text

    def _replacement(match: re.Match[str]) -> str:
        placeholder_id = match.group("id")
        return mapping.get(placeholder_id, match.group(0))

    # Pattern matches both PH### and ASSET_*
    pattern = re.compile(r'<ph\s+id="(?P<id>(?:PH\d{3}|ASSET_[A-Z0-9\-_]+))"\s*/>')
    return pattern.sub(_replacement, text)


def merge_placeholder_mappings(mappings: Iterable[Dict[str, str]]) -> Dict[str, str]:
    """Merge multiple placeholder mappings ensuring no collisions."""
    merged: Dict[str, str] = {}
    for mapping in mappings:
        for key, value in mapping.items():
            if key in merged and merged[key] != value:
                raise ValueError(f"Placeholder id collision for {key}: {merged[key]} != {value}")
            merged[key] = value
    return merged


__all__ = [
    "encode_placeholders",
    "decode_placeholders",
    "merge_placeholder_mappings",
    "ASSET_MARKER_PATTERN",
]
