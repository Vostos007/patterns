"""
Semantic Translation Memory - умная память переводов с embeddings и RAG.

Функции:
- Семантический поиск похожих переводов (не только точное совпадение!)
- Embeddings для понимания смысла текста
- RAG (Retrieval-Augmented Generation) для контекстного поиска
- Автоматическое обучение на похожих примерах
- База данных с векторным индексом

Технологии:
- Sentence-BERT для embeddings (многоязычный)
- Cosine similarity для поиска похожих
- SQLite + JSON для хранения
- In-memory cache для скорости
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Опциональный импорт для embeddings
try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

from kps.clients.embeddings import EmbeddingsClient


logger = logging.getLogger(__name__)


@dataclass
class SemanticEntry:
    """Запись с embeddings для семантического поиска."""

    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    glossary_terms: List[str]
    timestamp: float
    usage_count: int = 1
    quality_score: float = 1.0
    embedding: Optional[List[float]] = None  # Векторное представление
    context: str = ""  # Контекст использования


@dataclass
class SimilarTranslation:
    """Похожий перевод с оценкой сходства."""

    entry: SemanticEntry
    similarity: float  # Косинусное сходство 0.0-1.0
    exact_match: bool  # Точное совпадение или похожее


class SemanticTranslationMemory:
    """
    Умная память переводов с семантическим поиском.

    Возможности:
    1. Находит похожие переводы (не только точные!)
    2. Использует embeddings для понимания смысла
    3. RAG - получает релевантные примеры для ИИ
    4. Учится на похожих контекстах

    Примеры:
        >>> memory = SemanticTranslationMemory("data/semantic_memory.db")
        >>>
        >>> # Сохранить перевод
        >>> memory.add_translation(
        ...     "Провяжите 2 петли вместе",
        ...     "Knit 2 stitches together",
        ...     "ru", "en", ["k2tog"]
        ... )
        >>>
        >>> # Найти точный или похожий
        >>> results = memory.find_similar(
        ...     "Провяжите две петли вместе",  # Немного другой текст!
        ...     "ru", "en",
        ...     threshold=0.85  # 85% сходства достаточно
        ... )
        >>> if results:
        ...     best = results[0]
        ...     print(f"Найдено (сходство {best.similarity:.0%}): {best.entry.translated_text}")
        >>>
        >>> # RAG - получить релевантные примеры для промпта
        >>> examples = memory.get_rag_examples(
        ...     "Вяжите лицевыми",  # Новый запрос
        ...     "ru", "en",
        ...     limit=3  # Топ-3 похожих
        ... )
    """

    def __init__(
        self,
        db_path: str,
        use_embeddings: bool = True,
        embedding_cache_size: int = 1000,
        embedding_client: Optional[EmbeddingsClient] = None,
        embedding_dimensions: Optional[int] = 1536,
    ):
        """
        Инициализация семантической памяти.

        Args:
            db_path: Путь к базе данных SQLite
            use_embeddings: Использовать embeddings для семантического поиска
            embedding_cache_size: Размер кэша embeddings в памяти
        """
        self.db_path = Path(db_path)
        self.embedding_client = embedding_client
        self.embedding_dimensions = embedding_dimensions

        if use_embeddings and not NUMPY_AVAILABLE:
            logger.warning("NumPy unavailable. Semantic embeddings disabled.")

        if use_embeddings and embedding_client is None:
            logger.warning(
                "Embedding client not provided. Semantic embeddings disabled until client is set."
            )

        self.use_embeddings = (
            use_embeddings and NUMPY_AVAILABLE and embedding_client is not None
        )
        self.embedding_cache_size = embedding_cache_size

        # In-memory кэш для быстрого доступа
        self.cache: Dict[str, SemanticEntry] = {}
        self.embedding_cache: "OrderedDict[str, np.ndarray]" = OrderedDict()

        # Инициализация БД
        self._init_database()

        # Загрузить популярные записи в кэш
        self._warm_up_cache()

    def _init_database(self) -> None:
        """Создать структуру базы данных."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Таблица переводов
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT UNIQUE NOT NULL,
                source_text TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                glossary_terms TEXT,  -- JSON array
                timestamp REAL NOT NULL,
                usage_count INTEGER DEFAULT 1,
                quality_score REAL DEFAULT 1.0,
                embedding BLOB,  -- Numpy array as bytes
                embedding_q16 BLOB,  -- Quantized embedding
                embedding_version INTEGER DEFAULT 0,
                context TEXT,
                created_at REAL DEFAULT (datetime('now'))
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """
        )

        self._ensure_column(
            cursor,
            "translations",
            "embedding_q16",
            "ALTER TABLE translations ADD COLUMN embedding_q16 BLOB",
        )
        self._ensure_column(
            cursor,
            "translations",
            "embedding_version",
            "ALTER TABLE translations ADD COLUMN embedding_version INTEGER DEFAULT 0",
        )

        # Индексы для быстрого поиска
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_hash ON translations(hash)
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_lang_pair ON translations(source_lang, target_lang)
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_usage ON translations(usage_count DESC)
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_quality ON translations(quality_score DESC)
        """
        )

        # Таблица предложений терминов
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS term_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_text TEXT NOT NULL,
                translated_text TEXT,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                confidence REAL DEFAULT 0.5,
                contexts TEXT,  -- JSON array
                UNIQUE(source_text, source_lang, target_lang)
            )
        """
        )

        conn.commit()
        conn.close()

    def _ensure_column(
        self, cursor: sqlite3.Cursor, table: str, column: str, ddl: str
    ) -> None:
        """Ensure optional columns exist for backward compatibility."""

        cursor.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in cursor.fetchall()]
        if column not in cols:
            cursor.execute(ddl)

    def _warm_up_cache(self) -> None:
        """Загрузить популярные записи в кэш."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Загрузить топ-N по usage_count
        cursor.execute(
            """
            SELECT * FROM translations
            ORDER BY usage_count DESC, quality_score DESC
            LIMIT ?
        """,
            (self.embedding_cache_size,),
        )

        for row in cursor.fetchall():
            entry = self._row_to_entry(row)
            key = self._make_key(entry.source_text, entry.source_lang, entry.target_lang)
            self.cache[key] = entry

        conn.close()

    def add_translation(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        glossary_terms: List[str],
        quality_score: float = 1.0,
        context: str = "",
        glossary_version: Optional[int] = None,
        model: Optional[str] = None,
    ) -> None:
        """
        Добавить перевод в память.

        Args:
            source_text: Исходный текст
            translated_text: Переведённый текст
            source_lang: Исходный язык
            target_lang: Целевой язык
            glossary_terms: Использованные термины
            quality_score: Оценка качества (0.0-1.0)
            context: Контекст использования
            glossary_version: Версия глоссария (NEW - для правильного кэширования)
            model: Название модели (NEW - для правильного кэширования)
        """
        # IMPROVED: Include glossary_version and model in cache key
        key = self._make_key(
            source_text,
            source_lang,
            target_lang,
            glossary_version=glossary_version,
            model=model,
        )

        # Вычислить embedding
        embedding = None
        embedding_bytes = None
        embedding_q16 = None
        embedding_version_value = 0
        if self.use_embeddings:
            embedding = self._get_embedding(source_text, source_lang)
            if embedding is not None:
                embedding_bytes = self._embedding_to_bytes(embedding)
                embedding_q16 = self._quantize_embedding(embedding)
                embedding_version_value = 1

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # Попробовать вставить
            cursor.execute(
                """
                INSERT INTO translations
                (hash, source_text, translated_text, source_lang, target_lang,
                 glossary_terms, timestamp, quality_score, embedding, embedding_q16,
                 embedding_version, context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    key,
                    source_text,
                    translated_text,
                    source_lang,
                    target_lang,
                    json.dumps(glossary_terms),
                    time.time(),
                    quality_score,
                    embedding_bytes,
                    embedding_q16,
                    embedding_version_value,
                    context,
                ),
            )
        except sqlite3.IntegrityError:
            # Уже существует - обновить
            cursor.execute(
                """
                UPDATE translations
                SET usage_count = usage_count + 1,
                    quality_score = (quality_score + ?) / 2,
                    timestamp = ?
                WHERE hash = ?
            """,
                (quality_score, time.time(), key),
            )

        conn.commit()
        conn.close()

        # Обновить кэш
        entry = SemanticEntry(
            source_text=source_text,
            translated_text=translated_text,
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_terms=glossary_terms,
            timestamp=time.time(),
            quality_score=quality_score,
            embedding=embedding.tolist() if embedding is not None else None,
            context=context,
        )
        self.cache[key] = entry

    def get_translation(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        glossary_version: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Optional[SemanticEntry]:
        """
        Получить точный перевод из кэша.

        Args:
            source_text: Исходный текст
            source_lang: Исходный язык
            target_lang: Целевой язык
            glossary_version: Версия глоссария (NEW)
            model: Название модели (NEW)

        Returns:
            Запись или None
        """
        # IMPROVED: Include glossary_version and model in cache key
        key = self._make_key(
            source_text,
            source_lang,
            target_lang,
            glossary_version=glossary_version,
            model=model,
        )

        # Сначала проверить in-memory кэш
        if key in self.cache:
            return self.cache[key]

        # Поискать в БД
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM translations WHERE hash = ?
        """,
            (key,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            entry = self._row_to_entry(row)
            self.cache[key] = entry  # Добавить в кэш
            return entry

        return None

    def delete_translation(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        glossary_version: Optional[int] = None,
        model: Optional[str] = None,
    ) -> None:
        """Удалить запись перевода из базы и из in-memory кэшей."""

        key = self._make_key(
            source_text,
            source_lang,
            target_lang,
            glossary_version=glossary_version,
            model=model,
        )

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM translations WHERE hash = ?", (key,))
        conn.commit()
        conn.close()

        self.cache.pop(key, None)
        self.embedding_cache.pop(key, None)

    def find_similar(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        threshold: float = 0.85,
        limit: int = 5,
    ) -> List[SimilarTranslation]:
        """
        Найти похожие переводы (семантический поиск!).

        Это ключевая функция для самообучения - находит не только
        точные совпадения, но и семантически похожие фразы.

        Args:
            source_text: Текст для поиска
            source_lang: Исходный язык
            target_lang: Целевой язык
            threshold: Минимальное сходство (0.0-1.0)
            limit: Максимум результатов

        Returns:
            Список похожих переводов с оценкой сходства
        """
        # Сначала проверить точное совпадение
        exact = self.get_translation(source_text, source_lang, target_lang)
        if exact:
            return [SimilarTranslation(entry=exact, similarity=1.0, exact_match=True)]

        # Семантический поиск
        if not self.use_embeddings:
            return []  # Без embeddings не можем искать похожие

        # Получить embedding запроса
        query_embedding = self._get_embedding(source_text, source_lang)
        if query_embedding is None:
            return []

        # Получить все записи для языковой пары
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM translations
            WHERE source_lang = ? AND target_lang = ?
            AND embedding IS NOT NULL
            ORDER BY usage_count DESC, quality_score DESC
            LIMIT 1000
        """,
            (source_lang, target_lang),
        )

        results = []
        for row in cursor.fetchall():
            entry = self._row_to_entry(row)

            if entry.embedding is None:
                continue

            # Вычислить косинусное сходство
            entry_emb = np.array(entry.embedding)
            similarity = self._cosine_similarity(query_embedding, entry_emb)

            if similarity >= threshold:
                results.append(
                    SimilarTranslation(
                        entry=entry, similarity=similarity, exact_match=False
                    )
                )

        conn.close()

        # Сортировать по сходству
        results.sort(key=lambda x: x.similarity, reverse=True)

        return results[:limit]

    def get_rag_examples(
        self,
        query_text: str,
        source_lang: str,
        target_lang: str,
        limit: int = 5,
        min_similarity: float = 0.7,
    ) -> List[Tuple[str, str, float]]:
        """
        RAG - получить релевантные примеры для промпта ИИ.

        Retrieval-Augmented Generation: находит похожие переводы
        и возвращает их как few-shot примеры.

        Args:
            query_text: Текст запроса
            source_lang: Исходный язык
            target_lang: Целевой язык
            limit: Максимум примеров
            min_similarity: Минимальное сходство

        Returns:
            Список (source, target, similarity)
        """
        similar = self.find_similar(
            query_text, source_lang, target_lang, threshold=min_similarity, limit=limit
        )

        examples = [
            (s.entry.source_text, s.entry.translated_text, s.similarity) for s in similar
        ]

        return examples

    # Compatibility helpers -------------------------------------------------
    def get_few_shot_examples(
        self,
        source_lang: str,
        target_lang: str,
        limit: int = 5,
        min_quality: float = 0.8,
    ) -> List[Tuple[str, str]]:
        """Return top translations for few-shot prompts.

        Provides the same interface as ``TranslationMemory.get_few_shot_examples``
        so higher-level translators can reuse semantic memory transparently.
        """

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT source_text, translated_text, quality_score, usage_count
            FROM translations
            WHERE source_lang = ? AND target_lang = ? AND quality_score >= ?
            ORDER BY quality_score DESC, usage_count DESC, timestamp DESC
            LIMIT ?
        """,
            (source_lang, target_lang, min_quality, limit),
        )

        rows = cursor.fetchall()
        conn.close()

        return [(row[0], row[1]) for row in rows]

    def save(self) -> None:
        """API compatibility shim (data is committed eagerly)."""

        # SQLite writes happen eagerly on add_translation, so nothing to do.
        return None

    def suggest_glossary_term(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        confidence: float = 0.5,
        context: str = "",
    ) -> None:
        """Store candidate glossary term for later review."""

        contexts: List[str] = []
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT contexts, frequency FROM term_suggestions
            WHERE source_text=? AND source_lang=? AND target_lang=?
        """,
            (source_text, source_lang, target_lang),
        )
        row = cursor.fetchone()
        if row:
            stored_contexts = json.loads(row[0]) if row[0] else []
            contexts = stored_contexts
            frequency = row[1] + 1
            if context:
                contexts.append(context)
                contexts = contexts[-5:]
            cursor.execute(
                """
                UPDATE term_suggestions
                SET translated_text=?, frequency=?, confidence=?, contexts=?
                WHERE source_text=? AND source_lang=? AND target_lang=?
            """,
                (
                    translated_text,
                    frequency,
                    confidence,
                    json.dumps(contexts, ensure_ascii=False),
                    source_text,
                    source_lang,
                    target_lang,
                ),
            )
        else:
            if context:
                contexts.append(context)
            cursor.execute(
                """
                INSERT INTO term_suggestions
                (source_text, translated_text, source_lang, target_lang, frequency, confidence, contexts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    source_text,
                    translated_text,
                    source_lang,
                    target_lang,
                    1,
                    confidence,
                    json.dumps(contexts, ensure_ascii=False),
                ),
            )

        conn.commit()
        conn.close()

    def get_glossary_suggestions(
        self,
        min_frequency: int = 2,
        min_confidence: float = 0.5,
    ) -> List[Dict]:
        """Return aggregated glossary suggestions."""

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT source_text, translated_text, source_lang, target_lang, frequency, confidence, contexts
            FROM term_suggestions
            WHERE frequency >= ? AND confidence >= ?
            ORDER BY frequency DESC, confidence DESC
        """,
            (min_frequency, min_confidence),
        )

        suggestions = []
        for row in cursor.fetchall():
            contexts = json.loads(row[6]) if row[6] else []
            suggestions.append(
                {
                    "source_text": row[0],
                    "translated_text": row[1],
                    "source_lang": row[2],
                    "target_lang": row[3],
                    "frequency": row[4],
                    "confidence": row[5],
                    "contexts": contexts,
                }
            )

        conn.close()
        return suggestions

    def _get_embedding(self, text: str, lang: str) -> Optional[np.ndarray]:
        """Получить embedding для текста через EmbeddingsClient."""

        if not self.use_embeddings or not NUMPY_AVAILABLE:
            return None

        cache_key = f"{lang}:{text}"
        cached = self.embedding_cache.get(cache_key)
        if cached is not None:
            self.embedding_cache.move_to_end(cache_key)
            return cached

        if not self.embedding_client:
            return None

        vectors = self.embedding_client.create_vectors([text])
        if not vectors:
            return None

        vector = np.asarray(vectors[0], dtype=np.float32)

        if self.embedding_dimensions is None:
            self.embedding_dimensions = len(vector)
        elif len(vector) != self.embedding_dimensions:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.embedding_dimensions}, got {len(vector)}"
            )

        self._cache_embedding(cache_key, vector)
        return vector

    def _cache_embedding(self, key: str, value: np.ndarray) -> None:
        if self.embedding_cache_size <= 0:
            return

        if key in self.embedding_cache:
            self.embedding_cache.move_to_end(key)
        self.embedding_cache[key] = value

        while len(self.embedding_cache) > self.embedding_cache_size:
            self.embedding_cache.popitem(last=False)

    def get_metadata(self, key: str) -> Optional[str]:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM metadata WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def set_metadata(self, key: str, value: str) -> None:
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO metadata(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )
        conn.commit()
        conn.close()

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Вычислить косинусное сходство.

        Args:
            vec1: Первый вектор
            vec2: Второй вектор

        Returns:
            Сходство 0.0-1.0
        """
        dot = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot / (norm1 * norm2)
        # Преобразовать в 0.0-1.0
        return float((similarity + 1.0) / 2.0)

    @staticmethod
    def _embedding_to_bytes(embedding: np.ndarray) -> bytes:
        """Преобразовать embedding в bytes для SQLite."""
        return embedding.astype(np.float32).tobytes()

    @staticmethod
    def _quantize_embedding(embedding: np.ndarray) -> bytes:
        """Quantize embedding to float16 for compact storage."""
        return embedding.astype(np.float16).tobytes()

    @staticmethod
    def _bytes_to_embedding(data: bytes) -> np.ndarray:
        """Преобразовать bytes в embedding."""
        return np.frombuffer(data, dtype=np.float32)

    def _row_to_entry(self, row: tuple) -> SemanticEntry:
        """Преобразовать строку БД в SemanticEntry."""
        (
            id_,
            hash_,
            source_text,
            translated_text,
            source_lang,
            target_lang,
            glossary_terms_json,
            timestamp,
            usage_count,
            quality_score,
            embedding_bytes,
            _embedding_q16_bytes,
            _embedding_version,
            context,
            created_at,
        ) = row

        glossary_terms = json.loads(glossary_terms_json) if glossary_terms_json else []

        embedding = None
        if embedding_bytes and NUMPY_AVAILABLE:
            embedding = self._bytes_to_embedding(embedding_bytes).tolist()

        return SemanticEntry(
            source_text=source_text,
            translated_text=translated_text,
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_terms=glossary_terms,
            timestamp=timestamp,
            usage_count=usage_count,
            quality_score=quality_score,
            embedding=embedding,
            context=context or "",
        )

    def _make_key(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        glossary_version: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Создать ключ для хеша кэша.

        IMPROVED: Now includes glossary version and model to prevent cache
        collisions when glossary or model changes.

        Args:
            text: Source text
            source_lang: Source language
            target_lang: Target language
            glossary_version: Glossary version number (optional, defaults to 0)
            model: Model name (optional, defaults to "unknown")

        Returns:
            SHA256 hash as hex string
        """
        normalized = text.lower().strip()

        # Create versioned key payload
        payload = {
            "t": normalized,
            "s": source_lang,
            "tgt": target_lang,
            "g": glossary_version or 0,
            "m": model or "unknown",
        }

        # Use deterministic JSON serialization
        key_string = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(',', ':'),
            sort_keys=True  # Ensure consistent ordering
        )

        # Use SHA256 (more secure than MD5)
        return hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    def get_statistics(self) -> Dict:
        """Получить статистику."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM translations")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(usage_count) FROM translations")
        total_usage = cursor.fetchone()[0] or 0

        cursor.execute("SELECT AVG(quality_score) FROM translations")
        avg_quality = cursor.fetchone()[0] or 0.0

        cursor.execute(
            """
            SELECT source_lang, target_lang, COUNT(*)
            FROM translations
            GROUP BY source_lang, target_lang
        """
        )
        lang_pairs = {f"{row[0]} → {row[1]}": row[2] for row in cursor.fetchall()}

        conn.close()

        return {
            "total_entries": total,
            "total_usage": total_usage,
            "average_quality": avg_quality,
            "language_pairs": lang_pairs,
            "cache_size": len(self.cache),
            "embeddings_enabled": self.use_embeddings,
        }


__all__ = ["SemanticTranslationMemory", "SemanticEntry", "SimilarTranslation"]
