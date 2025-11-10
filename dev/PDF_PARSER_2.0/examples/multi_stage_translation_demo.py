#!/usr/bin/env python3
"""
Multi-Stage Translation Pipeline Demo

This demo shows how to use the new multi-stage translation system with
comprehensive glossary integration for Russian ↔ English ↔ French translations.

Features demonstrated:
1. Multi-stage pipeline with glossary integration
2. Advanced term matching and extraction
3. Translation quality verification
4. Universal language routing
5. Multi-language translation
"""

import os
from pathlib import Path

# Add parent directory to path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from kps.translation import (
    AdvancedGlossaryMatcher,
    GlossaryManager,
    LanguageRouter,
    MultiStageTranslationPipeline,
    PipelineConfig,
    TranslationOrchestrator,
    TranslationSegment,
    TranslationVerifier,
)


def demo_basic_translation():
    """Demo 1: Basic multi-stage translation."""
    print("=" * 80)
    print("DEMO 1: Basic Multi-Stage Translation")
    print("=" * 80)

    # Initialize components
    glossary = GlossaryManager()
    orchestrator = TranslationOrchestrator(model="gpt-4o-mini")
    pipeline = MultiStageTranslationPipeline(
        orchestrator=orchestrator, glossary_manager=glossary
    )

    # Create sample segments
    segments = [
        TranslationSegment(
            segment_id="seg1",
            text="Вяжите 2вм лиц в конце каждого ряда.",
            placeholders={},
        ),
        TranslationSegment(
            segment_id="seg2",
            text="Используйте круговые спицы 4 мм.",
            placeholders={},
        ),
    ]

    print("\nSource text (Russian):")
    for seg in segments:
        print(f"  {seg.segment_id}: {seg.text}")

    # Translate to English
    print("\nTranslating to English...")
    result = pipeline.translate(segments=segments, target_language="en")

    print(f"\nDetected source language: {result.detected_source_language}")
    print(f"Quality score: {result.average_quality:.2%}")
    print(f"Terms found: {result.total_terms_found}")
    print(f"Terms verified: {result.total_terms_verified}")
    print(f"Cost: ${result.total_cost:.4f}")

    print("\nTranslated segments:")
    for i, text in enumerate(result.segments):
        print(f"  {segments[i].segment_id}: {text}")

    print("\nTerm analysis:")
    for analysis in result.analyses:
        if analysis.matched_terms:
            print(f"  {analysis.segment_id}:")
            for term in analysis.matched_terms:
                print(
                    f"    - '{term.source_text}' → '{term.target_text}' (confidence: {term.confidence:.2f})"
                )


def demo_advanced_term_matching():
    """Demo 2: Advanced term matching strategies."""
    print("\n" + "=" * 80)
    print("DEMO 2: Advanced Term Matching")
    print("=" * 80)

    glossary = GlossaryManager()
    matcher = AdvancedGlossaryMatcher(glossary)

    # Test text with various terms
    text = "Наберите 60 петель. Вяжите резинку 1x1 на протяжении 5 см. Затем вяжите лицевой гладью."

    print(f"\nText: {text}")
    print("\nFinding glossary terms...")

    occurrences = matcher.find_terms(text, "ru", "en")

    print(f"\nFound {len(occurrences)} terms:")
    for occ in occurrences:
        print(
            f"  - '{occ.matched_text}' → '{occ.entry.en}' "
            f"(strategy: {occ.strategy}, confidence: {occ.confidence:.2f})"
        )

    # Get statistics
    stats = matcher.get_term_statistics(text, "ru", "en")
    print(f"\nStatistics:")
    print(f"  Total occurrences: {stats['total_occurrences']}")
    print(f"  Unique terms: {stats['unique_terms']}")
    print(f"  Coverage: {stats['coverage']:.2%}")
    print(f"  Average confidence: {stats['average_confidence']:.2f}")
    print(f"  By category: {stats['by_category']}")
    print(f"  By strategy: {stats['by_strategy']}")


def demo_translation_verification():
    """Demo 3: Translation quality verification."""
    print("\n" + "=" * 80)
    print("DEMO 3: Translation Quality Verification")
    print("=" * 80)

    glossary = GlossaryManager()
    verifier = TranslationVerifier(glossary, min_quality_threshold=0.8)

    # Sample source and translation
    source_segments = [
        ("seg1", "Вяжите 2вм лиц в конце ряда."),
        ("seg2", "Используйте круговые спицы 4 мм."),
    ]

    # Good translation
    translated_good = [
        ("seg1", "Knit k2tog at the end of the row."),
        ("seg2", "Use 4 mm circular needles."),
    ]

    # Poor translation (missing terms)
    translated_poor = [
        ("seg1", "Knit 2 together in the end of line."),  # Missing "k2tog"
        ("seg2", "Use 4 mm round knitting needles."),  # Missing "circular needles"
    ]

    # Verify good translation
    print("\nVerifying GOOD translation:")
    report_good = verifier.verify_translation(
        source_segments=source_segments,
        translated_segments=translated_good,
        source_lang="ru",
        target_lang="en",
    )

    print(f"  Average quality: {report_good.average_quality:.2%}")
    print(f"  Passed: {report_good.passed_segments}/{report_good.total_segments}")
    print(f"  Total issues: {report_good.total_issues}")

    # Verify poor translation
    print("\nVerifying POOR translation:")
    report_poor = verifier.verify_translation(
        source_segments=source_segments,
        translated_segments=translated_poor,
        source_lang="ru",
        target_lang="en",
    )

    print(f"  Average quality: {report_poor.average_quality:.2%}")
    print(f"  Passed: {report_poor.passed_segments}/{report_poor.total_segments}")
    print(f"  Total issues: {report_poor.total_issues}")

    print("\nIssues found:")
    for seg_ver in report_poor.segments:
        if seg_ver.issues:
            print(f"  {seg_ver.segment_id}:")
            for issue in seg_ver.issues:
                print(
                    f"    - [{issue.severity}] {issue.description}"
                )
                if issue.suggestion:
                    print(f"      Suggestion: {issue.suggestion}")


def demo_multi_language_routing():
    """Demo 4: Universal language routing for multiple languages."""
    print("\n" + "=" * 80)
    print("DEMO 4: Multi-Language Translation Routing")
    print("=" * 80)

    glossary = GlossaryManager()
    orchestrator = TranslationOrchestrator(model="gpt-4o-mini")
    router = LanguageRouter(orchestrator=orchestrator, glossary_manager=glossary)

    # Create sample segments
    segments = [
        TranslationSegment(
            segment_id="seg1",
            text="Вяжите лицевой гладью 10 см.",
            placeholders={},
        ),
    ]

    print("\nSource text (Russian):")
    print(f"  {segments[0].text}")

    # Get supported language pairs
    pairs = router.get_supported_pairs(source_language="ru")
    print(f"\nSupported language pairs from Russian:")
    for pair in pairs:
        glossary_mark = "✓" if pair.glossary_available else "✗"
        print(f"  ru → {pair.target}: glossary {glossary_mark}")

    # Translate to multiple languages
    print("\nTranslating to English and French...")
    result = router.translate_multi_language(
        segments=segments, source_language="ru", target_languages=["en", "fr"]
    )

    print(f"\nSource language: {result.source_language}")
    print(f"Overall quality: {result.overall_quality:.2%}")
    print(f"Total cost: ${result.total_cost:.4f}")
    print(f"Total time: {result.total_time:.2f}s")

    print("\nTranslations:")
    for lang, translation_result in result.results.items():
        print(f"  {lang}: {translation_result.segments[0]}")
        if lang in result.verification_reports:
            report = result.verification_reports[lang]
            print(
                f"      Quality: {report.average_quality:.2%}, Issues: {report.total_issues}"
            )


def demo_configuration_options():
    """Demo 5: Pipeline configuration options."""
    print("\n" + "=" * 80)
    print("DEMO 5: Pipeline Configuration Options")
    print("=" * 80)

    glossary = GlossaryManager()
    orchestrator = TranslationOrchestrator(model="gpt-4o-mini")

    # Strict configuration
    strict_config = PipelineConfig(
        enable_term_extraction=True,
        enable_fuzzy_matching=True,
        enable_verification=True,
        enable_auto_correction=True,
        min_quality_threshold=0.9,  # High quality requirement
        strict_mode=True,  # Fail on warnings
    )

    # Relaxed configuration
    relaxed_config = PipelineConfig(
        enable_term_extraction=True,
        enable_fuzzy_matching=False,  # No fuzzy matching
        enable_verification=False,  # Skip verification
        enable_auto_correction=False,  # No auto-correction
        min_quality_threshold=0.6,  # Lower quality requirement
        strict_mode=False,
    )

    print("\nConfiguration comparison:")
    print("\nStrict config:")
    print(f"  - Fuzzy matching: {strict_config.enable_fuzzy_matching}")
    print(f"  - Verification: {strict_config.enable_verification}")
    print(f"  - Auto-correction: {strict_config.enable_auto_correction}")
    print(f"  - Quality threshold: {strict_config.min_quality_threshold:.0%}")
    print(f"  - Strict mode: {strict_config.strict_mode}")

    print("\nRelaxed config:")
    print(f"  - Fuzzy matching: {relaxed_config.enable_fuzzy_matching}")
    print(f"  - Verification: {relaxed_config.enable_verification}")
    print(f"  - Auto-correction: {relaxed_config.enable_auto_correction}")
    print(f"  - Quality threshold: {relaxed_config.min_quality_threshold:.0%}")
    print(f"  - Strict mode: {relaxed_config.strict_mode}")


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "Multi-Stage Translation Pipeline Demo" + " " * 21 + "║")
    print("╚" + "=" * 78 + "╝")

    # Check if API key is set
    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "\n⚠️  Warning: OPENAI_API_KEY not set. Translation demos will not work."
        )
        print("   Set it with: export OPENAI_API_KEY='your-key-here'\n")
        # Continue with demos that don't require API

    try:
        # Run demos
        # demo_basic_translation()  # Requires API key
        demo_advanced_term_matching()
        demo_translation_verification()
        # demo_multi_language_routing()  # Requires API key
        demo_configuration_options()

        print("\n" + "=" * 80)
        print("Demo completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
