# Translation Orchestrator - Quick Reference

## Installation

No additional dependencies required beyond existing KPS v2.0 setup.

## Quick Start

```python
from kps.translation import TranslationOrchestrator, TranslationSegment, TranslationProgress

# Create orchestrator
orchestrator = TranslationOrchestrator(model="gpt-4o-mini")

# Create segments
segments = [
    TranslationSegment(
        segment_id="p.intro.001.seg0",
        text="Пряжа: 100% шерсть, спицы 4 мм.",
        placeholders={},
    ),
]

# Translate
result = orchestrator.translate_with_batching(
    segments=segments,
    target_languages=["en", "fr"],
)

# Get results
print(f"Cost: ${result.total_cost:.4f}")
print(f"EN: {result.translations['en'].segments[0]}")
```

## Key Features

| Feature | Default | Configuration |
|---------|---------|---------------|
| Batch Size | 50 segments | `max_batch_size=50` |
| Max Retries | 3 attempts | `max_retries=3` |
| Retry Delay | 1.0s | `retry_delay=1.0` |
| Model | gpt-4o-mini | `model="gpt-4o-mini"` |

## Progress Tracking

```python
def progress(p: TranslationProgress):
    print(f"[{p.current_batch}/{p.total_batches}] ${p.estimated_cost:.4f}")

result = orchestrator.translate_with_batching(
    segments=segments,
    target_languages=["en"],
    progress_callback=progress,
)
```

## Glossary Integration

```python
from kps.translation.glossary import GlossaryManager

glossary = GlossaryManager()  # Auto-loads from config/glossaries/

result = orchestrator.translate_with_batching(
    segments=segments,
    target_languages=["en"],
    glossary_manager=glossary,
)
```

## Cost Estimation

| Model | Input ($/1M) | Output ($/1M) | 1K Segments (est.) |
|-------|--------------|---------------|--------------------|
| gpt-4o-mini | $0.15 | $0.60 | $0.0014 |
| gpt-4o | $2.50 | $10.00 | $0.0225 |
| gpt-4-turbo | $10.00 | $30.00 | $0.0900 |

## Common Patterns

### Pattern 1: Translate with Progress

```python
def show_progress(p: TranslationProgress):
    percent = (p.current_batch / p.total_batches) * 100
    print(f"[{percent:.0f}%] {p.current_language} - ${p.estimated_cost:.4f}")

result = orchestrator.translate_with_batching(
    segments=segments,
    target_languages=["en", "fr"],
    progress_callback=show_progress,
)
```

### Pattern 2: Translate with Glossary

```python
glossary = GlossaryManager()

result = orchestrator.translate_with_batching(
    segments=segments,
    target_languages=["en"],
    glossary_manager=glossary,
)
```

### Pattern 3: Custom Configuration

```python
# High-quality
orchestrator = TranslationOrchestrator(
    model="gpt-4o",
    max_batch_size=30,
    max_retries=5,
)

# Cost-effective
orchestrator = TranslationOrchestrator(
    model="gpt-4o-mini",
    max_batch_size=50,
    max_retries=2,
)
```

## Error Handling

```python
try:
    result = orchestrator.translate_with_batching(...)
except RateLimitError:
    print("Rate limit hit after all retries")
except OpenAIError as e:
    print(f"Translation failed: {e}")
```

## Testing

```bash
# Run tests
python3 test_orchestrator_enhanced.py

# Expected output: ✓ All tests passed!
```

## Files

- **Implementation**: `kps/translation/orchestrator.py`
- **Tests**: `test_orchestrator_enhanced.py`
- **Docs**: `docs/TRANSLATION_ORCHESTRATOR_ENHANCED.md`
- **Summary**: `ENHANCEMENT_SUMMARY.md`

## Support

For issues or questions:
1. Check documentation: `docs/TRANSLATION_ORCHESTRATOR_ENHANCED.md`
2. Run tests: `python3 test_orchestrator_enhanced.py`
3. Review examples: `examples/translation_orchestrator_enhanced.py`
