"""
Simple and fast glossary-driven translation.

This module provides a streamlined translation system focused on:
- Fast glossary term matching
- Efficient translation with glossary context
- Minimal overhead, maximum performance

Usage:
    translator = GlossaryTranslator(orchestrator, glossary)
    result = translator.translate(segments, target_lang="en")
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from .glossary.manager import GlossaryEntry, GlossaryManager
from .orchestrator import (
    BatchTranslationResult,
    TranslationOrchestrator,
    TranslationSegment,
)


@dataclass
class TranslationResult:
    """Simple translation result."""

    source_language: str
    target_language: str
    segments: List[str]  # Translated segments
    terms_found: int  # Glossary terms found in source
    total_cost: float


class GlossaryTranslator:
    """
    Fast and simple glossary-driven translator.

    This translator:
    1. Finds glossary terms in source text (exact matching)
    2. Injects relevant glossary into translation prompt
    3. Translates with glossary context

    Example:
        >>> translator = GlossaryTranslator(orchestrator, glossary)
        >>> result = translator.translate(segments, target_lang="en")
        >>> print(f"Translated {len(result.segments)} segments")
        >>> print(f"Found {result.terms_found} glossary terms")
    """

    def __init__(
        self,
        orchestrator: TranslationOrchestrator,
        glossary_manager: GlossaryManager,
        max_glossary_terms: int = 100,
    ):
        """
        Initialize translator.

        Args:
            orchestrator: Translation orchestrator for API calls
            glossary_manager: Glossary manager for term lookups
            max_glossary_terms: Maximum terms to inject in prompt (default: 100)
        """
        self.orchestrator = orchestrator
        self.glossary = glossary_manager
        self.max_glossary_terms = max_glossary_terms

    def translate(
        self,
        segments: List[TranslationSegment],
        target_language: str,
        source_language: Optional[str] = None,
    ) -> TranslationResult:
        """
        Translate segments with glossary.

        Args:
            segments: Segments to translate
            target_language: Target language code (e.g., "en", "fr", "ru")
            source_language: Source language (auto-detected if None)

        Returns:
            TranslationResult with translated segments
        """
        # Detect source language if not provided
        if source_language is None:
            sample = " ".join([s.text for s in segments[:5]])
            source_language = self.orchestrator.detect_language(sample)

        # Find all glossary terms in source text
        all_text = " ".join([s.text for s in segments])
        term_keys = self._find_terms(all_text, source_language, target_language)

        # Get glossary entries for found terms
        glossary_entries = self._get_entries_for_keys(term_keys)

        # Limit to max terms (prioritize by frequency)
        if len(glossary_entries) > self.max_glossary_terms:
            # Count term frequency
            term_freq = {key: 0 for key in term_keys}
            for segment in segments:
                found = self._find_terms(segment.text, source_language, target_language)
                for key in found:
                    term_freq[key] = term_freq.get(key, 0) + 1

            # Sort by frequency and take top N
            sorted_entries = sorted(
                glossary_entries,
                key=lambda e: term_freq.get(e.key, 0),
                reverse=True,
            )
            glossary_entries = sorted_entries[: self.max_glossary_terms]

        # Build glossary context for prompt
        glossary_context = self.glossary.build_context_for_prompt(
            source_lang=source_language,
            target_lang=target_language,
            selected_entries=glossary_entries,
        )

        # Translate with glossary context
        batch_result = self.orchestrator.translate_batch(
            segments=segments,
            target_languages=[target_language],
            glossary_context=glossary_context,
        )

        # Extract translated segments
        translated_segments = batch_result.translations[
            target_language
        ].segments

        return TranslationResult(
            source_language=source_language,
            target_language=target_language,
            segments=translated_segments,
            terms_found=len(term_keys),
            total_cost=batch_result.total_cost,
        )

    def _find_terms(
        self, text: str, source_lang: str, target_lang: str
    ) -> List[str]:
        """
        Find glossary term keys in text.

        Uses simple and fast exact matching (case-insensitive).

        Args:
            text: Text to search
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            List of glossary entry keys found
        """
        found_keys = []
        text_lower = text.lower()

        # Search for each glossary entry
        for entry in self.glossary.get_all_entries():
            source_term = getattr(entry, source_lang, "")
            target_term = getattr(entry, target_lang, "")

            # Skip if no terms for this language pair
            if not source_term or not target_term:
                continue

            # Check if term appears in text (case-insensitive, word boundaries)
            term_lower = source_term.lower()
            pattern = r"\b" + re.escape(term_lower) + r"\b"

            if re.search(pattern, text_lower):
                found_keys.append(entry.key)

        return found_keys

    def _get_entries_for_keys(
        self, keys: List[str]
    ) -> List[GlossaryEntry]:
        """
        Get glossary entries for given keys.

        Args:
            keys: List of glossary entry keys

        Returns:
            List of glossary entries
        """
        entries = []
        key_set = set(keys)

        for entry in self.glossary.get_all_entries():
            if entry.key in key_set:
                entries.append(entry)

        return entries


__all__ = ["GlossaryTranslator", "TranslationResult"]
