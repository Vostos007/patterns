"""
Comprehensive tests for translation system with semantic memory.

Tests:
1. Basic translation with glossary
2. Semantic search and similarity matching
3. RAG examples retrieval
4. Cache hit scenarios
5. Self-learning behavior
6. Performance benchmarks
"""

import json
import pytest
import sqlite3
import tempfile
from pathlib import Path
from typing import List

from kps.translation import (
    GlossaryTranslator,
    GlossaryManager,
    TranslationMemory,
    SemanticTranslationMemory,
    TranslationOrchestrator,
)
from kps.translation.semantic_memory_pg import SemanticTranslationMemoryPG
from kps.core.unified_pipeline import PipelineConfig, MemoryType, SemanticMemoryBackend
from kps.clients.embeddings import EmbeddingsClient
from scripts.reindex_semantic_memory import reindex_semantic_memory as run_reindex
from scripts.seed_glossary_memory import seed_glossary_memory as run_seed_glossary


class DummyRateLimitError(Exception):
    """Mimic OpenAI 429 errors for retry testing."""

    def __init__(self, message="Rate limit", status=429):
        super().__init__(message)
        self.status = status


class _FakeEmbeddingsEndpoint:
    """Fake OpenAI embeddings endpoint that can fail deterministically."""

    def __init__(self, events, dimension=8, fail_on_calls=None):
        self.events = events
        self.dimension = dimension
        self.fail_on_calls = fail_on_calls or set()
        self._call_index = 0

    def create(self, model, input):
        self.events.append((model, tuple(input)))
        call_index = self._call_index
        self._call_index += 1

        if call_index in self.fail_on_calls:
            # Ensure subsequent retries succeed
            self.fail_on_calls.remove(call_index)
            raise DummyRateLimitError()

        data = []
        for idx, text in enumerate(input):
            vec = [float(idx + len(text))] * self.dimension
            data.append(type("EmbeddingObj", (object,), {"embedding": vec})())

        return type("EmbeddingsResponse", (object,), {"data": data})()


class _FakeOpenAIClient:
    def __init__(self, endpoint):
        self.embeddings = endpoint


class TestEmbeddingsClient:
    def test_embedding_client_round_trip(self):
        events = []
        fake_endpoint = _FakeEmbeddingsEndpoint(events, dimension=6)
        fake_client = _FakeOpenAIClient(fake_endpoint)

        client = EmbeddingsClient(
            model="text-embedding-3-small",
            max_batch=2,
            client=fake_client,
        )

        vectors = client.create_vectors(["foo", "бар", "baz"])

        assert len(vectors) == 3
        assert all(len(vec) == 6 for vec in vectors)
        assert events == [
            ("text-embedding-3-small", ("foo", "бар")),
            ("text-embedding-3-small", ("baz",)),
        ]

    def test_embedding_client_retries_on_rate_limit(self):
        events = []
        fake_endpoint = _FakeEmbeddingsEndpoint(events, dimension=4, fail_on_calls={0})
        fake_client = _FakeOpenAIClient(fake_endpoint)

        client = EmbeddingsClient(
            model="text-embedding-3-small",
            max_batch=4,
            max_retries=2,
            client=fake_client,
        )

        vectors = client.create_vectors(["retry-me"])

        assert len(vectors) == 1
        assert len(vectors[0]) == 4
        # First call failed, second succeeded
        assert len(events) == 2


class _StubEmbeddingsClient:
    def __init__(self, dimension=8):
        self.dimension = dimension
        self.calls = []

    def create_vectors(self, texts):
        self.calls.extend(texts)
        return [[float(len(text))] * self.dimension for text in texts]


class _FakePGCursor:
    def __init__(self, connection):
        self.conn = connection

    def execute(self, query, params=None):
        self.conn.executed.append((query, params))

    def fetchall(self):
        return self.conn.rows

    def fetchone(self):
        if self.conn.fetchone_rows:
            return self.conn.fetchone_rows.pop(0)
        return None


class _FakePGConnection:
    def __init__(self, rows=None, fetchone_rows=None):
        self.rows = rows or []
        self.fetchone_rows = fetchone_rows or []
        self.executed: List = []

    def cursor(self):
        return _FakePGCursor(self)

    def commit(self):
        self.executed.append("commit")

    def close(self):
        pass


class _FakeSemanticMemoryForRAG:
    def __init__(self):
        self.rag_calls: List[float] = []

    def get_translation(self, *args, **kwargs):
        return None

    def get_few_shot_examples(self, *args, **kwargs):
        return []

    def get_rag_examples(
        self,
        query_text: str,
        source_lang: str,
        target_lang: str,
        limit: int,
        min_similarity: float,
    ):
        self.rag_calls.append(min_similarity)
        return [(query_text, target_lang, min_similarity)]

    def add_translation(self, *args, **kwargs):
        return None

    def suggest_glossary_term(self, *args, **kwargs):
        return None

    def get_glossary_suggestions(self, *args, **kwargs):
        return []


class _DummySemanticMemoryPG(SemanticTranslationMemoryPG):
    def _init_db(self):
        # Skip real DDL for tests
        return None


class TestSemanticMemoryEmbeddings:
    def test_semantic_memory_persists_real_embeddings(self, tmp_path):
        db_path = tmp_path / "semantic.db"
        client = _StubEmbeddingsClient(dimension=6)
        memory = SemanticTranslationMemory(
            str(db_path),
            use_embeddings=True,
            embedding_cache_size=4,
            embedding_client=client,
            embedding_dimensions=None,
        )

        memory.add_translation(
            "Провяжите 2 петли вместе",
            "Knit 2 stitches together",
            "ru",
            "en",
            ["k2tog"],
        )

        entry = memory.get_translation("Провяжите 2 петли вместе", "ru", "en")

        assert entry is not None
        assert entry.embedding is not None
        assert len(entry.embedding) == 6
        assert client.calls.count("Провяжите 2 петли вместе") == 1

        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT embedding FROM translations LIMIT 1").fetchone()
        conn.close()
        assert row[0] is not None
        assert len(row[0]) == 6 * 4  # float32 bytes per dim

    def test_embedding_cache_eviction(self, tmp_path):
        db_path = tmp_path / "semantic_cache.db"
        client = _StubEmbeddingsClient(dimension=3)
        memory = SemanticTranslationMemory(
            str(db_path),
            use_embeddings=True,
            embedding_cache_size=2,
            embedding_client=client,
            embedding_dimensions=None,
        )

        memory._get_embedding("alpha", "ru")
        memory._get_embedding("beta", "ru")

        # This should evict "alpha"
        memory._get_embedding("gamma", "ru")

        # Cache hit for beta
        memory._get_embedding("beta", "ru")

        # alpha was evicted, so fetching again triggers another API call
        memory._get_embedding("alpha", "ru")

        assert client.calls == ["alpha", "beta", "gamma", "alpha"]


class TestSemanticMemoryCLI:
    def test_reindex_semantic_memory_cli(self, tmp_path):
        db_path = tmp_path / "semantic_cli.db"
        memory = SemanticTranslationMemory(str(db_path), use_embeddings=False)

        memory.add_translation("A", "A", "ru", "en", ["term_a"])
        memory.add_translation("B", "B", "ru", "en", ["term_b"])

        # Ensure rows start without embeddings
        conn = sqlite3.connect(str(db_path))
        before = conn.execute(
            "SELECT COUNT(*) FROM translations WHERE IFNULL(embedding_version,0) = 0"
        ).fetchone()[0]
        assert before == 2

        processed = run_reindex(
            str(db_path),
            target_version=2,
            batch_size=1,
            embedding_client=_StubEmbeddingsClient(dimension=4),
        )

        assert processed == 2

        row = conn.execute(
            "SELECT embedding, embedding_q16, embedding_version FROM translations LIMIT 1"
        ).fetchone()
        conn.close()

        assert row[0] is not None
        assert row[1] is not None
        assert row[2] == 2


class TestGlossarySeeder:
    def test_seed_glossary_memory_script(self, tmp_path):
        glossary_file = tmp_path / "glossary.yaml"
        glossary_file.write_text(
            """
terms:
  test_term:
    ru: спец символ
    en: special symbol
""",
            encoding="utf-8",
        )

        db_path = tmp_path / "seeded.db"
        seeded = run_seed_glossary(
            str(glossary_file),
            str(db_path),
            embedding_client=_StubEmbeddingsClient(dimension=4),
        )

        assert seeded == 1

        memory = SemanticTranslationMemory(str(db_path), use_embeddings=False)
        entry = memory.get_translation("спец символ", "ru", "en")
        assert entry is not None
        assert memory.get_metadata("glossary_seed:ru:en") is not None


class TestPostgresSemanticMemory:
    def test_similarity_query_has_filters_before_order(self):
        pg = _DummySemanticMemoryPG(
            "postgresql://dummy",
            embedding_client=None,
            connection_factory=lambda: _FakePGConnection(),
        )
        query, _ = pg._build_similarity_query(limit=5)
        query_lower = query.lower()
        assert query_lower.index("where") < query_lower.index("order by")

    def test_find_similar_uses_embedding_client_and_threshold(self):
        rows = [
            (
                "src",
                "tgt",
                "ru",
                "en",
                json.dumps(["k2tog"]),
                5,
                0.92,
            ),
            ("src2", "tgt2", "ru", "en", None, 1, 0.4),
        ]
        connections = iter([_FakePGConnection(rows=rows)])

        def factory():
            return next(connections)

        client = _StubEmbeddingsClient(dimension=4)
        pg = _DummySemanticMemoryPG(
            "postgresql://dummy",
            embedding_client=client,
            connection_factory=factory,
        )

        similar = pg.find_similar("query", "ru", "en", threshold=0.6, limit=5)
        assert len(similar) == 1
        assert similar[0].entry.translated_text == "tgt"
        assert client.calls  # ensure embeddings queried


class TestRAGScoping:
    def test_rag_threshold_adjusts_for_symbol_terms(self):
        orchestrator = MockOrchestrator()
        glossary = MockGlossary()
        memory = _FakeSemanticMemoryForRAG()
        config = type(
            "Cfg",
            (object,),
            {
                "rag_enabled": True,
                "rag_examples_limit": 1,
                "rag_min_similarity": 0.8,
                "special_symbol_min_similarity": 0.5,
            },
        )()

        translator = GlossaryTranslator(
            orchestrator,
            glossary,
            memory=memory,
            config=config,
        )

        segments = [
            TranslationSegment("1", "⟨кромка⟩ держите маркер", {}),
            TranslationSegment("2", "Провяжите 2 петли вместе", {}),
        ]

        translator.translate(segments, target_language="en", source_language="ru")

        assert memory.rag_calls == [0.5, 0.8]
from kps.translation.orchestrator import TranslationSegment


# Mock Orchestrator for testing
class MockOrchestrator:
    """Mock orchestrator for testing without API calls."""

    def __init__(self):
        self.call_count = 0
        self.translations = {
            "Провяжите 2 петли вместе": "Knit 2 stitches together",
            "Закройте все петли": "Bind off all stitches",
            "Повторяйте ряд": "Repeat row",
            "Вяжите лицевыми": "Knit",
        }

    def detect_language(self, text):
        # Simple detection
        if any(ord(c) > 1000 for c in text):  # Cyrillic
            return "ru"
        return "en"

    def translate_batch(self, segments, target_languages, glossary_context=""):
        self.call_count += 1

        # Mock translation
        translations = {}
        for lang in target_languages:
            segments_trans = []
            for seg in segments:
                # Try to find in mock translations
                trans = self.translations.get(seg.text, f"[{seg.text}]")
                segments_trans.append(trans)

            translations[lang] = type("obj", (object,), {"segments": segments_trans})()

        result = type(
            "obj",
            (object,),
            {"translations": translations, "total_cost": 0.001 * len(segments)},
        )()

        return result


# Mock GlossaryManager for testing
class MockGlossary:
    """Mock glossary for testing."""

    def __init__(self):
        self.entries = [
            type(
                "Entry",
                (object,),
                {
                    "key": "k2tog",
                    "ru": "2 петли вместе",
                    "en": "k2tog",
                    "category": "stitch",
                },
            )(),
            type(
                "Entry",
                (object,),
                {
                    "key": "bind_off",
                    "ru": "закройте петли",
                    "en": "bind off",
                    "category": "technique",
                },
            )(),
            type(
                "Entry",
                (object,),
                {
                    "key": "row",
                    "ru": "ряд",
                    "en": "row",
                    "category": "structure",
                },
            )(),
            type(
                "Entry",
                (object,),
                {
                    "key": "special_symbol",
                    "ru": "⟨кромка⟩",
                    "en": "selvage marker",
                    "category": "symbol",
                },
            )(),
        ]

    def get_all_entries(self):
        return self.entries

    def build_context_for_prompt(self, source_lang, target_lang, selected_entries):
        context = "Glossary:\n"
        for entry in selected_entries:
            source = getattr(entry, source_lang, "")
            target = getattr(entry, target_lang, "")
            context += f"- {source} → {target}\n"
        return context

    def lookup(self, key, source_lang="ru", target_lang="en"):
        for entry in self.entries:
            if entry.key == key:
                return type(
                    "Match",
                    (object,),
                    {
                        "key": key,
                        "source_text": getattr(entry, source_lang, ""),
                        "target_text": getattr(entry, target_lang, ""),
                        "category": entry.category,
                    },
                )()
        return None


class TestBasicTranslation:
    """Test basic translation functionality."""

    def test_simple_translation(self, tmp_path):
        """Test simple translation without memory."""
        orchestrator = MockOrchestrator()
        glossary = MockGlossary()

        translator = GlossaryTranslator(orchestrator, glossary)

        segments = [
            TranslationSegment("1", "Провяжите 2 петли вместе", {}),
        ]

        result = translator.translate(segments, target_language="en")

        assert result.source_language == "ru"
        assert result.target_language == "en"
        assert len(result.segments) == 1
        assert result.terms_found > 0  # Should find glossary terms

    def test_glossary_term_matching(self):
        """Test that glossary terms are found in text."""
        orchestrator = MockOrchestrator()
        glossary = MockGlossary()

        translator = GlossaryTranslator(orchestrator, glossary)

        # Test finding terms
        terms = translator._find_terms("Провяжите 2 петли вместе", "ru", "en")

        assert len(terms) > 0  # Should find at least one term


class TestTranslationMemory:
    """Test translation memory and caching."""

    def test_cache_hit(self, tmp_path):
        """Test that repeated translations use cache."""
        cache_file = tmp_path / "cache.json"

        orchestrator = MockOrchestrator()
        glossary = MockGlossary()
        memory = TranslationMemory(str(cache_file))

        translator = GlossaryTranslator(orchestrator, glossary, memory=memory)

        segments = [
            TranslationSegment("1", "Провяжите 2 петли вместе", {}),
        ]

        # First translation - should call API
        result1 = translator.translate(segments, target_language="en")
        api_calls_1 = orchestrator.call_count

        # Second translation - should use cache
        result2 = translator.translate(segments, target_language="en")
        api_calls_2 = orchestrator.call_count

        assert result2.cached_segments == 1  # Should be cached
        assert api_calls_2 == api_calls_1  # No new API calls

    def test_partial_cache_hit(self, tmp_path):
        """Test mixed cached and new translations."""
        cache_file = tmp_path / "cache.json"

        orchestrator = MockOrchestrator()
        glossary = MockGlossary()
        memory = TranslationMemory(str(cache_file))

        translator = GlossaryTranslator(orchestrator, glossary, memory=memory)

        # First: translate 2 segments
        segments1 = [
            TranslationSegment("1", "Провяжите 2 петли вместе", {}),
            TranslationSegment("2", "Закройте все петли", {}),
        ]
        result1 = translator.translate(segments1, target_language="en")

        # Second: 1 cached + 1 new
        segments2 = [
            TranslationSegment("1", "Провяжите 2 петли вместе", {}),  # Cached
            TranslationSegment("3", "Повторяйте ряд", {}),  # New
        ]
        result2 = translator.translate(segments2, target_language="en")

        assert result2.cached_segments == 1  # One from cache
        assert len(result2.segments) == 2  # Both returned

    def test_memory_persistence(self, tmp_path):
        """Test that memory persists across sessions."""
        cache_file = tmp_path / "cache.json"

        orchestrator = MockOrchestrator()
        glossary = MockGlossary()

        # Session 1: translate and save
        memory1 = TranslationMemory(str(cache_file))
        translator1 = GlossaryTranslator(orchestrator, glossary, memory=memory1)

        segments = [TranslationSegment("1", "Провяжите 2 петли вместе", {})]
        translator1.translate(segments, target_language="en")
        translator1.save_memory()

        # Session 2: load and use cache
        memory2 = TranslationMemory(str(cache_file))
        translator2 = GlossaryTranslator(orchestrator, glossary, memory=memory2)

        result = translator2.translate(segments, target_language="en")

        assert result.cached_segments == 1  # Should use saved cache

    def test_cached_source_language_entries_are_invalidated(self, tmp_path):
        """Ensure cached Russian text is evicted and retranslated."""

        cache_file = tmp_path / "cache.json"
        orchestrator = MockOrchestrator()
        glossary = MockGlossary()
        memory = TranslationMemory(str(cache_file))

        # Seed cache with bad translation (still Russian)
        memory.add_translation(
            "Провяжите 2 петли вместе",
            "Провяжите 2 петли вместе",
            "ru",
            "en",
            ["k2tog"],
        )

        translator = GlossaryTranslator(orchestrator, glossary, memory=memory)
        segments = [TranslationSegment("1", "Провяжите 2 петли вместе", {})]

        result = translator.translate(segments, target_language="en", source_language="ru")

        assert result.cached_segments == 0
        assert result.segments[0] == "Knit 2 stitches together"

        # Cache should now contain the corrected translation
        cached = memory.get_translation("Провяжите 2 петли вместе", "ru", "en")
        assert cached is not None
        assert cached.translated_text == "Knit 2 stitches together"


class TestSemanticMemory:
    """Test semantic memory with similarity matching."""

    def test_exact_match(self, tmp_path):
        """Test exact match in semantic memory."""
        db_file = tmp_path / "semantic.db"

        memory = SemanticTranslationMemory(
            str(db_file),
            use_embeddings=True,
            embedding_client=_StubEmbeddingsClient(dimension=6),
            embedding_dimensions=None,
        )

        # Add translation
        memory.add_translation(
            "Провяжите 2 петли вместе",
            "Knit 2 stitches together",
            "ru",
            "en",
            ["k2tog"],
        )

        # Exact match should work
        result = memory.get_translation("Провяжите 2 петли вместе", "ru", "en")

        assert result is not None
        assert result.translated_text == "Knit 2 stitches together"

    def test_semantic_similarity(self, tmp_path):
        """Test finding similar translations."""
        db_file = tmp_path / "semantic.db"

        memory = SemanticTranslationMemory(
            str(db_file),
            use_embeddings=True,
            embedding_client=_StubEmbeddingsClient(dimension=6),
            embedding_dimensions=None,
        )

        # Add original
        memory.add_translation(
            "Провяжите 2 петли вместе",
            "Knit 2 stitches together",
            "ru",
            "en",
            ["k2tog"],
        )

        # Search for similar (slightly different text)
        similar = memory.find_similar(
            "Провяжите две петли вместе", "ru", "en", threshold=0.70, limit=5
        )

        # Should find at least one result
        assert len(similar) > 0

    def test_rag_examples(self, tmp_path):
        """Test RAG example retrieval."""
        db_file = tmp_path / "semantic.db"

        memory = SemanticTranslationMemory(
            str(db_file),
            use_embeddings=True,
            embedding_client=_StubEmbeddingsClient(dimension=6),
            embedding_dimensions=None,
        )

        # Add several translations
        translations = [
            ("Провяжите 2 петли вместе", "Knit 2 stitches together", ["k2tog"]),
            ("Закройте все петли", "Bind off all stitches", ["bind_off"]),
            ("Повторяйте ряд", "Repeat row", ["row"]),
        ]

        for source, target, terms in translations:
            memory.add_translation(source, target, "ru", "en", terms)

        # Get RAG examples
        examples = memory.get_rag_examples("Вяжите лицевыми", "ru", "en", limit=3)

        # Should return some examples
        assert isinstance(examples, list)


class TestSelfLearning:
    """Test self-learning behavior."""

    def test_usage_count_increment(self, tmp_path):
        """Test that usage count increases on reuse."""
        cache_file = tmp_path / "cache.json"

        orchestrator = MockOrchestrator()
        glossary = MockGlossary()
        memory = TranslationMemory(str(cache_file))

        translator = GlossaryTranslator(orchestrator, glossary, memory=memory)

        segments = [TranslationSegment("1", "Провяжите 2 петли вместе", {})]

        # Translate multiple times
        for _ in range(3):
            translator.translate(segments, target_language="en")

        # Check usage count increased
        cached = memory.get_translation(segments[0].text, "ru", "en")
        assert cached.usage_count > 1

    def test_statistics_tracking(self, tmp_path):
        """Test statistics collection."""
        cache_file = tmp_path / "cache.json"

        orchestrator = MockOrchestrator()
        glossary = MockGlossary()
        memory = TranslationMemory(str(cache_file))

        translator = GlossaryTranslator(orchestrator, glossary, memory=memory)

        # Translate several segments
        segments = [
            TranslationSegment("1", "Провяжите 2 петли вместе", {}),
            TranslationSegment("2", "Закройте все петли", {}),
        ]
        translator.translate(segments, target_language="en")

        # Get statistics
        stats = translator.get_statistics()

        assert stats is not None
        assert stats["total_entries"] == 2
        assert stats["total_usage"] >= 2


class TestPerformance:
    """Test performance characteristics."""

    def test_cache_speedup(self, tmp_path):
        """Test that cache provides speedup."""
        import time

        cache_file = tmp_path / "cache.json"

        orchestrator = MockOrchestrator()
        glossary = MockGlossary()
        memory = TranslationMemory(str(cache_file))

        translator = GlossaryTranslator(orchestrator, glossary, memory=memory)

        segments = [TranslationSegment("1", "Провяжите 2 петли вместе", {})]

        # First translation
        start = time.time()
        translator.translate(segments, target_language="en")
        time_first = time.time() - start

        # Second translation (cached)
        start = time.time()
        translator.translate(segments, target_language="en")
        time_cached = time.time() - start

        # Cached should be faster (or at least not slower)
        assert time_cached <= time_first * 1.1  # Allow 10% margin


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_segments(self):
        """Test handling of empty segment list."""
        orchestrator = MockOrchestrator()
        glossary = MockGlossary()

        translator = GlossaryTranslator(orchestrator, glossary)

        result = translator.translate([], target_language="en")

        assert len(result.segments) == 0
        assert result.total_cost == 0.0

    def test_no_glossary_terms(self):
        """Test translation with no matching glossary terms."""
        orchestrator = MockOrchestrator()
        glossary = MockGlossary()

        translator = GlossaryTranslator(orchestrator, glossary)

        segments = [TranslationSegment("1", "Совершенно другой текст", {})]

        result = translator.translate(segments, target_language="en")

        assert len(result.segments) == 1
        assert result.terms_found == 0  # No glossary terms found

    def test_unicode_handling(self):
        """Test proper unicode handling."""
        orchestrator = MockOrchestrator()
        glossary = MockGlossary()

        translator = GlossaryTranslator(orchestrator, glossary)

        # Text with various unicode characters
        segments = [
            TranslationSegment("1", "Провяжите № 2 петли вместе ©", {}),
        ]

        result = translator.translate(segments, target_language="en")

        assert len(result.segments) == 1
        # Should not crash on unicode


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
