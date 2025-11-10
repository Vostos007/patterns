"""
Universal language routing and translation coordination.

This module provides intelligent routing for any language pair and coordinates
the translation process across multiple stages and language combinations.

Supported languages:
- Russian (ru)
- English (en)
- French (fr)
- German (de)
- Spanish (es)
- Italian (it)
- And any other language supported by the translation model
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from .glossary.manager import GlossaryManager
from .multi_stage_pipeline import (
    MultiStageResult,
    MultiStageTranslationPipeline,
    PipelineConfig,
)
from .orchestrator import TranslationOrchestrator, TranslationSegment
from .verification import TranslationVerifier, VerificationReport


@dataclass
class LanguagePair:
    """Configuration for a language pair."""

    source: str  # Source language code
    target: str  # Target language code
    glossary_available: bool = False  # Whether glossary exists for this pair
    quality_threshold: float = 0.8  # Minimum quality for this pair


@dataclass
class MultiLanguageResult:
    """Result of multi-language translation."""

    source_language: str
    target_languages: List[str]
    results: Dict[str, MultiStageResult]  # {target_lang: result}
    verification_reports: Dict[str, VerificationReport]  # {target_lang: report}
    total_cost: float
    total_time: float
    overall_quality: float


class LanguageRouter:
    """
    Universal language routing and translation coordination.

    This router intelligently handles translation between any language pair,
    automatically detecting the best strategy based on:
    - Glossary availability
    - Language pair characteristics
    - Quality requirements
    - Cost optimization

    Example:
        >>> router = LanguageRouter(
        ...     orchestrator=orchestrator,
        ...     glossary_manager=glossary,
        ... )
        >>> # Translate from Russian to English and French
        >>> result = router.translate_multi_language(
        ...     segments=segments,
        ...     source_language="ru",
        ...     target_languages=["en", "fr"],
        ... )
        >>> print(f"Quality: {result.overall_quality:.2%}")
        >>> print(f"Cost: ${result.total_cost:.4f}")
    """

    # Supported language configurations
    SUPPORTED_LANGUAGES = {
        "ru": {
            "name": "Russian",
            "default_glossary": True,
            "primary_targets": ["en", "fr"],
        },
        "en": {
            "name": "English",
            "default_glossary": True,
            "primary_targets": ["ru", "fr", "de", "es"],
        },
        "fr": {
            "name": "French",
            "default_glossary": True,
            "primary_targets": ["en", "ru"],
        },
        "de": {"name": "German", "default_glossary": False, "primary_targets": ["en"]},
        "es": {"name": "Spanish", "default_glossary": False, "primary_targets": ["en"]},
        "it": {"name": "Italian", "default_glossary": False, "primary_targets": ["en"]},
    }

    def __init__(
        self,
        orchestrator: TranslationOrchestrator,
        glossary_manager: Optional[GlossaryManager] = None,
        default_config: Optional[PipelineConfig] = None,
    ):
        """
        Initialize language router.

        Args:
            orchestrator: Translation orchestrator
            glossary_manager: Optional glossary manager
            default_config: Default pipeline configuration
        """
        self.orchestrator = orchestrator
        self.glossary = glossary_manager
        self.default_config = default_config or PipelineConfig()

        # Initialize verifier if glossary available
        self.verifier = (
            TranslationVerifier(glossary_manager) if glossary_manager else None
        )

    def translate_multi_language(
        self,
        segments: List[TranslationSegment],
        source_language: Optional[str] = None,
        target_languages: Optional[List[str]] = None,
        config: Optional[PipelineConfig] = None,
    ) -> MultiLanguageResult:
        """
        Translate segments to multiple target languages.

        Args:
            segments: Segments to translate
            source_language: Source language (auto-detected if None)
            target_languages: Target languages (uses defaults if None)
            config: Pipeline configuration (uses default if None)

        Returns:
            MultiLanguageResult with translations and quality metrics
        """
        import time

        start_time = time.time()

        # Detect source language if not provided
        if source_language is None:
            sample = " ".join([s.text for s in segments[:5]])
            source_language = self.orchestrator.detect_language(sample)

        # Determine target languages
        if target_languages is None:
            target_languages = self._get_default_targets(source_language)

        # Remove source language from targets
        target_languages = [
            lang for lang in target_languages if lang != source_language
        ]

        # Use provided config or default
        config = config or self.default_config

        # Translate to each target language
        results = {}
        verification_reports = {}
        total_cost = 0.0

        for target_lang in target_languages:
            # Check if glossary available for this pair
            pair = LanguagePair(
                source=source_language,
                target=target_lang,
                glossary_available=self._has_glossary(source_language, target_lang),
            )

            # Translate using multi-stage pipeline
            if pair.glossary_available and self.glossary:
                pipeline = MultiStageTranslationPipeline(
                    orchestrator=self.orchestrator,
                    glossary_manager=self.glossary,
                    config=config,
                )
                result = pipeline.translate(
                    segments=segments,
                    target_language=target_lang,
                    source_language=source_language,
                )
                results[target_lang] = result
                total_cost += result.total_cost

                # Verify translation
                if self.verifier:
                    source_pairs = [(s.segment_id, s.text) for s in segments]
                    translated_pairs = [
                        (segments[i].segment_id, result.segments[i])
                        for i in range(len(segments))
                    ]
                    report = self.verifier.verify_translation(
                        source_segments=source_pairs,
                        translated_segments=translated_pairs,
                        source_lang=source_language,
                        target_lang=target_lang,
                    )
                    verification_reports[target_lang] = report
            else:
                # Use basic translation without glossary
                basic_result = self.orchestrator.translate_batch(
                    segments=segments,
                    target_languages=[target_lang],
                    glossary_context=None,
                )

                # Convert to MultiStageResult format
                result = MultiStageResult(
                    detected_source_language=basic_result.detected_source_language,
                    target_language=target_lang,
                    segments=basic_result.translations[target_lang].segments,
                    analyses=[],
                    quality_metrics=[],
                    total_terms_found=0,
                    total_terms_verified=0,
                    average_quality=0.8,  # Assume reasonable quality
                    total_cost=basic_result.total_cost,
                    corrections_applied=0,
                )
                results[target_lang] = result
                total_cost += basic_result.total_cost

        # Calculate overall metrics
        total_time = time.time() - start_time

        overall_quality = (
            sum(r.average_quality for r in results.values()) / len(results)
            if results
            else 0.0
        )

        return MultiLanguageResult(
            source_language=source_language,
            target_languages=target_languages,
            results=results,
            verification_reports=verification_reports,
            total_cost=total_cost,
            total_time=total_time,
            overall_quality=overall_quality,
        )

    def translate_single_pair(
        self,
        segments: List[TranslationSegment],
        source_language: str,
        target_language: str,
        config: Optional[PipelineConfig] = None,
    ) -> MultiStageResult:
        """
        Translate segments for a single language pair.

        Args:
            segments: Segments to translate
            source_language: Source language code
            target_language: Target language code
            config: Pipeline configuration

        Returns:
            MultiStageResult
        """
        config = config or self.default_config

        # Check if glossary available
        if self._has_glossary(source_language, target_language) and self.glossary:
            pipeline = MultiStageTranslationPipeline(
                orchestrator=self.orchestrator,
                glossary_manager=self.glossary,
                config=config,
            )
            return pipeline.translate(
                segments=segments,
                target_language=target_language,
                source_language=source_language,
            )
        else:
            # Basic translation
            basic_result = self.orchestrator.translate_batch(
                segments=segments,
                target_languages=[target_language],
                glossary_context=None,
            )

            return MultiStageResult(
                detected_source_language=basic_result.detected_source_language,
                target_language=target_language,
                segments=basic_result.translations[target_language].segments,
                analyses=[],
                quality_metrics=[],
                total_terms_found=0,
                total_terms_verified=0,
                average_quality=0.8,
                total_cost=basic_result.total_cost,
                corrections_applied=0,
            )

    def get_supported_pairs(self, source_language: Optional[str] = None) -> List[LanguagePair]:
        """
        Get all supported language pairs.

        Args:
            source_language: Filter by source language (None for all)

        Returns:
            List of supported language pairs
        """
        pairs = []

        languages = (
            [source_language] if source_language else self.SUPPORTED_LANGUAGES.keys()
        )

        for src_lang in languages:
            if src_lang not in self.SUPPORTED_LANGUAGES:
                continue

            config = self.SUPPORTED_LANGUAGES[src_lang]
            for tgt_lang in config["primary_targets"]:
                pair = LanguagePair(
                    source=src_lang,
                    target=tgt_lang,
                    glossary_available=self._has_glossary(src_lang, tgt_lang),
                )
                pairs.append(pair)

        return pairs

    def _get_default_targets(self, source_language: str) -> List[str]:
        """Get default target languages for a source language."""
        if source_language in self.SUPPORTED_LANGUAGES:
            return self.SUPPORTED_LANGUAGES[source_language]["primary_targets"]
        else:
            # Default to English if unknown source
            return ["en"]

    def _has_glossary(self, source_lang: str, target_lang: str) -> bool:
        """Check if glossary exists for language pair."""
        if not self.glossary:
            return False

        # Check if glossary has entries for both languages
        entries = self.glossary.get_all_entries()
        if not entries:
            return False

        # Check if at least one entry has both languages
        for entry in entries[:10]:  # Check first 10 entries
            source_text = getattr(entry, source_lang, None)
            target_text = getattr(entry, target_lang, None)
            if source_text and target_text:
                return True

        return False

    def get_language_info(self, language_code: str) -> Optional[Dict]:
        """
        Get information about a language.

        Args:
            language_code: Language code (e.g., "ru", "en")

        Returns:
            Dictionary with language info or None if not supported
        """
        return self.SUPPORTED_LANGUAGES.get(language_code)

    def optimize_translation_order(
        self, source_language: str, target_languages: List[str]
    ) -> List[str]:
        """
        Optimize the order of target languages for translation.

        Priority:
        1. Languages with glossary support
        2. Primary targets for the source language
        3. Alphabetical order

        Args:
            source_language: Source language code
            target_languages: List of target language codes

        Returns:
            Optimized list of target languages
        """
        # Score each target language
        scores = {}
        for target_lang in target_languages:
            score = 0

            # Priority 1: Glossary available
            if self._has_glossary(source_language, target_lang):
                score += 100

            # Priority 2: Primary target
            if (
                source_language in self.SUPPORTED_LANGUAGES
                and target_lang
                in self.SUPPORTED_LANGUAGES[source_language]["primary_targets"]
            ):
                score += 10

            scores[target_lang] = score

        # Sort by score (descending), then alphabetically
        return sorted(target_languages, key=lambda lang: (-scores.get(lang, 0), lang))


__all__ = ["LanguageRouter", "LanguagePair", "MultiLanguageResult"]
