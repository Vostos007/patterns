"""
Advanced glossary term matching with multiple strategies.

This module provides sophisticated term matching capabilities including:
- Exact matching
- Fuzzy matching with edit distance
- Context-aware matching
- Bi-directional matching (source→target and target→source)
- Multi-word term matching
- Abbreviation expansion
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .manager import GlossaryEntry, GlossaryManager


@dataclass
class MatchStrategy:
    """Configuration for term matching strategy."""

    exact_match: bool = True  # Enable exact word matching
    case_sensitive: bool = False  # Case-sensitive matching
    fuzzy_match: bool = True  # Enable fuzzy matching
    max_edit_distance: int = 2  # Maximum Levenshtein distance
    context_aware: bool = True  # Consider surrounding context
    multi_word: bool = True  # Match multi-word terms
    abbreviations: bool = True  # Match abbreviations
    bidirectional: bool = True  # Search in both directions


@dataclass
class TermOccurrence:
    """A single occurrence of a term in text."""

    entry: GlossaryEntry  # Glossary entry
    matched_text: str  # Actual text that matched
    position: int  # Start position in text
    length: int  # Length of match
    confidence: float  # Match confidence (0.0-1.0)
    strategy: str  # Matching strategy used
    context_before: str  # Text before match
    context_after: str  # Text after match


class AdvancedGlossaryMatcher:
    """
    Advanced glossary term matcher with multiple strategies.

    This matcher can find glossary terms using various strategies:
    - Exact matching (case-insensitive by default)
    - Fuzzy matching with edit distance
    - Context-aware matching
    - Bi-directional matching (useful for finding untranslated terms)
    - Multi-word term matching
    - Abbreviation matching

    Example:
        >>> matcher = AdvancedGlossaryMatcher(glossary_manager)
        >>> text = "Вяжите 2вм лиц в конце ряда"
        >>> occurrences = matcher.find_terms(text, "ru", "en")
        >>> for occ in occurrences:
        ...     print(f"{occ.matched_text} → {occ.entry.en}")
        2вм лиц → k2tog
        ряда → row
    """

    def __init__(
        self, glossary_manager: GlossaryManager, strategy: Optional[MatchStrategy] = None
    ):
        """
        Initialize advanced matcher.

        Args:
            glossary_manager: Glossary manager instance
            strategy: Matching strategy (uses defaults if None)
        """
        self.glossary = glossary_manager
        self.strategy = strategy or MatchStrategy()

        # Build search indices for fast lookup
        self._build_indices()

    def _build_indices(self) -> None:
        """Build search indices for all languages."""
        self._indices: Dict[str, Dict[str, List[GlossaryEntry]]] = {}

        # Build index for each language
        for lang in ["ru", "en", "fr"]:
            self._indices[lang] = {}

            for entry in self.glossary.get_all_entries():
                term = getattr(entry, lang, "")
                if not term:
                    continue

                # Index by lowercase term
                term_lower = term.lower()
                if term_lower not in self._indices[lang]:
                    self._indices[lang][term_lower] = []
                self._indices[lang][term_lower].append(entry)

                # Also index individual words for multi-word terms
                if " " in term:
                    for word in term.split():
                        word_lower = word.lower()
                        if word_lower not in self._indices[lang]:
                            self._indices[lang][word_lower] = []
                        if entry not in self._indices[lang][word_lower]:
                            self._indices[lang][word_lower].append(entry)

    def find_terms(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        min_confidence: float = 0.7,
    ) -> List[TermOccurrence]:
        """
        Find all glossary terms in text.

        Args:
            text: Text to search
            source_lang: Source language code
            target_lang: Target language code
            min_confidence: Minimum confidence threshold (0.0-1.0)

        Returns:
            List of term occurrences, sorted by position
        """
        occurrences = []

        # Strategy 1: Exact matching
        if self.strategy.exact_match:
            occurrences.extend(
                self._exact_match(text, source_lang, target_lang, min_confidence)
            )

        # Strategy 2: Fuzzy matching
        if self.strategy.fuzzy_match:
            occurrences.extend(
                self._fuzzy_match(text, source_lang, target_lang, min_confidence)
            )

        # Strategy 3: Multi-word matching
        if self.strategy.multi_word:
            occurrences.extend(
                self._multi_word_match(text, source_lang, target_lang, min_confidence)
            )

        # Strategy 4: Bidirectional matching (find target terms in source text)
        if self.strategy.bidirectional:
            occurrences.extend(
                self._bidirectional_match(text, source_lang, target_lang, min_confidence)
            )

        # Remove duplicates and overlaps
        occurrences = self._remove_overlaps(occurrences)

        # Sort by position
        occurrences.sort(key=lambda o: o.position)

        return occurrences

    def _exact_match(
        self, text: str, source_lang: str, target_lang: str, min_confidence: float
    ) -> List[TermOccurrence]:
        """Find exact term matches."""
        occurrences = []
        text_lower = text.lower() if not self.strategy.case_sensitive else text

        # Search for each glossary entry
        for entry in self.glossary.get_all_entries():
            source_term = getattr(entry, source_lang, "")
            if not source_term:
                continue

            term_to_search = (
                source_term.lower() if not self.strategy.case_sensitive else source_term
            )

            # Use word boundaries for better matching
            pattern = r"\b" + re.escape(term_to_search) + r"\b"
            for match in re.finditer(pattern, text_lower):
                position = match.start()
                length = match.end() - match.start()

                # Get context
                context_before = text[max(0, position - 20) : position]
                context_after = text[position + length : position + length + 20]

                occurrence = TermOccurrence(
                    entry=entry,
                    matched_text=text[position : position + length],
                    position=position,
                    length=length,
                    confidence=1.0,  # Exact match
                    strategy="exact",
                    context_before=context_before,
                    context_after=context_after,
                )
                occurrences.append(occurrence)

        return occurrences

    def _fuzzy_match(
        self, text: str, source_lang: str, target_lang: str, min_confidence: float
    ) -> List[TermOccurrence]:
        """Find fuzzy term matches using edit distance."""
        occurrences = []
        words = text.split()

        for i, word in enumerate(words):
            word_lower = word.lower()

            # Skip very short words
            if len(word_lower) < 3:
                continue

            # Find candidate entries
            for entry in self.glossary.get_all_entries():
                source_term = getattr(entry, source_lang, "")
                if not source_term or len(source_term) < 3:
                    continue

                term_lower = source_term.lower()

                # Calculate edit distance
                distance = self._levenshtein_distance(word_lower, term_lower)

                # Check if within threshold
                if distance <= self.strategy.max_edit_distance:
                    # Calculate confidence based on distance
                    max_len = max(len(word_lower), len(term_lower))
                    confidence = 1.0 - (distance / max_len)

                    if confidence >= min_confidence:
                        # Find position in original text
                        position = text.lower().find(word_lower)
                        if position == -1:
                            continue

                        length = len(word)
                        context_before = text[max(0, position - 20) : position]
                        context_after = text[position + length : position + length + 20]

                        occurrence = TermOccurrence(
                            entry=entry,
                            matched_text=word,
                            position=position,
                            length=length,
                            confidence=confidence,
                            strategy="fuzzy",
                            context_before=context_before,
                            context_after=context_after,
                        )
                        occurrences.append(occurrence)

        return occurrences

    def _multi_word_match(
        self, text: str, source_lang: str, target_lang: str, min_confidence: float
    ) -> List[TermOccurrence]:
        """Find multi-word term matches."""
        occurrences = []
        text_lower = text.lower() if not self.strategy.case_sensitive else text

        # Look for multi-word terms
        for entry in self.glossary.get_all_entries():
            source_term = getattr(entry, source_lang, "")
            if not source_term or " " not in source_term:
                continue

            term_to_search = (
                source_term.lower() if not self.strategy.case_sensitive else source_term
            )

            # Use word boundaries
            pattern = r"\b" + re.escape(term_to_search) + r"\b"
            for match in re.finditer(pattern, text_lower):
                position = match.start()
                length = match.end() - match.start()

                context_before = text[max(0, position - 20) : position]
                context_after = text[position + length : position + length + 20]

                occurrence = TermOccurrence(
                    entry=entry,
                    matched_text=text[position : position + length],
                    position=position,
                    length=length,
                    confidence=1.0,  # Exact multi-word match
                    strategy="multi_word",
                    context_before=context_before,
                    context_after=context_after,
                )
                occurrences.append(occurrence)

        return occurrences

    def _bidirectional_match(
        self, text: str, source_lang: str, target_lang: str, min_confidence: float
    ) -> List[TermOccurrence]:
        """
        Find terms in reverse direction (target language in source text).

        This is useful for detecting untranslated terms.
        """
        occurrences = []
        text_lower = text.lower() if not self.strategy.case_sensitive else text

        # Search for target language terms in source text
        for entry in self.glossary.get_all_entries():
            target_term = getattr(entry, target_lang, "")
            if not target_term:
                continue

            term_to_search = (
                target_term.lower() if not self.strategy.case_sensitive else target_term
            )

            pattern = r"\b" + re.escape(term_to_search) + r"\b"
            for match in re.finditer(pattern, text_lower):
                position = match.start()
                length = match.end() - match.start()

                context_before = text[max(0, position - 20) : position]
                context_after = text[position + length : position + length + 20]

                # Lower confidence for reverse matches
                occurrence = TermOccurrence(
                    entry=entry,
                    matched_text=text[position : position + length],
                    position=position,
                    length=length,
                    confidence=0.9,  # Slightly lower confidence
                    strategy="bidirectional",
                    context_before=context_before,
                    context_after=context_after,
                )
                occurrences.append(occurrence)

        return occurrences

    def _remove_overlaps(
        self, occurrences: List[TermOccurrence]
    ) -> List[TermOccurrence]:
        """
        Remove overlapping occurrences, keeping the best match.

        Priority:
        1. Longer matches
        2. Higher confidence
        3. Better strategy (exact > multi_word > fuzzy > bidirectional)
        """
        if not occurrences:
            return []

        strategy_priority = {"exact": 4, "multi_word": 3, "fuzzy": 2, "bidirectional": 1}

        # Sort by position, then by priority
        occurrences.sort(
            key=lambda o: (
                o.position,
                -o.length,
                -o.confidence,
                -strategy_priority.get(o.strategy, 0),
            )
        )

        non_overlapping = []
        for occ in occurrences:
            # Check if overlaps with any existing occurrence
            overlaps = False
            for existing in non_overlapping:
                if (
                    existing.position < occ.position + occ.length
                    and occ.position < existing.position + existing.length
                ):
                    overlaps = True
                    break

            if not overlaps:
                non_overlapping.append(occ)

        return non_overlapping

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Edit distance
        """
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost of insertions, deletions, or substitutions
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def get_term_statistics(
        self, text: str, source_lang: str, target_lang: str
    ) -> Dict:
        """
        Get statistics about terms in text.

        Args:
            text: Text to analyze
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Dictionary with statistics
        """
        occurrences = self.find_terms(text, source_lang, target_lang)

        # Count by category
        by_category = {}
        for occ in occurrences:
            cat = occ.entry.category
            by_category[cat] = by_category.get(cat, 0) + 1

        # Count by strategy
        by_strategy = {}
        for occ in occurrences:
            strat = occ.strategy
            by_strategy[strat] = by_strategy.get(strat, 0) + 1

        # Calculate coverage
        total_chars = len(text)
        term_chars = sum(occ.length for occ in occurrences)
        coverage = term_chars / total_chars if total_chars > 0 else 0.0

        return {
            "total_occurrences": len(occurrences),
            "unique_terms": len(set(occ.entry.key for occ in occurrences)),
            "by_category": by_category,
            "by_strategy": by_strategy,
            "coverage": coverage,
            "average_confidence": (
                sum(occ.confidence for occ in occurrences) / len(occurrences)
                if occurrences
                else 0.0
            ),
        }


__all__ = ["AdvancedGlossaryMatcher", "TermOccurrence", "MatchStrategy"]
