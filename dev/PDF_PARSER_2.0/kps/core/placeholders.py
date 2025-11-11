"""Placeholder encoding and decoding utilities.

The previous draft of this module consisted of a few loosely defined functions
and even missed the opening module docstring marker, making the entire package
fail to import.  This refactor introduces a focused implementation with clear
semantics and ample inline documentation so downstream code – primarily the
segmenter and the translation pipeline – can depend on deterministic
behaviour.

Highlights of the refactor:

* Deterministic placeholder identifiers with predictable prefixes.
* Support for the ``[[asset_id]]`` markers used by the anchoring subsystem.
* Reusable compiled regular expressions for both encoding and decoding to
  avoid recompilation overhead when processing hundreds of segments.
* Helpful exceptions when collisions are detected while merging placeholder
  mappings coming from different segmentation passes.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, Tuple

# ---------------------------------------------------------------------------
# Regular expressions and templates
# ---------------------------------------------------------------------------

PLACEHOLDER_TEMPLATE = '<ph id="{id}" />'

_STANDARD_TOKEN_PATTERN = re.compile(
    r"("  # group start
    r"https?://[^\s<>\"]+"  # URLs
    r"|"
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"  # email addresses
    r"|"
    r"\b\d[\d,.]*\b"  # numbers with separators
    r")"
)

_ASSET_MARKER_PATTERN = re.compile(r"\[\[([a-z0-9\-_]+)\]\]", re.IGNORECASE)

_PLACEHOLDER_TOKEN_PATTERN = re.compile(
    r'<ph\s+id="(?P<id>[A-Z0-9_\-]+)"\s*/>'
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def encode_placeholders(text: str, *, start_index: int = 1) -> Tuple[str, Dict[str, str]]:
    """Return ``text`` with fragile tokens replaced by placeholders.

    The function processes asset markers first so they keep their dedicated
    ``ASSET_`` prefix.  Afterwards general URLs, email addresses and numbers are
    assigned sequential ``PH###`` identifiers.
    """

    if not text:
        return text, {}

    counter = start_index
    mapping: Dict[str, str] = {}

    def _replace_asset(match: re.Match[str]) -> str:
        nonlocal counter
        token = match.group(0)
        asset_id = match.group(1).upper()
        placeholder_id = f"ASSET_{asset_id}"
        mapping[placeholder_id] = token
        counter += 1
        return PLACEHOLDER_TEMPLATE.format(id=placeholder_id)

    encoded = _ASSET_MARKER_PATTERN.sub(_replace_asset, text)

    def _replace_standard(match: re.Match[str]) -> str:
        nonlocal counter
        token = match.group(0)
        placeholder_id = f"PH{counter:03d}"
        mapping[placeholder_id] = token
        counter += 1
        return PLACEHOLDER_TEMPLATE.format(id=placeholder_id)

    encoded = _STANDARD_TOKEN_PATTERN.sub(_replace_standard, encoded)

    return encoded, mapping


def decode_placeholders(text: str, mapping: Dict[str, str]) -> str:
    """Restore previously encoded placeholders back into ``text``."""

    if not mapping or "<ph" not in text:
        return text

    def _replace(match: re.Match[str]) -> str:
        placeholder_id = match.group("id")
        return mapping.get(placeholder_id, match.group(0))

    return _PLACEHOLDER_TOKEN_PATTERN.sub(_replace, text)


def merge_placeholder_mappings(mappings: Iterable[Dict[str, str]]) -> Dict[str, str]:
    """Merge multiple placeholder dictionaries and guard against collisions."""

    merged: Dict[str, str] = {}
    for mapping in mappings:
        for key, value in mapping.items():
            if key in merged and merged[key] != value:
                raise ValueError(
                    f"Placeholder collision for '{key}': '{merged[key]}' != '{value}'"
                )
            merged[key] = value
    return merged


__all__ = [
    "PLACEHOLDER_TEMPLATE",
    "encode_placeholders",
    "decode_placeholders",
    "merge_placeholder_mappings",
]

