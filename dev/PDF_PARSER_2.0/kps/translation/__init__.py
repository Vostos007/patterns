"""
Translation pipeline for KPS v2.0 with multi-stage glossary-driven translation.

This package provides a comprehensive translation system with:
- Multi-stage translation pipeline with glossary integration
- Advanced term matching and verification
- Universal language routing for any language pair
- Quality assurance and verification
- Support for Russian, English, French, and other languages
"""

from .glossary import (
    GlossaryEntry,
    GlossaryManager,
    GlossaryMatch,
    extract_protected_tokens,
    select_glossary_terms,
)
from .glossary.advanced_matcher import (
    AdvancedGlossaryMatcher,
    MatchStrategy,
    TermOccurrence,
)
from .language_router import LanguagePair, LanguageRouter, MultiLanguageResult
from .multi_stage_pipeline import (
    MultiStageResult,
    MultiStageTranslationPipeline,
    PipelineConfig,
    SegmentAnalysis,
    TermMatch,
    TranslationQuality,
)
from .orchestrator import (
    BatchTranslationResult,
    TranslationOrchestrator,
    TranslationResult,
    TranslationSegment,
)
from .verification import (
    SegmentVerification,
    TranslationVerifier,
    VerificationIssue,
    VerificationReport,
)

__all__ = [
    # Orchestrator
    "TranslationOrchestrator",
    "TranslationSegment",
    "TranslationResult",
    "BatchTranslationResult",
    # Glossary
    "GlossaryManager",
    "GlossaryEntry",
    "GlossaryMatch",
    "select_glossary_terms",
    "extract_protected_tokens",
    # Advanced Matcher
    "AdvancedGlossaryMatcher",
    "MatchStrategy",
    "TermOccurrence",
    # Multi-Stage Pipeline
    "MultiStageTranslationPipeline",
    "MultiStageResult",
    "PipelineConfig",
    "TermMatch",
    "SegmentAnalysis",
    "TranslationQuality",
    # Verification
    "TranslationVerifier",
    "VerificationReport",
    "SegmentVerification",
    "VerificationIssue",
    # Language Router
    "LanguageRouter",
    "LanguagePair",
    "MultiLanguageResult",
]
