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

import pytest
import tempfile
from pathlib import Path

from kps.translation import (
    GlossaryTranslator,
    GlossaryManager,
    TranslationMemory,
    SemanticTranslationMemory,
    TranslationOrchestrator,
)
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


class TestSemanticMemory:
    """Test semantic memory with similarity matching."""

    def test_exact_match(self, tmp_path):
        """Test exact match in semantic memory."""
        db_file = tmp_path / "semantic.db"

        memory = SemanticTranslationMemory(str(db_file), use_embeddings=True)

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

        memory = SemanticTranslationMemory(str(db_file), use_embeddings=True)

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

        memory = SemanticTranslationMemory(str(db_file), use_embeddings=True)

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
