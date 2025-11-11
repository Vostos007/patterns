"""
Knowledge Base System - обучаемая база знаний о вязании.

Система для накопления знаний из документов и использования их
для более точного перевода и генерации описаний изделий.

Основные компоненты:
- KnowledgeBase: база знаний с автоматической категоризацией
- PatternGenerator: генератор описаний изделий на основе знаний
- DocumentSplitter: умное разбиение документов на секции

ВАЖНО: По умолчанию система разбивает документы на секции!
Один документ (книга) может содержать узоры, техники, пряжу и т.д.
Каждая секция категоризируется отдельно.

Example:
    >>> from kps.knowledge import KnowledgeBase, PatternGenerator
    >>>
    >>> # Загрузить знания из папки (с разбиением на секции)
    >>> kb = KnowledgeBase("data/knowledge.db", split_sections=True)
    >>> kb.ingest_folder("knowledge/patterns")
    >>> # Один файл "Полное руководство.pdf" → множество секций!
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

from .splitter import (
    DocumentSplitter,
    DocumentSection,
    SplitStrategy,
    categorize_section,
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
    # Splitter
    "DocumentSplitter",
    "DocumentSection",
    "SplitStrategy",
    "categorize_section",
]
