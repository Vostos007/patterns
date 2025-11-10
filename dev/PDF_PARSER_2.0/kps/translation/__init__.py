"""
Fast and simple glossary-driven translation for KPS v2.0.

RECOMMENDED: Use GlossaryTranslator for fast, efficient translation.

This package provides:
- GlossaryTranslator: Simple, fast glossary-driven translation (RECOMMENDED)
- TranslationOrchestrator: Core translation engine
- GlossaryManager: Glossary term management

For advanced features (multi-stage pipeline, verification, routing),
import from submodules if needed.
"""

# RECOMMENDED: Simple and fast
from .glossary_translator import GlossaryTranslator, TranslationResult as SimpleResult

# Core components
from .glossary import (
    GlossaryEntry,
    GlossaryManager,
    GlossaryMatch,
    extract_protected_tokens,
    select_glossary_terms,
)
from .orchestrator import (
    BatchTranslationResult,
    TranslationOrchestrator,
    TranslationResult,
    TranslationSegment,
)

# Advanced components (optional, available if needed)
try:
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
    from .verification import (
        SegmentVerification,
        TranslationVerifier,
        VerificationIssue,
        VerificationReport,
    )

    _ADVANCED_AVAILABLE = True
except ImportError:
    _ADVANCED_AVAILABLE = False


__all__ = [
    # RECOMMENDED: Simple and fast
    "GlossaryTranslator",
    "SimpleResult",
    # Core components
    "TranslationOrchestrator",
    "TranslationSegment",
    "TranslationResult",
    "BatchTranslationResult",
    "GlossaryManager",
    "GlossaryEntry",
    "GlossaryMatch",
    "select_glossary_terms",
    "extract_protected_tokens",
]

# Add advanced components to __all__ if available
if _ADVANCED_AVAILABLE:
    __all__.extend(
        [
            "AdvancedGlossaryMatcher",
            "MatchStrategy",
            "TermOccurrence",
            "MultiStageTranslationPipeline",
            "MultiStageResult",
            "PipelineConfig",
            "TermMatch",
            "SegmentAnalysis",
            "TranslationQuality",
            "TranslationVerifier",
            "VerificationReport",
            "SegmentVerification",
            "VerificationIssue",
            "LanguageRouter",
            "LanguagePair",
            "MultiLanguageResult",
        ]
    )
