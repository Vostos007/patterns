"""
Enhanced Translation Orchestrator Demo for KPS v2.0

Demonstrates production features:
- Batch processing (50 segments per batch)
- Progress tracking with callbacks
- Token counting and cost estimation
- Retry logic with exponential backoff
- Glossary integration with smart term selection
"""

from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kps.translation import (
    TranslationOrchestrator,
    TranslationSegment,
    TranslationProgress,
)
from kps.translation.glossary import GlossaryManager


def progress_callback(progress: TranslationProgress):
    """
    Progress callback to track translation status.

    Called after each batch is completed.
    """
    print(f"\n[Progress Update]")
    print(f"  Batch: {progress.current_batch}/{progress.total_batches}")
    print(f"  Segments: {progress.segments_completed}/{progress.total_segments}")
    print(f"  Language: {progress.current_language}")
    print(f"  Estimated cost: ${progress.estimated_cost:.4f}")
    print(f"  Elapsed: {progress.elapsed_time:.1f}s")
    print(f"  ETA: {progress.estimated_time_remaining:.1f}s")


def demo_basic_batching():
    """Demo 1: Basic batch processing without glossary."""
    print("\n" + "=" * 60)
    print("DEMO 1: Basic Batch Processing")
    print("=" * 60)

    # Create 120 test segments (will create 3 batches of 50, 50, 20)
    segments = []
    for i in range(120):
        segment = TranslationSegment(
            segment_id=f"p.materials.{i:03d}.seg0",
            text=f"Пряжа: 100% шерсть, спицы 4 мм. Образец {i+1}.",
            placeholders={},
        )
        segments.append(segment)

    # Initialize orchestrator with batch size 50
    orchestrator = TranslationOrchestrator(
        model="gpt-4o-mini",
        max_batch_size=50,
        max_retries=3,
        retry_delay=1.0,
    )

    print(f"\nTranslating {len(segments)} segments...")
    print(f"Batch size: {orchestrator.max_batch_size}")
    print(f"Expected batches: {len(segments) // orchestrator.max_batch_size + 1}")

    # Translate with batching
    result = orchestrator.translate_with_batching(
        segments=segments,
        target_languages=["en", "fr"],
        progress_callback=progress_callback,
    )

    # Print final results
    print("\n" + "-" * 60)
    print("[Final Results]")
    print(f"  Source language detected: {result.detected_source_language}")
    print(f"  Total input tokens: {result.total_input_tokens:,}")
    print(f"  Total output tokens: {result.total_output_tokens:,}")
    print(f"  Total cost: ${result.total_cost:.4f}")

    for lang, translation in result.translations.items():
        print(f"\n  {lang.upper()} Translation:")
        print(f"    Segments translated: {len(translation.segments)}")
        print(f"    Sample: {translation.segments[0][:80]}...")


def demo_glossary_integration():
    """Demo 2: Batch processing with glossary integration."""
    print("\n" + "=" * 60)
    print("DEMO 2: Batch Processing with Glossary")
    print("=" * 60)

    # Create segments with knitting terminology
    segments = [
        TranslationSegment(
            segment_id="p.intro.001.seg0",
            text="Наберите 60 п. на спицы 4 мм.",
            placeholders={},
        ),
        TranslationSegment(
            segment_id="p.intro.002.seg0",
            text="Вяжите резинкой 1x1 (1 лиц., 1 изн.) 10 рядов.",
            placeholders={},
        ),
        TranslationSegment(
            segment_id="p.pattern.001.seg0",
            text="Р. 1: *2 лиц., 2 изн.*, повторять от * до * до конца ряда.",
            placeholders={},
        ),
        TranslationSegment(
            segment_id="p.pattern.002.seg0",
            text="Убавить 4 п. равномерно по ряду (56 п.).",
            placeholders={},
        ),
        TranslationSegment(
            segment_id="p.gauge.001.seg0",
            text="Плотность вязания: 22 п. x 30 р. = 10 x 10 см.",
            placeholders={},
        ),
    ]

    # Initialize glossary manager
    glossary = GlossaryManager()
    print(f"\nGlossary loaded:")
    stats = glossary.get_statistics()
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  By category: {stats['by_category']}")

    # Initialize orchestrator
    orchestrator = TranslationOrchestrator(
        model="gpt-4o-mini",
        max_batch_size=50,
    )

    print(f"\nTranslating {len(segments)} segments with glossary...")

    # Translate with glossary
    result = orchestrator.translate_with_batching(
        segments=segments,
        target_languages=["en"],
        glossary_manager=glossary,
        progress_callback=progress_callback,
    )

    # Print results
    print("\n" + "-" * 60)
    print("[Translation Results]")

    en_translation = result.translations["en"]
    for i, (original, translated) in enumerate(
        zip(segments, en_translation.segments), 1
    ):
        print(f"\n  [{i}] RU: {original.text}")
        print(f"      EN: {translated}")

    print(f"\n  Total cost: ${result.total_cost:.4f}")


def demo_retry_logic():
    """Demo 3: Retry logic with exponential backoff (simulated)."""
    print("\n" + "=" * 60)
    print("DEMO 3: Retry Logic Demo")
    print("=" * 60)

    # Create a small segment set
    segments = [
        TranslationSegment(
            segment_id="p.test.001.seg0",
            text="Пряжа: 50% шерсть, 50% акрил.",
            placeholders={},
        ),
    ]

    # Initialize with aggressive retry settings
    orchestrator = TranslationOrchestrator(
        model="gpt-4o-mini",
        max_retries=3,
        retry_delay=0.5,  # 0.5s initial delay
    )

    print("\nRetry configuration:")
    print(f"  Max retries: {orchestrator.max_retries}")
    print(f"  Initial delay: {orchestrator.retry_delay}s")
    print(f"  Backoff strategy: Exponential (2x)")
    print(f"  Retry on: 429 (Rate Limit), 500, 502, 503 (Transient)")

    # In production, rate limits or transient errors would trigger retries
    # For demo, we just show the configuration
    print("\n  Note: Retries happen automatically on rate limits or transient errors.")
    print("  Example retry sequence:")
    print("    Attempt 1: Failed (429 Rate Limit)")
    print("    Wait 0.5s...")
    print("    Attempt 2: Failed (429 Rate Limit)")
    print("    Wait 1.0s...")
    print("    Attempt 3: Success!")


def demo_cost_estimation():
    """Demo 4: Token counting and cost estimation."""
    print("\n" + "=" * 60)
    print("DEMO 4: Cost Estimation")
    print("=" * 60)

    orchestrator = TranslationOrchestrator(model="gpt-4o-mini")

    # Test token estimation
    test_texts = [
        ("Short text", "Спицы 4 мм"),
        ("Medium text", "Наберите 60 петель на спицы 4 мм и вяжите резинкой."),
        (
            "Long text",
            "Наберите 60 петель на спицы 4 мм. Вяжите резинкой 1x1 (1 лицевая, 1 изнаночная) 10 рядов. "
            "Затем перейдите на основной узор и вяжите до достижения нужной длины.",
        ),
    ]

    print("\n[Token Estimation]")
    for label, text in test_texts:
        tokens = orchestrator._count_tokens(text, "gpt-4o-mini")
        print(f"  {label}: {len(text)} chars → ~{tokens} tokens")

    # Show pricing tiers
    print("\n[Model Pricing (per 1M tokens)]")
    for model, prices in orchestrator.MODEL_PRICING.items():
        print(f"  {model}:")
        print(f"    Input:  ${prices['input']:.2f}")
        print(f"    Output: ${prices['output']:.2f}")

    # Calculate costs for different scenarios
    print("\n[Cost Scenarios]")
    scenarios = [
        ("Small doc (1000 segments)", 1000, 2000),
        ("Medium doc (5000 segments)", 5000, 10000),
        ("Large doc (20000 segments)", 20000, 40000),
    ]

    for label, input_tokens, output_tokens in scenarios:
        cost = orchestrator._calculate_cost(input_tokens, output_tokens, "gpt-4o-mini")
        print(f"  {label}:")
        print(f"    Input tokens: {input_tokens:,}")
        print(f"    Output tokens: {output_tokens:,}")
        print(f"    Estimated cost: ${cost:.4f}")


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("KPS v2.0 - Enhanced Translation Orchestrator Demos")
    print("=" * 60)

    # Note: Some demos require OpenAI API key
    print("\nNote: Demos 1-2 require OPENAI_API_KEY environment variable.")
    print("Demos 3-4 demonstrate configuration without making API calls.")

    try:
        # Demo 1: Basic batching (requires API key)
        # Uncomment to run:
        # demo_basic_batching()

        # Demo 2: Glossary integration (requires API key)
        # Uncomment to run:
        # demo_glossary_integration()

        # Demo 3: Retry logic (no API call)
        demo_retry_logic()

        # Demo 4: Cost estimation (no API call)
        demo_cost_estimation()

        print("\n" + "=" * 60)
        print("All demos completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure OPENAI_API_KEY is set for API-based demos.")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
