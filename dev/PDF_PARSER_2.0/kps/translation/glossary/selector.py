"""
Smart glossary term selection with scoring algorithm.

Enhanced from PDF_parser with multi-language support for KPS v2.0.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple


def select_glossary_terms(
    terms: Sequence[str],
    glossary_entries: List[Dict],
    source_lang: str = "ru",
    max_terms: int = 50,
) -> List[Dict]:
    """
    Select relevant glossary entries based on text content.

    Scoring algorithm:
    - Exact match: score 3
    - Prefix match: score 2
    - Substring match (≥4 chars): score 1

    Args:
        terms: List of terms/words found in source text
        glossary_entries: Full glossary entry list
        source_lang: Source language code (e.g., "ru")
        max_terms: Maximum entries to return

    Returns:
        List of selected glossary entries, sorted by relevance
    """
    if max_terms <= 0 or not glossary_entries or not terms:
        return []

    normalized_terms = [term.lower() for term in terms if term]
    if not normalized_terms:
        return []

    # Score each glossary entry
    candidates: List[Tuple[int, int, Dict]] = []
    for index, entry in enumerate(glossary_entries):
        source_value = str(entry.get(source_lang, ""))
        if not source_value:
            continue

        source_lower = source_value.lower()
        best_score = 0

        for term in normalized_terms:
            if source_lower == term:
                best_score = max(best_score, 3)  # Exact match
            elif source_lower.startswith(term) or term.startswith(source_lower):
                best_score = max(best_score, 2)  # Prefix match
            elif term in source_lower and len(term) >= 4:
                best_score = max(best_score, 1)  # Substring match

        if best_score:
            candidates.append((best_score, index, entry))

    if not candidates:
        return []

    # Prioritize high-score matches
    high_priority = sorted(
        (item for item in candidates if item[0] > 1),
        key=lambda item: (-item[0], item[1]),  # Score desc, then index
    )
    low_priority = sorted(
        (item for item in candidates if item[0] == 1),
        key=lambda item: item[1],
    )

    # Select entries without duplicates
    selected: List[Dict] = []
    seen_sources: set[str] = set()

    def _consume(sequence: List[Tuple[int, int, Dict]]) -> None:
        for _, _, entry in sequence:
            source_value = str(entry.get(source_lang, ""))
            if source_value in seen_sources:
                continue
            selected.append(entry)
            seen_sources.add(source_value)
            if len(selected) >= max_terms:
                return

    # First consume high-priority matches
    _consume(high_priority)

    # Then low-priority if space remains
    if len(selected) < max_terms:
        _consume(low_priority)

    return selected


def extract_protected_tokens(glossary_entries: List[Dict]) -> List[str]:
    """
    Extract protected tokens from glossary entries.

    Protected tokens are terms that should NOT be translated
    (e.g., brand names, technical abbreviations).

    Args:
        glossary_entries: Glossary entries

    Returns:
        List of protected tokens
    """
    tokens = []
    for entry in glossary_entries:
        protected = entry.get("protected_tokens", []) or []
        tokens.extend(protected)
    return tokens


__all__ = ["select_glossary_terms", "extract_protected_tokens"]
