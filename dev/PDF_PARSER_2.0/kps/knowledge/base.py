"""
Knowledge Base - База знаний о вязании с категоризацией и RAG.

Система автоматического обучения из документов:
- Загрузка из папок (PDF, TXT, JSON, MD)
- Автоматическая категоризация (узоры, техники, пряжа, инструменты)
- Embeddings для семантического поиска
- RAG для контекстного перевода и генерации

Категории:
- Patterns (узоры) - схемы вязания, паттерны
- Techniques (техники) - способы вязания, приёмы
- Yarns (пряжа) - типы пряжи, свойства
- Tools (инструменты) - спицы, крючки, аксессуары
- Materials (материалы) - состав, характеристики
- Projects (изделия) - готовые описания изделий
- Stitches (петли) - виды петель и их обозначения
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

# Embeddings
try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

# Import splitter for section-based ingestion
from .splitter import DocumentSplitter, SplitStrategy, categorize_section


logger = logging.getLogger(__name__)


class KnowledgeCategory(Enum):
    """Категории знаний о вязании."""

    PATTERN = "pattern"  # Узоры и схемы
    TECHNIQUE = "technique"  # Техники вязания
    YARN = "yarn"  # Пряжа и её свойства
    TOOL = "tool"  # Инструменты (спицы, крючки)
    MATERIAL = "material"  # Материалы и состав
    PROJECT = "project"  # Готовые изделия
    STITCH = "stitch"  # Виды петель
    GENERAL = "general"  # Общая информация


@dataclass
class KnowledgeEntry:
    """Запись в базе знаний."""

    id: Optional[int]
    category: KnowledgeCategory
    title: str
    content: str
    language: str  # ru, en, fr
    source_file: str
    metadata: Dict  # Дополнительные данные
    embedding: Optional[List[float]] = None
    created_at: Optional[datetime] = None
    keywords: Optional[List[str]] = None


class KnowledgeBase:
    """
    База знаний о вязании с автоматическим обучением.

    Функции:
    1. Загрузка документов из папки (автоматически)
    2. Категоризация по темам
    3. Embeddings для поиска
    4. RAG для контекстного перевода
    5. Генерация описаний на основе знаний

    Example:
        >>> # Создать базу знаний
        >>> kb = KnowledgeBase("data/knowledge.db")
        >>>
        >>> # Загрузить данные из папки
        >>> kb.ingest_folder("knowledge/patterns")
        >>> kb.ingest_folder("knowledge/techniques")
        >>>
        >>> # Поиск релевантных знаний
        >>> results = kb.search(
        ...     "как вязать косу",
        ...     category=KnowledgeCategory.TECHNIQUE,
        ...     limit=5
        ... )
        >>>
        >>> # Получить контекст для перевода
        >>> context = kb.get_translation_context(
        ...     "2 лиц вместе с наклоном влево",
        ...     source_lang="ru",
        ...     target_lang="en"
        ... )
        >>>
        >>> # Генерация описания изделия
        >>> description = kb.generate_project_description(
        ...     project_type="шарф",
        ...     yarn_type="мохер",
        ...     technique="ажурное вязание"
        ... )
    """

    def __init__(
        self,
        db_path: str,
        use_embeddings: bool = True,
        split_sections: bool = True,
        split_strategy: SplitStrategy = SplitStrategy.AUTO,
    ):
        """
        Инициализация базы знаний.

        Args:
            db_path: Путь к SQLite базе
            use_embeddings: Использовать embeddings для поиска
            split_sections: Разбивать документы на секции (рекомендуется!)
            split_strategy: Стратегия разбиения (AUTO, MARKDOWN, CHAPTERS, etc.)
        """
        self.db_path = Path(db_path)
        self.use_embeddings = use_embeddings and NUMPY_AVAILABLE
        self.split_sections = split_sections
        self.split_strategy = split_strategy

        # Создать БД
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # Кэш для embeddings
        self.embedding_cache = {}

        # Document splitter для разбиения на секции
        if self.split_sections:
            self.splitter = DocumentSplitter(
                min_section_length=100,
                max_section_length=10000,
                chunk_size=2000,
            )
        else:
            self.splitter = None

        logger.info(
            f"KnowledgeBase initialized: {db_path} "
            f"(split_sections={split_sections}, embeddings={self.use_embeddings})"
        )

    def _init_database(self):
        """Создать структуру БД."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Таблица знаний
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                language TEXT NOT NULL,
                source_file TEXT,
                metadata TEXT,  -- JSON
                embedding BLOB,  -- Numpy array
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                keywords TEXT  -- JSON array
            )
        """
        )

        # Индексы
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_category ON knowledge(category)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_language ON knowledge(language)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_created ON knowledge(created_at DESC)"
        )

        # Таблица связей (что с чем работает)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry1_id INTEGER,
                entry2_id INTEGER,
                relationship_type TEXT,  -- compatible, requires, alternative
                strength REAL,  -- 0.0-1.0
                FOREIGN KEY (entry1_id) REFERENCES knowledge(id),
                FOREIGN KEY (entry2_id) REFERENCES knowledge(id)
            )
        """
        )

        conn.commit()
        conn.close()

    def ingest_folder(
        self,
        folder_path: str,
        category: Optional[KnowledgeCategory] = None,
        language: Optional[str] = None,
        recursive: bool = True,
    ) -> int:
        """
        Загрузить все документы из папки.

        Args:
            folder_path: Путь к папке с документами
            category: Категория (auto-detect если None)
            language: Язык (auto-detect если None)
            recursive: Рекурсивно по подпапкам

        Returns:
            Количество загруженных документов
        """
        folder = Path(folder_path)
        if not folder.exists():
            logger.warning(f"Folder not found: {folder_path}")
            return 0

        # Поддерживаемые форматы
        extensions = {".txt", ".md", ".json", ".pdf"}

        # Собрать файлы
        if recursive:
            files = [f for f in folder.rglob("*") if f.suffix.lower() in extensions]
        else:
            files = [f for f in folder.glob("*") if f.suffix.lower() in extensions]

        logger.info(f"Found {len(files)} files in {folder_path}")

        count = 0
        for file_path in files:
            try:
                # Загрузить файл (может вернуть несколько записей если split_sections=True)
                entries = self._load_file(file_path, category, language)
                if entries:
                    for entry in entries:
                        self.add_entry(entry)
                        count += 1

            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")
                continue

        logger.info(f"Ingested {count} sections from {folder_path}")
        return count

    def _load_file(
        self,
        file_path: Path,
        category: Optional[KnowledgeCategory],
        language: Optional[str],
    ) -> List[KnowledgeEntry]:
        """
        Загрузить один файл.

        Если split_sections=True, разбивает документ на секции
        и возвращает список записей (одна на секцию).
        Иначе возвращает одну запись для всего файла.

        Returns:
            Список записей (может быть много из одного файла!)
        """

        # Прочитать содержимое
        if file_path.suffix == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                title = data.get("title", file_path.stem)
                content = data.get("content", "")
                base_metadata = data.get("metadata", {})
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                title = file_path.stem
                base_metadata = {}

        if not content.strip():
            return []

        # Определить язык (если не указан)
        if language is None:
            language = self._detect_language(content)

        # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Разбить на секции если включено
        if self.split_sections and self.splitter:
            sections = self.splitter.split(
                content, strategy=self.split_strategy, filename=str(file_path)
            )

            entries = []
            for section in sections:
                # Категория для каждой секции отдельно!
                if category is None:
                    section_category = categorize_section(section)
                else:
                    section_category = category

                # Метаданные секции
                section_metadata = {
                    **base_metadata,
                    "section_level": section.level,
                    "section_start": section.start_pos,
                    "section_end": section.end_pos,
                    "parent_section": section.parent_title,
                    "document_title": title,
                }

                # Извлечь ключевые слова из секции
                section_keywords = self._extract_keywords(section.content)

                entry = KnowledgeEntry(
                    id=None,
                    category=section_category,
                    title=section.title,
                    content=section.content,
                    language=language,
                    source_file=str(file_path),
                    metadata=section_metadata,
                    keywords=section_keywords,
                )
                entries.append(entry)

            logger.info(
                f"Split '{file_path.name}' into {len(entries)} sections "
                f"({', '.join(set(e.category.value for e in entries))})"
            )
            return entries

        else:
            # Старое поведение: весь документ как одна запись
            if category is None:
                category = self._detect_category(title, content, file_path)

            keywords = self._extract_keywords(content)

            entry = KnowledgeEntry(
                id=None,
                category=category,
                title=title,
                content=content,
                language=language,
                source_file=str(file_path),
                metadata=base_metadata,
                keywords=keywords,
            )
            return [entry]

    def _detect_category(
        self, title: str, content: str, file_path: Path
    ) -> KnowledgeCategory:
        """Автоматически определить категорию."""

        # По пути к файлу
        path_lower = str(file_path).lower()
        if "pattern" in path_lower or "узор" in path_lower:
            return KnowledgeCategory.PATTERN
        if "technique" in path_lower or "техник" in path_lower:
            return KnowledgeCategory.TECHNIQUE
        if "yarn" in path_lower or "пряж" in path_lower:
            return KnowledgeCategory.YARN
        if "tool" in path_lower or "инструмент" in path_lower:
            return KnowledgeCategory.TOOL
        if "project" in path_lower or "изделие" in path_lower:
            return KnowledgeCategory.PROJECT
        if "stitch" in path_lower or "петл" in path_lower:
            return KnowledgeCategory.STITCH

        # По содержимому
        text = (title + " " + content).lower()

        # Ключевые слова для категорий
        category_keywords = {
            KnowledgeCategory.PATTERN: [
                "узор",
                "схема",
                "раппорт",
                "pattern",
                "chart",
                "repeat",
            ],
            KnowledgeCategory.TECHNIQUE: [
                "техника",
                "способ",
                "метод",
                "technique",
                "method",
                "way",
            ],
            KnowledgeCategory.YARN: [
                "пряжа",
                "нить",
                "волокно",
                "yarn",
                "fiber",
                "thread",
            ],
            KnowledgeCategory.TOOL: [
                "спицы",
                "крючок",
                "инструмент",
                "needle",
                "hook",
                "tool",
            ],
            KnowledgeCategory.STITCH: [
                "петля",
                "лицевая",
                "изнаночная",
                "stitch",
                "knit",
                "purl",
            ],
            KnowledgeCategory.PROJECT: [
                "свитер",
                "шарф",
                "шапка",
                "sweater",
                "scarf",
                "hat",
            ],
        }

        # Подсчитать совпадения
        scores = {}
        for cat, keywords in category_keywords.items():
            score = sum(1 for kw in keywords if kw in text)
            scores[cat] = score

        # Вернуть категорию с максимальным score
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)

        return KnowledgeCategory.GENERAL

    def _detect_language(self, text: str) -> str:
        """Определить язык текста."""
        # Простая эвристика по Кириллице
        cyrillic = sum(1 for c in text if ord(c) >= 0x0400 and ord(c) <= 0x04FF)
        latin = sum(1 for c in text if c.isalpha() and ord(c) < 0x0400)

        if cyrillic > latin:
            return "ru"
        return "en"

    def _extract_keywords(self, text: str) -> List[str]:
        """Извлечь ключевые слова."""
        # Простое извлечение часто встречающихся слов
        words = re.findall(r"\b\w{4,}\b", text.lower())

        # Убрать стоп-слова
        stop_words = {
            "this",
            "that",
            "with",
            "from",
            "have",
            "will",
            "your",
            "это",
            "для",
            "как",
            "что",
            "или",
        }
        words = [w for w in words if w not in stop_words]

        # Топ-10 частых слов
        from collections import Counter

        counter = Counter(words)
        return [word for word, count in counter.most_common(10)]

    def add_entry(self, entry: KnowledgeEntry) -> int:
        """Добавить запись в базу знаний."""

        # Создать embedding
        if self.use_embeddings:
            entry.embedding = self._get_embedding(entry.content, entry.language)

        # Сохранить в БД
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO knowledge
            (category, title, content, language, source_file, metadata, embedding, keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                entry.category.value,
                entry.title,
                entry.content,
                entry.language,
                entry.source_file,
                json.dumps(entry.metadata),
                self._embedding_to_bytes(entry.embedding) if entry.embedding else None,
                json.dumps(entry.keywords) if entry.keywords else None,
            ),
        )

        entry_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return entry_id

    def search(
        self,
        query: str,
        category: Optional[KnowledgeCategory] = None,
        language: Optional[str] = None,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> List[KnowledgeEntry]:
        """
        Семантический поиск в базе знаний.

        Args:
            query: Поисковый запрос
            category: Фильтр по категории
            language: Фильтр по языку
            limit: Максимум результатов
            threshold: Минимальное сходство

        Returns:
            Список релевантных записей
        """
        if not self.use_embeddings:
            # Простой текстовый поиск
            return self._text_search(query, category, language, limit)

        # Semantic search
        query_emb = self._get_embedding(query, language or "en")

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Построить WHERE clause
        where = []
        params = []

        if category:
            where.append("category = ?")
            params.append(category.value)

        if language:
            where.append("language = ?")
            params.append(language)

        where_clause = " AND ".join(where) if where else "1=1"

        # Получить кандидатов
        cursor.execute(
            f"""
            SELECT * FROM knowledge
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT 100
        """,
            params,
        )

        results = []
        for row in cursor.fetchall():
            entry = self._row_to_entry(row)

            if entry.embedding is None:
                continue

            # Вычислить сходство
            entry_emb = np.array(entry.embedding)
            similarity = self._cosine_similarity(query_emb, entry_emb)

            if similarity >= threshold:
                results.append((entry, similarity))

        conn.close()

        # Сортировать по сходству
        results.sort(key=lambda x: x[1], reverse=True)

        return [entry for entry, sim in results[:limit]]

    def _text_search(
        self,
        query: str,
        category: Optional[KnowledgeCategory],
        language: Optional[str],
        limit: int,
    ) -> List[KnowledgeEntry]:
        """Простой текстовый поиск."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        where = ["content LIKE ?"]
        params = [f"%{query}%"]

        if category:
            where.append("category = ?")
            params.append(category.value)

        if language:
            where.append("language = ?")
            params.append(language)

        where_clause = " AND ".join(where)

        cursor.execute(
            f"""
            SELECT * FROM knowledge
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """,
            params + [limit],
        )

        results = [self._row_to_entry(row) for row in cursor.fetchall()]
        conn.close()

        return results

    def get_translation_context(
        self, text: str, source_lang: str, target_lang: str, limit: int = 3
    ) -> str:
        """
        Получить контекст для перевода из базы знаний.

        Ищет релевантные примеры и термины для улучшения перевода.

        Args:
            text: Текст для перевода
            source_lang: Исходный язык
            target_lang: Целевой язык
            limit: Количество примеров

        Returns:
            Контекст для добавления в промпт
        """
        # Поиск релевантных знаний
        results = self.search(text, language=source_lang, limit=limit)

        if not results:
            return ""

        # Форматировать контекст
        context = "\n\nКонтекст из базы знаний:\n"

        for entry in results:
            context += f"\nКатегория: {entry.category.value}\n"
            context += f"Термины: {', '.join(entry.keywords[:5]) if entry.keywords else 'N/A'}\n"
            context += f"Фрагмент: {entry.content[:200]}...\n"

        return context

    def get_category_stats(self) -> Dict[str, int]:
        """Получить статистику по категориям."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT category, COUNT(*) as count
            FROM knowledge
            GROUP BY category
        """
        )

        stats = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()

        return stats

    def _get_embedding(self, text: str, language: str) -> Optional[np.ndarray]:
        """Создать embedding."""
        if not NUMPY_AVAILABLE:
            return None

        # Простая симуляция (в продакшене использовать sentence-transformers)
        import hashlib

        hash_bytes = hashlib.sha256(text.lower().encode()).digest()
        embedding = np.frombuffer(hash_bytes, dtype=np.uint8)
        embedding = np.tile(embedding, (384 // len(embedding) + 1))[:384]
        return embedding.astype(np.float32) / 255.0

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Косинусное сходство."""
        dot = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float((dot / (norm1 * norm2) + 1.0) / 2.0)

    def _embedding_to_bytes(self, embedding: np.ndarray) -> bytes:
        """Embedding в bytes."""
        return embedding.astype(np.float32).tobytes()

    def _bytes_to_embedding(self, data: bytes) -> np.ndarray:
        """Bytes в embedding."""
        return np.frombuffer(data, dtype=np.float32)

    def _row_to_entry(self, row: tuple) -> KnowledgeEntry:
        """Строка БД в KnowledgeEntry."""
        (
            id_,
            category,
            title,
            content,
            language,
            source_file,
            metadata_json,
            embedding_bytes,
            created_at,
            keywords_json,
        ) = row

        metadata = json.loads(metadata_json) if metadata_json else {}
        keywords = json.loads(keywords_json) if keywords_json else None

        embedding = None
        if embedding_bytes and NUMPY_AVAILABLE:
            embedding = self._bytes_to_embedding(embedding_bytes).tolist()

        return KnowledgeEntry(
            id=id_,
            category=KnowledgeCategory(category),
            title=title,
            content=content,
            language=language,
            source_file=source_file,
            metadata=metadata,
            embedding=embedding,
            keywords=keywords,
        )


__all__ = ["KnowledgeBase", "KnowledgeCategory", "KnowledgeEntry"]
