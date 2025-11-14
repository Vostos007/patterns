"""PostgreSQL + pgvector backend for semantic translation memory."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

try:  # pragma: no cover - imported lazily in runtime environments
    import psycopg2
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore

from .semantic_memory import SemanticEntry, SimilarTranslation
from .semantic_memory import SemanticTranslationMemory as SQLiteSemanticMemory

logger = logging.getLogger(__name__)


@dataclass
class _PGConfig:
    dsn: str
    embedding_dimensions: int = 1536


class SemanticTranslationMemoryPG:
    """Semantic memory backed by Postgres + pgvector."""

    def __init__(
        self,
        dsn: str,
        *,
        embedding_client=None,
        embedding_dimensions: int = 1536,
        connection_factory: Optional[Callable[[], any]] = None,
    ) -> None:
        if psycopg2 is None and connection_factory is None:  # pragma: no cover
            raise RuntimeError("psycopg2 is required for SemanticTranslationMemoryPG")

        self.config = _PGConfig(dsn=dsn, embedding_dimensions=embedding_dimensions)
        self._embedding_client = embedding_client
        self._connection_factory = connection_factory or self._default_connection

        self._init_db()

    # ------------------------------------------------------------------
    def _default_connection(self):  # pragma: no cover - executed in real env
        return psycopg2.connect(self.config.dsn)

    @contextmanager
    def _connection(self):
        conn = self._connection_factory()
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:  # pragma: no cover - best effort cleanup
                pass

    def _init_db(self) -> None:
        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS semantic_translations (
                    id BIGSERIAL PRIMARY KEY,
                    hash TEXT UNIQUE NOT NULL,
                    source_text TEXT NOT NULL,
                    translated_text TEXT NOT NULL,
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    glossary_terms JSONB,
                    usage_count INTEGER DEFAULT 1,
                    quality_score REAL DEFAULT 1.0,
                    embedding VECTOR({self.config.embedding_dimensions}),
                    context TEXT,
                    created_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS term_suggestions (
                    id BIGSERIAL PRIMARY KEY,
                    source_text TEXT NOT NULL,
                    translated_text TEXT,
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    confidence REAL DEFAULT 0.5,
                    contexts JSONB,
                    UNIQUE(source_text, source_lang, target_lang)
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
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
        key = SQLiteSemanticMemory._make_key(  # reuse helper
            source_text,
            source_lang,
            target_lang,
            glossary_version=glossary_version,
            model=model,
        )

        embedding = None
        if self._embedding_client:
            vectors = self._embedding_client.create_vectors([source_text])
            if vectors:
                embedding = vectors[0]

        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO semantic_translations
                    (hash, source_text, translated_text, source_lang, target_lang,
                     glossary_terms, quality_score, embedding, context)
                VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (hash) DO UPDATE SET
                    usage_count = semantic_translations.usage_count + 1,
                    quality_score = (semantic_translations.quality_score + EXCLUDED.quality_score) / 2
                """,
                (
                    key,
                    source_text,
                    translated_text,
                    source_lang,
                    target_lang,
                    json.dumps(glossary_terms),
                    quality_score,
                    embedding,
                    context,
                ),
            )
            conn.commit()

    # ------------------------------------------------------------------
    def get_translation(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        glossary_version: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Optional[SemanticEntry]:
        key = SQLiteSemanticMemory._make_key(
            source_text,
            source_lang,
            target_lang,
            glossary_version=glossary_version,
            model=model,
        )
        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT source_text, translated_text, source_lang, target_lang, glossary_terms, usage_count, quality_score, context FROM semantic_translations WHERE hash=%s",
                (key,),
            )
            row = cur.fetchone()
            if not row:
                return None

        glossary_terms = json.loads(row[4]) if row[4] else []
        return SemanticEntry(
            source_text=row[0],
            translated_text=row[1],
            source_lang=row[2],
            target_lang=row[3],
            glossary_terms=glossary_terms,
            timestamp=0.0,
            usage_count=row[5],
            quality_score=row[6],
            embedding=None,
            context=row[7] or "",
        )

    def delete_translation(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        glossary_version: Optional[int] = None,
        model: Optional[str] = None,
    ) -> None:
        key = SQLiteSemanticMemory._make_key(
            source_text,
            source_lang,
            target_lang,
            glossary_version=glossary_version,
            model=model,
        )
        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM semantic_translations WHERE hash=%s", (key,))
            conn.commit()

    # ------------------------------------------------------------------
    def find_similar(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        threshold: float = 0.75,
        limit: int = 5,
    ) -> List[SimilarTranslation]:
        if not self._embedding_client:
            return []
        vectors = self._embedding_client.create_vectors([source_text])
        if not vectors:
            return []
        query_vector = vectors[0]

        query, params = self._build_similarity_query(limit)
        params = (
            source_lang,
            target_lang,
            query_vector,
            query_vector,
            limit,
        )

        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()

        results: List[SimilarTranslation] = []
        for row in rows:
            similarity = float(row[6])
            if similarity < threshold:
                continue
            glossary_terms = json.loads(row[4]) if row[4] else []
            entry = SemanticEntry(
                source_text=row[0],
                translated_text=row[1],
                source_lang=row[2],
                target_lang=row[3],
                glossary_terms=glossary_terms,
                timestamp=0.0,
                usage_count=row[5],
                quality_score=1.0,
                embedding=None,
                context="",
            )
            results.append(SimilarTranslation(entry=entry, similarity=similarity, exact_match=False))

        return results[:limit]

    def _build_similarity_query(self, limit: int) -> Tuple[str, tuple]:
        query = (
            "SELECT source_text, translated_text, source_lang, target_lang, glossary_terms, usage_count,"
            " 1 - (embedding <=> %s) AS similarity "
            "FROM semantic_translations "
            "WHERE source_lang = %s AND target_lang = %s "
            "ORDER BY embedding <=> %s LIMIT %s"
        )
        return query, ()

    def get_rag_examples(
        self,
        query_text: str,
        source_lang: str,
        target_lang: str,
        limit: int = 5,
        min_similarity: float = 0.7,
    ) -> List[Tuple[str, str, float]]:
        similar = self.find_similar(
            query_text,
            source_lang,
            target_lang,
            threshold=min_similarity,
            limit=limit,
        )
        return [
            (s.entry.source_text, s.entry.translated_text, s.similarity) for s in similar
        ]

    def get_few_shot_examples(
        self,
        source_lang: str,
        target_lang: str,
        limit: int = 5,
        min_quality: float = 0.8,
    ) -> List[Tuple[str, str]]:
        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT source_text, translated_text
                FROM semantic_translations
                WHERE source_lang=%s AND target_lang=%s AND quality_score >= %s
                ORDER BY quality_score DESC, usage_count DESC
                LIMIT %s
                """,
                (source_lang, target_lang, min_quality, limit),
            )
            rows = cur.fetchall()
        return [(row[0], row[1]) for row in rows]

    def save(self) -> None:
        return None

    # ------------------------------------------------------------------
    def suggest_glossary_term(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        confidence: float = 0.5,
        context: str = "",
    ) -> None:
        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO term_suggestions
                    (source_text, translated_text, source_lang, target_lang, frequency, confidence, contexts)
                VALUES(%s, %s, %s, %s, 1, %s, %s)
                ON CONFLICT (source_text, source_lang, target_lang) DO UPDATE
                SET frequency = term_suggestions.frequency + 1,
                    confidence = (term_suggestions.confidence + EXCLUDED.confidence)/2
                """,
                (
                    source_text,
                    translated_text,
                    source_lang,
                    target_lang,
                    confidence,
                    json.dumps([context]) if context else json.dumps([]),
                ),
            )
            conn.commit()

    def get_glossary_suggestions(
        self,
        min_frequency: int = 3,
        min_confidence: float = 0.7,
    ) -> List[Dict]:
        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT source_text, translated_text, source_lang, target_lang, frequency, confidence, contexts
                FROM term_suggestions
                WHERE frequency >= %s AND confidence >= %s
                ORDER BY frequency DESC, confidence DESC
                """,
                (min_frequency, min_confidence),
            )
            rows = cur.fetchall()
        suggestions = []
        for row in rows:
            ctx = json.loads(row[6]) if row[6] else []
            suggestions.append(
                {
                    "source_text": row[0],
                    "translated_text": row[1],
                    "source_lang": row[2],
                    "target_lang": row[3],
                    "frequency": row[4],
                    "confidence": row[5],
                    "contexts": ctx,
                }
            )
        return suggestions

    def get_metadata(self, key: str) -> Optional[str]:
        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT value FROM metadata WHERE key=%s", (key,))
            row = cur.fetchone()
        return row[0] if row else None

    def set_metadata(self, key: str, value: str) -> None:
        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO metadata(key, value)
                VALUES(%s, %s)
                ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value
                """,
                (key, value),
            )
            conn.commit()

    def get_statistics(self) -> Dict:
        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM semantic_translations")
            total = cur.fetchone()[0]
            cur.execute("SELECT SUM(usage_count) FROM semantic_translations")
            total_usage = cur.fetchone()[0] or 0
        return {
            "total_entries": total,
            "total_usage": total_usage,
            "language_pairs": {},
            "cache_size": 0,
            "embeddings_enabled": bool(self._embedding_client),
        }


__all__ = ["SemanticTranslationMemoryPG"]
