"""
Knowledge Base System - обучаемая база знаний о вязании.

Система для накопления знаний из документов и использования их
для более точного перевода и генерации описаний изделий.

Основные компоненты:
- KnowledgeBase: база знаний с автоматической категоризацией
- PatternGenerator: генератор описаний изделий на основе знаний

Example:
    >>> from kps.knowledge import KnowledgeBase, PatternGenerator
    >>>
    >>> # Загрузить знания из папки
    >>> kb = KnowledgeBase("data/knowledge.db")
    >>> kb.ingest_folder("knowledge/patterns")
    >>> kb.ingest_folder("knowledge/techniques")
    >>>
    >>> # Использовать для генерации
    >>> generator = PatternGenerator(kb)
    >>> req = ProjectRequirements(
    ...     project_type="шарф",
    ...     yarn_type="мохер"
    ... )
    >>> description = generator.generate(req)
"""

from .base import (
    KnowledgeBase,
    KnowledgeCategory,
    KnowledgeEntry,
)

from .generator import (
    PatternGenerator,
    ProjectRequirements,
    ProjectDescription,
)

__all__ = [
    # Base
    "KnowledgeBase",
    "KnowledgeCategory",
    "KnowledgeEntry",
    # Generator
    "PatternGenerator",
    "ProjectRequirements",
    "ProjectDescription",
]
