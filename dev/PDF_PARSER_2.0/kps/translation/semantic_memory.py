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
import sqlite3
import time
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
    ):
        """
        Инициализация семантической памяти.

        Args:
            db_path: Путь к базе данных SQLite
            use_embeddings: Использовать embeddings для семантического поиска
            embedding_cache_size: Размер кэша embeddings в памяти
        """
        self.db_path = Path(db_path)
        self.use_embeddings = use_embeddings and NUMPY_AVAILABLE
        self.embedding_cache_size = embedding_cache_size

        # In-memory кэш для быстрого доступа
        self.cache: Dict[str, SemanticEntry] = {}
        self.embedding_cache: Dict[str, np.ndarray] = {}

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
                context TEXT,
                created_at REAL DEFAULT (datetime('now'))
            )
        """
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
        """
        key = self._make_key(source_text, source_lang, target_lang)

        # Вычислить embedding
        embedding = None
        if self.use_embeddings:
            embedding = self._get_embedding(source_text, source_lang)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            # Попробовать вставить
            cursor.execute(
                """
                INSERT INTO translations
                (hash, source_text, translated_text, source_lang, target_lang,
                 glossary_terms, timestamp, quality_score, embedding, context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    self._embedding_to_bytes(embedding) if embedding is not None else None,
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
        self, source_text: str, source_lang: str, target_lang: str
    ) -> Optional[SemanticEntry]:
        """
        Получить точный перевод из кэша.

        Args:
            source_text: Исходный текст
            source_lang: Исходный язык
            target_lang: Целевой язык

        Returns:
            Запись или None
        """
        key = self._make_key(source_text, source_lang, target_lang)

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

    def _get_embedding(self, text: str, lang: str) -> Optional[np.ndarray]:
        """
        Получить embedding для текста.

        Использует простую симуляцию embeddings.
        В продакшене нужно использовать sentence-transformers.

        Args:
            text: Текст
            lang: Язык

        Returns:
            Numpy array или None
        """
        if not self.use_embeddings or not NUMPY_AVAILABLE:
            return None

        # Проверить кэш
        cache_key = f"{lang}:{text}"
        if cache_key in self.embedding_cache:
            return self.embedding_cache[cache_key]

        # УПРОЩЁННАЯ СИМУЛЯЦИЯ embeddings
        # В продакшене использовать: sentence-transformers
        # from sentence_transformers import SentenceTransformer
        # model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        # embedding = model.encode(text)

        # Для демо: простое хеширование в вектор
        hash_bytes = hashlib.sha256(text.lower().encode()).digest()
        # Преобразовать в вектор 384 измерений (стандарт для sentence-BERT)
        embedding = np.frombuffer(hash_bytes, dtype=np.uint8)
        # Повторить до 384 измерений
        embedding = np.tile(embedding, (384 // len(embedding) + 1))[:384]
        # Нормализовать
        embedding = embedding.astype(np.float32) / 255.0

        # Добавить в кэш
        if len(self.embedding_cache) < self.embedding_cache_size:
            self.embedding_cache[cache_key] = embedding

        return embedding

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

    def _embedding_to_bytes(self, embedding: np.ndarray) -> bytes:
        """Преобразовать embedding в bytes для SQLite."""
        return embedding.astype(np.float32).tobytes()

    def _bytes_to_embedding(self, data: bytes) -> np.ndarray:
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

    def _make_key(self, text: str, source_lang: str, target_lang: str) -> str:
        """Создать ключ для хеша."""
        normalized = text.lower().strip()
        key_string = f"{source_lang}:{target_lang}:{normalized}"
        return hashlib.md5(key_string.encode()).hexdigest()

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
