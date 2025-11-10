"""Glossary management for KPS v2.0."""

from .manager import GlossaryEntry, GlossaryManager, GlossaryMatch
from .selector import extract_protected_tokens, select_glossary_terms

__all__ = [
    "GlossaryManager",
    "GlossaryEntry",
    "GlossaryMatch",
    "select_glossary_terms",
    "extract_protected_tokens",
]
