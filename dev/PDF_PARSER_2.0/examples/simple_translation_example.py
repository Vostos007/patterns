"""
Simple and fast glossary-driven translation example.

This example shows how to use the simplified GlossaryTranslator
for efficient translation with glossary terms.
"""

from kps.translation import GlossaryTranslator, GlossaryManager, TranslationOrchestrator
from kps.translation.orchestrator import TranslationSegment


def main():
    """Run simple translation example."""

    # Initialize components
    print("Initializing translation system...")
    orchestrator = TranslationOrchestrator()
    glossary = GlossaryManager()

    # Load glossary
    glossary.load_from_yaml("glossary.yaml")
    print(f"Loaded {len(glossary.get_all_entries())} glossary terms")

    # Create simple translator
    translator = GlossaryTranslator(
        orchestrator=orchestrator,
        glossary_manager=glossary,
        max_glossary_terms=100  # Limit for prompt efficiency
    )

    # Example text with glossary terms
    segments = [
        TranslationSegment(
            segment_id="seg1",
            text="Провяжите 2 лиц вместе в конце ряда.",
            metadata={},
        ),
        TranslationSegment(
            segment_id="seg2",
            text="Повторяйте с 1-го по 4-й ряд.",
            metadata={},
        ),
        TranslationSegment(
            segment_id="seg3",
            text="Закройте все петли лицевыми.",
            metadata={},
        ),
    ]

    print("\nTranslating Russian → English...")

    # Translate (source language auto-detected)
    result = translator.translate(
        segments=segments,
        target_language="en"
    )

    # Show results
    print(f"\nSource language: {result.source_language}")
    print(f"Target language: {result.target_language}")
    print(f"Glossary terms found: {result.terms_found}")
    print(f"Translation cost: ${result.total_cost:.4f}")
    print("\nTranslated segments:")

    for i, (original, translated) in enumerate(zip(segments, result.segments), 1):
        print(f"\n{i}. Original:   {original.text}")
        print(f"   Translated: {translated}")

    # Example: Russian → French
    print("\n" + "="*60)
    print("Translating Russian → French...")

    result_fr = translator.translate(
        segments=segments,
        target_language="fr",
        source_language="ru"  # Can specify explicitly
    )

    print(f"\nGlossary terms found: {result_fr.terms_found}")
    print(f"Translation cost: ${result_fr.total_cost:.4f}")
    print("\nTranslated segments:")

    for i, translated in enumerate(result_fr.segments, 1):
        print(f"{i}. {translated}")

    print("\n" + "="*60)
    print("✓ Translation complete!")
    print(f"Total cost: ${result.total_cost + result_fr.total_cost:.4f}")


if __name__ == "__main__":
    main()
