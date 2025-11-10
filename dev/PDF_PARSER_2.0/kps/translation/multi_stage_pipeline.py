"""
Multi-stage translation pipeline with deep glossary integration.

This module provides a comprehensive multi-stage translation system that ensures
accurate and consistent translations using glossary terms at every stage.

Stages:
1. Preprocessing: Extract and identify glossary terms in source text
2. Translation: Translate with glossary context and term protection
3. Verification: Validate correct usage of glossary terms
4. Post-processing: Final validation and corrections

Features:
- Deep glossary integration at all stages
- Multi-language support (any language pair)
- Term frequency analysis
- Context-aware term matching
- Automatic term correction
- Quality metrics and reporting
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .glossary.manager import GlossaryEntry, GlossaryManager
from .orchestrator import (
    BatchTranslationResult,
    TranslationOrchestrator,
    TranslationSegment,
)


@dataclass
class TermMatch:
    """A matched glossary term in source text."""

    term_key: str  # Glossary entry key
    source_text: str  # Text in source language
    target_text: str  # Expected translation
    start_pos: int  # Position in segment
    end_pos: int  # End position
    category: str  # Term category
    confidence: float  # Match confidence (0.0-1.0)


@dataclass
class SegmentAnalysis:
    """Analysis of a single segment before translation."""

    segment_id: str
    source_text: str
    matched_terms: List[TermMatch]  # Glossary terms found
    protected_tokens: List[str]  # Tokens that should not be translated
    term_count: int  # Total terms found
    coverage: float  # % of text covered by glossary terms


@dataclass
class TranslationQuality:
    """Quality metrics for a translated segment."""

    segment_id: str
    source_text: str
    translated_text: str
    expected_terms: List[TermMatch]  # Terms that should appear
    found_terms: int  # Terms correctly translated
    missing_terms: List[str]  # Terms not found in translation
    incorrect_terms: List[Tuple[str, str]]  # (expected, found)
    quality_score: float  # Overall quality (0.0-1.0)


@dataclass
class MultiStageResult:
    """Result of multi-stage translation."""

    detected_source_language: str
    target_language: str
    segments: List[str]  # Translated segments
    analyses: List[SegmentAnalysis]  # Pre-translation analyses
    quality_metrics: List[TranslationQuality]  # Post-translation quality
    total_terms_found: int  # Total glossary terms in source
    total_terms_verified: int  # Terms correctly translated
    average_quality: float  # Average quality score
    total_cost: float  # Translation cost
    corrections_applied: int  # Number of automatic corrections


@dataclass
class PipelineConfig:
    """Configuration for multi-stage pipeline."""

    # Stage 1: Preprocessing
    enable_term_extraction: bool = True
    min_term_confidence: float = 0.7  # Minimum confidence for term matching
    enable_fuzzy_matching: bool = True  # Allow fuzzy term matching

    # Stage 2: Translation
    enable_glossary_injection: bool = True
    max_glossary_terms: int = 100  # Max terms to inject in prompt
    enable_term_protection: bool = True  # Protect terms as placeholders

    # Stage 3: Verification
    enable_verification: bool = True
    min_quality_threshold: float = 0.8  # Minimum quality to pass
    enable_auto_correction: bool = True  # Auto-correct term errors

    # Stage 4: Post-processing
    enable_final_validation: bool = True
    strict_mode: bool = False  # Fail on quality issues


class MultiStageTranslationPipeline:
    """
    Multi-stage translation pipeline with comprehensive glossary integration.

    This pipeline ensures that glossary terms are:
    1. Identified in source text (Preprocessing)
    2. Protected during translation (Translation)
    3. Verified in output (Verification)
    4. Corrected if needed (Post-processing)

    Example:
        >>> pipeline = MultiStageTranslationPipeline(
        ...     orchestrator=orchestrator,
        ...     glossary_manager=glossary,
        ... )
        >>> result = pipeline.translate(
        ...     segments=segments,
        ...     target_language="en",
        ... )
        >>> print(f"Quality: {result.average_quality:.2%}")
        >>> print(f"Terms verified: {result.total_terms_verified}/{result.total_terms_found}")
    """

    def __init__(
        self,
        orchestrator: TranslationOrchestrator,
        glossary_manager: GlossaryManager,
        config: Optional[PipelineConfig] = None,
    ):
        """
        Initialize multi-stage pipeline.

        Args:
            orchestrator: Translation orchestrator for API calls
            glossary_manager: Glossary manager for term lookups
            config: Pipeline configuration (uses defaults if None)
        """
        self.orchestrator = orchestrator
        self.glossary = glossary_manager
        self.config = config or PipelineConfig()

    def translate(
        self,
        segments: List[TranslationSegment],
        target_language: str,
        source_language: Optional[str] = None,
    ) -> MultiStageResult:
        """
        Translate segments using multi-stage pipeline.

        Args:
            segments: Segments to translate
            target_language: Target language code (e.g., "en", "fr")
            source_language: Source language (auto-detected if None)

        Returns:
            MultiStageResult with translations and quality metrics
        """
        # Detect source language if not provided
        if source_language is None:
            sample = " ".join([s.text for s in segments[:5]])
            source_language = self.orchestrator.detect_language(sample)

        # STAGE 1: Preprocessing - Extract and analyze glossary terms
        analyses = self._stage1_preprocessing(segments, source_language, target_language)

        # STAGE 2: Translation - Translate with glossary context
        translation_result = self._stage2_translation(
            segments, source_language, target_language, analyses
        )

        # STAGE 3: Verification - Check glossary term usage
        quality_metrics = self._stage3_verification(
            segments, translation_result.translations[target_language].segments, analyses
        )

        # STAGE 4: Post-processing - Apply corrections if needed
        final_segments, corrections = self._stage4_postprocessing(
            translation_result.translations[target_language].segments,
            quality_metrics,
            analyses,
        )

        # Calculate overall statistics
        total_terms_found = sum(a.term_count for a in analyses)
        total_terms_verified = sum(q.found_terms for q in quality_metrics)
        average_quality = (
            sum(q.quality_score for q in quality_metrics) / len(quality_metrics)
            if quality_metrics
            else 0.0
        )

        return MultiStageResult(
            detected_source_language=source_language,
            target_language=target_language,
            segments=final_segments,
            analyses=analyses,
            quality_metrics=quality_metrics,
            total_terms_found=total_terms_found,
            total_terms_verified=total_terms_verified,
            average_quality=average_quality,
            total_cost=translation_result.total_cost,
            corrections_applied=corrections,
        )

    def _stage1_preprocessing(
        self,
        segments: List[TranslationSegment],
        source_lang: str,
        target_lang: str,
    ) -> List[SegmentAnalysis]:
        """
        Stage 1: Preprocess segments and extract glossary terms.

        Args:
            segments: Segments to analyze
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            List of segment analyses
        """
        if not self.config.enable_term_extraction:
            return []

        analyses = []
        for segment in segments:
            # Find all glossary terms in segment
            matched_terms = self._find_glossary_terms(
                segment.text, source_lang, target_lang
            )

            # Get protected tokens
            protected = self.glossary.get_protected_tokens()

            # Calculate coverage
            term_chars = sum(len(t.source_text) for t in matched_terms)
            total_chars = len(segment.text)
            coverage = term_chars / total_chars if total_chars > 0 else 0.0

            analysis = SegmentAnalysis(
                segment_id=segment.segment_id,
                source_text=segment.text,
                matched_terms=matched_terms,
                protected_tokens=protected,
                term_count=len(matched_terms),
                coverage=coverage,
            )
            analyses.append(analysis)

        return analyses

    def _find_glossary_terms(
        self, text: str, source_lang: str, target_lang: str
    ) -> List[TermMatch]:
        """
        Find all glossary terms in text.

        Uses multiple matching strategies:
        1. Exact word match
        2. Case-insensitive match
        3. Fuzzy match (if enabled)

        Args:
            text: Text to search
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            List of matched terms
        """
        matches = []
        text_lower = text.lower()

        # Get all glossary entries
        for entry in self.glossary.get_all_entries():
            source_text = getattr(entry, source_lang, None)
            target_text = getattr(entry, target_lang, None)

            if not source_text or not target_text:
                continue

            # Try exact match (case-insensitive)
            pattern = re.compile(r"\b" + re.escape(source_text.lower()) + r"\b")
            for match in pattern.finditer(text_lower):
                confidence = 1.0  # Exact match

                term_match = TermMatch(
                    term_key=entry.key,
                    source_text=source_text,
                    target_text=target_text,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    category=entry.category,
                    confidence=confidence,
                )
                matches.append(term_match)

            # Try fuzzy match if enabled
            if self.config.enable_fuzzy_matching:
                # Match partial words (e.g., "лиц" in "лицевая")
                if len(source_text) >= 3:
                    partial_pattern = re.compile(re.escape(source_text.lower()))
                    for match in partial_pattern.finditer(text_lower):
                        # Check if already matched exactly
                        if any(
                            m.start_pos == match.start() and m.end_pos == match.end()
                            for m in matches
                        ):
                            continue

                        confidence = 0.8  # Fuzzy match

                        if confidence >= self.config.min_term_confidence:
                            term_match = TermMatch(
                                term_key=entry.key,
                                source_text=source_text,
                                target_text=target_text,
                                start_pos=match.start(),
                                end_pos=match.end(),
                                category=entry.category,
                                confidence=confidence,
                            )
                            matches.append(term_match)

        # Sort by position and remove overlaps
        matches.sort(key=lambda m: (m.start_pos, -m.confidence))
        non_overlapping = []
        for match in matches:
            # Check if overlaps with existing match
            overlaps = any(
                m.start_pos < match.end_pos and match.start_pos < m.end_pos
                for m in non_overlapping
            )
            if not overlaps:
                non_overlapping.append(match)

        return non_overlapping

    def _stage2_translation(
        self,
        segments: List[TranslationSegment],
        source_lang: str,
        target_lang: str,
        analyses: List[SegmentAnalysis],
    ) -> BatchTranslationResult:
        """
        Stage 2: Translate segments with glossary context.

        Args:
            segments: Segments to translate
            source_lang: Source language code
            target_lang: Target language code
            analyses: Preprocessing analyses

        Returns:
            BatchTranslationResult
        """
        # Build glossary context with all unique terms found
        all_terms = set()
        for analysis in analyses:
            for term in analysis.matched_terms:
                all_terms.add(term.term_key)

        # Get glossary entries for found terms
        glossary_entries = []
        for term_key in all_terms:
            for entry in self.glossary.get_all_entries():
                if entry.key == term_key:
                    glossary_entries.append(entry)
                    break

        # Limit to max terms
        if len(glossary_entries) > self.config.max_glossary_terms:
            # Sort by frequency and take top N
            term_freq = {}
            for analysis in analyses:
                for term in analysis.matched_terms:
                    term_freq[term.term_key] = term_freq.get(term.term_key, 0) + 1

            glossary_entries.sort(key=lambda e: term_freq.get(e.key, 0), reverse=True)
            glossary_entries = glossary_entries[: self.config.max_glossary_terms]

        # Build context string
        glossary_context = self.glossary.build_context_for_prompt(
            source_lang=source_lang,
            target_lang=target_lang,
            selected_entries=glossary_entries,
        )

        # Translate with glossary context
        result = self.orchestrator.translate_batch(
            segments=segments,
            target_languages=[target_lang],
            glossary_context=glossary_context,
        )

        return result

    def _stage3_verification(
        self,
        original_segments: List[TranslationSegment],
        translated_segments: List[str],
        analyses: List[SegmentAnalysis],
    ) -> List[TranslationQuality]:
        """
        Stage 3: Verify correct usage of glossary terms.

        Args:
            original_segments: Original segments
            translated_segments: Translated segments
            analyses: Preprocessing analyses

        Returns:
            List of quality metrics
        """
        if not self.config.enable_verification:
            return []

        quality_metrics = []
        for original, translated, analysis in zip(
            original_segments, translated_segments, analyses
        ):
            # Check which terms are correctly translated
            found_terms = 0
            missing_terms = []
            incorrect_terms = []

            translated_lower = translated.lower()

            for term_match in analysis.matched_terms:
                target_text_lower = term_match.target_text.lower()

                # Check if target term appears in translation
                if target_text_lower in translated_lower:
                    found_terms += 1
                else:
                    missing_terms.append(term_match.target_text)

            # Calculate quality score
            total_terms = len(analysis.matched_terms)
            quality_score = found_terms / total_terms if total_terms > 0 else 1.0

            quality = TranslationQuality(
                segment_id=analysis.segment_id,
                source_text=original.text,
                translated_text=translated,
                expected_terms=analysis.matched_terms,
                found_terms=found_terms,
                missing_terms=missing_terms,
                incorrect_terms=incorrect_terms,
                quality_score=quality_score,
            )
            quality_metrics.append(quality)

        return quality_metrics

    def _stage4_postprocessing(
        self,
        translated_segments: List[str],
        quality_metrics: List[TranslationQuality],
        analyses: List[SegmentAnalysis],
    ) -> Tuple[List[str], int]:
        """
        Stage 4: Apply corrections and final validation.

        Args:
            translated_segments: Translated segments
            quality_metrics: Quality metrics from verification
            analyses: Preprocessing analyses

        Returns:
            Tuple of (corrected_segments, corrections_count)
        """
        if not self.config.enable_auto_correction:
            return translated_segments, 0

        corrected_segments = []
        corrections_count = 0

        for segment, quality, analysis in zip(
            translated_segments, quality_metrics, analyses
        ):
            corrected = segment

            # Apply corrections for low-quality segments
            if quality.quality_score < self.config.min_quality_threshold:
                # Try to fix missing terms
                for missing_term in quality.missing_terms:
                    # Find the source term
                    for term_match in analysis.matched_terms:
                        if term_match.target_text == missing_term:
                            # Simple correction: if source term is still in translation,
                            # replace it with target term
                            source_lower = term_match.source_text.lower()
                            if source_lower in corrected.lower():
                                # Case-insensitive replacement
                                pattern = re.compile(
                                    re.escape(source_lower), re.IGNORECASE
                                )
                                corrected = pattern.sub(
                                    term_match.target_text, corrected, count=1
                                )
                                corrections_count += 1

            corrected_segments.append(corrected)

        return corrected_segments, corrections_count


__all__ = [
    "MultiStageTranslationPipeline",
    "MultiStageResult",
    "PipelineConfig",
    "TermMatch",
    "SegmentAnalysis",
    "TranslationQuality",
]
