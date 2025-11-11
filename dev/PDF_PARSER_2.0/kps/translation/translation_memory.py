"""
Translation memory - система кэширования и самообучения.

Функции:
- Кэширование переводов для повторного использования
- Автоматическое предложение новых терминов глоссария
- Few-shot learning - использование лучших примеров в промпте
- Статистика и улучшение качества со временем
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class TranslationMemoryEntry:
    """Запись в памяти переводов."""

    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    glossary_terms: List[str]  # Использованные термины глоссария
    timestamp: float
    usage_count: int = 1  # Сколько раз использовалась
    quality_score: float = 1.0  # Оценка качества (по умолчанию хорошая)


@dataclass
class SuggestedGlossaryTerm:
    """Предложенный термин для глоссария."""

    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    frequency: int  # Как часто встречался
    confidence: float  # Уверенность (0.0-1.0)
    contexts: List[str]  # Контексты использования


class TranslationMemory:
    """
    Система памяти переводов с самообучением.

    Функции:
    1. Кэширует переводы для быстрого повторного использования
    2. Предлагает новые термины для глоссария (авто-обнаружение)
    3. Выбирает лучшие примеры для few-shot learning
    4. Улучшает качество переводов со временем

    Example:
        >>> memory = TranslationMemory("data/translation_memory.json")
        >>>
        >>> # Сохранить перевод
        >>> memory.add_translation("2 лиц вместе", "k2tog", "ru", "en", ["k2tog"])
        >>>
        >>> # Найти в кэше
        >>> cached = memory.get_translation("2 лиц вместе", "ru", "en")
        >>> if cached:
        ...     print(f"Из кэша: {cached.translated_text}")
        >>>
        >>> # Получить лучшие примеры для промпта
        >>> examples = memory.get_few_shot_examples("ru", "en", limit=3)
        >>>
        >>> # Предложения новых терминов
        >>> suggestions = memory.get_glossary_suggestions(min_frequency=3)
    """

    def __init__(self, cache_file: Optional[str] = None):
        """
        Инициализация памяти переводов.

        Args:
            cache_file: Путь к файлу кэша (если None - только в памяти)
        """
        self.cache_file = Path(cache_file) if cache_file else None
        self.entries: Dict[str, TranslationMemoryEntry] = {}
        self.suggested_terms: Dict[str, SuggestedGlossaryTerm] = {}

        # Загрузить существующий кэш
        if self.cache_file and self.cache_file.exists():
            self._load_from_file()

    def add_translation(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        glossary_terms: List[str],
        quality_score: float = 1.0,
    ) -> None:
        """
        Добавить перевод в память.

        Args:
            source_text: Исходный текст
            translated_text: Переведённый текст
            source_lang: Исходный язык
            target_lang: Целевой язык
            glossary_terms: Использованные термины глоссария
            quality_score: Оценка качества (0.0-1.0)
        """
        key = self._make_key(source_text, source_lang, target_lang)

        if key in self.entries:
            # Обновить существующую запись
            entry = self.entries[key]
            entry.usage_count += 1
            entry.quality_score = (entry.quality_score + quality_score) / 2
            entry.timestamp = time.time()
        else:
            # Создать новую запись
            self.entries[key] = TranslationMemoryEntry(
                source_text=source_text,
                translated_text=translated_text,
                source_lang=source_lang,
                target_lang=target_lang,
                glossary_terms=glossary_terms,
                timestamp=time.time(),
                quality_score=quality_score,
            )

        # Автоматически сохранять периодически
        if len(self.entries) % 100 == 0:
            self.save()

    def get_translation(
        self, source_text: str, source_lang: str, target_lang: str
    ) -> Optional[TranslationMemoryEntry]:
        """
        Получить перевод из кэша.

        Args:
            source_text: Исходный текст
            source_lang: Исходный язык
            target_lang: Целевой язык

        Returns:
            Запись из кэша или None
        """
        key = self._make_key(source_text, source_lang, target_lang)
        return self.entries.get(key)

    def get_few_shot_examples(
        self,
        source_lang: str,
        target_lang: str,
        limit: int = 5,
        min_quality: float = 0.8,
    ) -> List[Tuple[str, str]]:
        """
        Получить лучшие примеры для few-shot learning.

        Выбирает самые качественные и часто используемые переводы
        для добавления в промпт.

        Args:
            source_lang: Исходный язык
            target_lang: Целевой язык
            limit: Максимум примеров
            min_quality: Минимальная оценка качества

        Returns:
            Список пар (source, translation)
        """
        # Фильтровать по языку и качеству
        candidates = [
            e
            for e in self.entries.values()
            if e.source_lang == source_lang
            and e.target_lang == target_lang
            and e.quality_score >= min_quality
        ]

        # Сортировать по качеству и частоте использования
        candidates.sort(
            key=lambda e: (e.quality_score, e.usage_count), reverse=True
        )

        # Взять топ N
        examples = [
            (e.source_text, e.translated_text) for e in candidates[:limit]
        ]

        return examples

    def suggest_glossary_term(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        context: str = "",
    ) -> None:
        """
        Предложить термин для добавления в глоссарий.

        Система автоматически отслеживает часто переводимые фразы
        и предлагает добавить их в глоссарий.

        Args:
            source_text: Исходный термин
            translated_text: Перевод термина
            source_lang: Исходный язык
            target_lang: Целевой язык
            context: Контекст использования
        """
        # Только короткие фразы (до 5 слов)
        if len(source_text.split()) > 5:
            return

        key = self._make_key(source_text, source_lang, target_lang)

        if key in self.suggested_terms:
            # Увеличить частоту
            term = self.suggested_terms[key]
            term.frequency += 1
            if context and context not in term.contexts:
                term.contexts.append(context)
        else:
            # Новое предложение
            self.suggested_terms[key] = SuggestedGlossaryTerm(
                source_text=source_text,
                translated_text=translated_text,
                source_lang=source_lang,
                target_lang=target_lang,
                frequency=1,
                confidence=0.5,  # Начальная уверенность
                contexts=[context] if context else [],
            )

    def get_glossary_suggestions(
        self, min_frequency: int = 3, min_confidence: float = 0.7
    ) -> List[SuggestedGlossaryTerm]:
        """
        Получить предложения для глоссария.

        Args:
            min_frequency: Минимальная частота использования
            min_confidence: Минимальная уверенность

        Returns:
            Список предложенных терминов
        """
        suggestions = [
            term
            for term in self.suggested_terms.values()
            if term.frequency >= min_frequency
            and term.confidence >= min_confidence
        ]

        # Сортировать по частоте
        suggestions.sort(key=lambda t: t.frequency, reverse=True)

        return suggestions

    def get_statistics(self) -> Dict:
        """
        Получить статистику использования.

        Returns:
            Словарь со статистикой
        """
        if not self.entries:
            return {
                "total_entries": 0,
                "total_suggestions": 0,
            }

        total_usage = sum(e.usage_count for e in self.entries.values())
        avg_quality = sum(e.quality_score for e in self.entries.values()) / len(
            self.entries
        )

        # Группировка по языкам
        language_pairs = {}
        for entry in self.entries.values():
            pair = f"{entry.source_lang} → {entry.target_lang}"
            language_pairs[pair] = language_pairs.get(pair, 0) + 1

        return {
            "total_entries": len(self.entries),
            "total_usage": total_usage,
            "average_quality": avg_quality,
            "language_pairs": language_pairs,
            "total_suggestions": len(self.suggested_terms),
            "high_frequency_suggestions": len(
                [t for t in self.suggested_terms.values() if t.frequency >= 3]
            ),
        }

    def save(self) -> None:
        """Сохранить кэш в файл."""
        if not self.cache_file:
            return

        # Подготовить данные
        data = {
            "entries": [
                {
                    "source_text": e.source_text,
                    "translated_text": e.translated_text,
                    "source_lang": e.source_lang,
                    "target_lang": e.target_lang,
                    "glossary_terms": e.glossary_terms,
                    "timestamp": e.timestamp,
                    "usage_count": e.usage_count,
                    "quality_score": e.quality_score,
                }
                for e in self.entries.values()
            ],
            "suggestions": [
                {
                    "source_text": s.source_text,
                    "translated_text": s.translated_text,
                    "source_lang": s.source_lang,
                    "target_lang": s.target_lang,
                    "frequency": s.frequency,
                    "confidence": s.confidence,
                    "contexts": s.contexts,
                }
                for s in self.suggested_terms.values()
            ],
        }

        # Создать директорию если нужно
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Сохранить
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_from_file(self) -> None:
        """Загрузить кэш из файла."""
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Загрузить записи
            for entry_data in data.get("entries", []):
                entry = TranslationMemoryEntry(**entry_data)
                key = self._make_key(
                    entry.source_text, entry.source_lang, entry.target_lang
                )
                self.entries[key] = entry

            # Загрузить предложения
            for sugg_data in data.get("suggestions", []):
                sugg = SuggestedGlossaryTerm(**sugg_data)
                key = self._make_key(
                    sugg.source_text, sugg.source_lang, sugg.target_lang
                )
                self.suggested_terms[key] = sugg

        except Exception as e:
            print(f"Warning: Failed to load cache: {e}")

    def _make_key(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Создать ключ для кэша.

        Args:
            text: Текст
            source_lang: Исходный язык
            target_lang: Целевой язык

        Returns:
            Хэш-ключ
        """
        # Нормализовать текст (lowercase, strip)
        normalized = text.lower().strip()

        # Создать ключ
        key_string = f"{source_lang}:{target_lang}:{normalized}"

        # Хэшировать для компактности
        return hashlib.md5(key_string.encode()).hexdigest()


__all__ = [
    "TranslationMemory",
    "TranslationMemoryEntry",
    "SuggestedGlossaryTerm",
]
