"""Translation pipeline for KPS v2.0."""

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
]
