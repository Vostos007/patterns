"""
Text normalization utilities.

Provides canonical text forms to reduce duplicate entries in database.
"""

import unicodedata
import re

# Regex patterns
_SPACES = re.compile(r"\s+")

# Apostrophe/quote normalization map
_APOS = {
    "'": "'",  # Right single quotation mark
    "'": "'",  # Left single quotation mark
    "´": "'",  # Acute accent
    "ʼ": "'",  # Modifier letter apostrophe
    """: '"',  # Left double quotation mark
    """: '"',  # Right double quotation mark
}


def canon(s: str) -> str:
    """
    Canonicalize text to reduce false duplicates.

    Applies:
    - NFKC normalization (canonical compatibility decomposition)
    - Apostrophe/quote normalization
    - Whitespace normalization (collapse multiple spaces)
    - Trim leading/trailing whitespace

    Args:
        s: Input text

    Returns:
        Canonical form

    Example:
        >>> canon("Hello   world")
        'Hello world'
        >>> canon("café")  # é -> e + combining accent -> é (composed)
        'café'
        >>> canon("'test'")
        "'test'"
    """
    # Unicode normalization (NFKC: compatibility + canonical composition)
    s = unicodedata.normalize("NFKC", s)

    # Normalize apostrophes and quotes
    for old, new in _APOS.items():
        s = s.replace(old, new)

    # Collapse whitespace
    s = _SPACES.sub(" ", s).strip()

    return s


def canon_lower(s: str) -> str:
    """
    Canonicalize and lowercase for case-insensitive comparison.

    Args:
        s: Input text

    Returns:
        Canonical lowercase form
    """
    return canon(s).lower()


__all__ = ["canon", "canon_lower"]
