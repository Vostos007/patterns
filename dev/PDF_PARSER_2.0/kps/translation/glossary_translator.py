"""
Simple and fast glossary-driven translation with self-learning.

This module provides a streamlined translation system focused on:
- Fast glossary term matching
- Efficient translation with glossary context
- Translation memory and caching (самообучение)
- Few-shot learning from best examples
- Minimal overhead, maximum performance

Usage:
    translator = GlossaryTranslator(orchestrator, glossary)
    result = translator.translate(segments, target_lang="en")
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from .glossary.manager import GlossaryEntry, GlossaryManager
from .orchestrator import (
    BatchTranslationResult,
    TranslationOrchestrator,
    TranslationSegment,
)
from .translation_memory import TranslationMemory
from kps.core.placeholders import decode_placeholders

logger = logging.getLogger(__name__)


@dataclass
class TranslationResult:
    """Simple translation result."""

    source_language: str
    target_language: str
    segments: List[str]  # Translated segments
    terms_found: int  # Glossary terms found in source
    total_cost: float
    cached_segments: int = 0  # Сегменты из кэша
    new_term_suggestions: int = 0  # Предложения новых терминов


class GlossaryTranslator:
    """
    Fast and simple glossary-driven translator with self-learning.

    This translator:
    1. Checks cache for existing translations (fast!)
    2. Finds glossary terms in source text (exact matching)
    3. Uses few-shot examples from best previous translations
    4. Injects relevant glossary into translation prompt
    5. Translates with glossary context
    6. Saves to cache and learns from results (автоматически!)

    Self-learning features:
    - Translation memory: caches all translations for reuse
    - Few-shot learning: uses best examples in prompts
    - Auto-suggestions: proposes new glossary terms automatically
    - Quality improvement: learns from successful translations

    Example:
        >>> # With self-learning (recommended)
        >>> memory = TranslationMemory("data/translation_cache.json")
        >>> translator = GlossaryTranslator(orchestrator, glossary, memory=memory)
        >>> result = translator.translate(segments, target_lang="en")
        >>> print(f"Cached: {result.cached_segments}/{len(result.segments)}")
        >>> print(f"Suggested terms: {result.new_term_suggestions}")
        >>>
        >>> # Get suggestions for glossary
        >>> suggestions = translator.get_glossary_suggestions()
        >>> for s in suggestions:
        ...     print(f"{s.source_text} → {s.translated_text} (freq: {s.frequency})")
    """

    def __init__(
        self,
        orchestrator: TranslationOrchestrator,
        glossary_manager: GlossaryManager,
        max_glossary_terms: int = 100,
        memory: Optional[TranslationMemory] = None,
        enable_few_shot: bool = True,
        enable_auto_suggestions: bool = True,
        config: Optional[object] = None,  # PipelineConfig for RAG params
    ):
        """
        Initialize translator.

        Args:
            orchestrator: Translation orchestrator for API calls
            glossary_manager: Glossary manager for term lookups
            max_glossary_terms: Maximum terms to inject in prompt (default: 100)
            memory: Translation memory for caching and learning (optional)
            enable_few_shot: Use few-shot examples in prompts (default: True)
            enable_auto_suggestions: Auto-suggest new glossary terms (default: True)
            config: PipelineConfig with RAG parameters (optional)
        """
        self.orchestrator = orchestrator
        self.glossary = glossary_manager
        self.max_glossary_terms = max_glossary_terms
        self.memory = memory
        self.enable_few_shot = enable_few_shot
        self.enable_auto_suggestions = enable_auto_suggestions
        self.config = config

        # If the orchestrator already has a term validator, force strict enforcement.
        if getattr(self.orchestrator, "term_validator", None):
            self.orchestrator.strict_glossary = True

    def translate(
        self,
        segments: List[TranslationSegment],
        target_language: str,
        source_language: Optional[str] = None,
    ) -> TranslationResult:
        """
        Translate segments with glossary and self-learning.

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

        # Check cache for existing translations
        translated_segments = []
        segments_to_translate = []
        segment_indices = []  # Индексы сегментов для перевода
        cached_count = 0

        for i, segment in enumerate(segments):
            if self.memory:
                cached = self.memory.get_translation(
                    segment.text, source_language, target_language
                )
                if cached:
                    translated_segments.append(cached.translated_text)
                    cached_count += 1
                    continue

            # Нужно перевести
            translated_segments.append(None)  # Placeholder
            segments_to_translate.append(segment)
            segment_indices.append(i)

        # If all cached, return immediately
        if not segments_to_translate:
            return TranslationResult(
                source_language=source_language,
                target_language=target_language,
                segments=translated_segments,
                terms_found=0,
                total_cost=0.0,
                cached_segments=cached_count,
            )

        # Find all glossary terms in source text
        all_text = " ".join([s.text for s in segments_to_translate])
        term_keys = self._find_terms(all_text, source_language, target_language)

        # Get glossary entries for found terms
        glossary_entries = self._get_entries_for_keys(term_keys)

        # Limit to max terms (prioritize by frequency)
        if len(glossary_entries) > self.max_glossary_terms:
            # Count term frequency
            term_freq = {key: 0 for key in term_keys}
            for segment in segments_to_translate:
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

        # Add few-shot examples if enabled
        if self.memory and self.enable_few_shot:
            few_shot_examples = self.memory.get_few_shot_examples(
                source_language, target_language, limit=3
            )
            if few_shot_examples:
                glossary_context += "\n\nПримеры хороших переводов:\n"
                for source, target in few_shot_examples:
                    glossary_context += f"- {source} → {target}\n"

        # RAG INTEGRATION - Add semantic examples
        if (self.memory and hasattr(self.memory, 'get_rag_examples') and 
            segments_to_translate and 
            self.config and getattr(self.config, 'rag_enabled', True)):
            try:
                # Use config parameters or defaults
                rag_limit = getattr(self.config, 'rag_examples_limit', 3)
                min_similarity = getattr(self.config, 'rag_min_similarity', 0.75)
                
                # Use first segment for semantic search
                query_text = " ".join([s.text[:100] for s in segments_to_translate[:2]])
                
                rag_examples = self.memory.get_rag_examples(
                    query_text,
                    source_language,
                    target_language,
                    limit=rag_limit,
                    min_similarity=min_similarity
                )
                
                if rag_examples:
                    glossary_context += "\n\n# Контекстуально-релевантные примеры (RAG):\n"
                    for source, target, similarity in rag_examples:
                        glossary_context += f"- Сходство {similarity:.2f}: \"{source[:50]}...\" → \"{target[:50]}...\"\n"
                    logger.info(f"RAG examples: {len(rag_examples)} semantic matches found (threshold: {min_similarity:.2f})")
                
            except Exception as e:
                logger.warning(f"RAG lookup failed: {e}, continuing without examples")

        # Translate with glossary context
        batch_result = self.orchestrator.translate_batch(
            segments=segments_to_translate,
            target_languages=[target_language],
            glossary_context=glossary_context,
        )

        # Extract translated segments
        batch_output = batch_result.translations[target_language].segments

        decoded_batch: List[str] = []
        for segment, translation in zip(segments_to_translate, batch_output):
            decoded_batch.append(
                decode_placeholders(translation, segment.placeholders)
            )

        # Merge cached and new translations
        for idx, translation in zip(segment_indices, decoded_batch):
            translated_segments[idx] = translation

        # Save to memory
        new_suggestions = 0
        if self.memory:
            for segment, translation in zip(segments_to_translate, decoded_batch):
                if translation.strip() == segment.text.strip():
                    logger.warning(
                        "Skipping cache for %s because translation == source",
                        segment.segment_id,
                    )
                    continue
                # Найти термины для этого сегмента
                segment_terms = self._find_terms(
                    segment.text, source_language, target_language
                )

                # Сохранить в память
                self.memory.add_translation(
                    source_text=segment.text,
                    translated_text=translation,
                    source_lang=source_language,
                    target_lang=target_language,
                    glossary_terms=segment_terms,
                )

                # Автоматически предлагать новые термины
                if self.enable_auto_suggestions:
                    # Найти короткие фразы для предложения
                    words = segment.text.split()
                    for i in range(len(words)):
                        for j in range(i + 1, min(i + 4, len(words) + 1)):
                            phrase = " ".join(words[i:j])
                            # Пропустить если уже в глоссарии
                            if phrase.lower() not in [
                                getattr(e, source_language, "").lower()
                                for e in self.glossary.get_all_entries()
                            ]:
                                # Попробовать найти перевод этой фразы
                                self.memory.suggest_glossary_term(
                                    source_text=phrase,
                                    translated_text="",  # Will be filled by analysis
                                    source_lang=source_language,
                                    target_lang=target_language,
                                    context=segment.text[:50],
                                )
                                new_suggestions += 1

        return TranslationResult(
            source_language=source_language,
            target_language=target_language,
            segments=translated_segments,
            terms_found=len(term_keys),
            total_cost=batch_result.total_cost,
            cached_segments=cached_count,
            new_term_suggestions=new_suggestions,
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

    def get_glossary_suggestions(
        self, min_frequency: int = 3, min_confidence: float = 0.7
    ):
        """
        Получить предложения новых терминов для глоссария.

        Система автоматически отслеживает часто используемые фразы
        и предлагает добавить их в глоссарий.

        Args:
            min_frequency: Минимальная частота использования
            min_confidence: Минимальная уверенность

        Returns:
            Список SuggestedGlossaryTerm или пустой список если memory не включена
        """
        if not self.memory:
            return []

        return self.memory.get_glossary_suggestions(min_frequency, min_confidence)

    def get_statistics(self):
        """
        Получить статистику использования памяти переводов.

        Returns:
            Словарь со статистикой или None если memory не включена
        """
        if not self.memory:
            return None

        return self.memory.get_statistics()

    def save_memory(self):
        """Сохранить память переводов на диск."""
        if self.memory:
            self.memory.save()


__all__ = ["GlossaryTranslator", "TranslationResult"]
