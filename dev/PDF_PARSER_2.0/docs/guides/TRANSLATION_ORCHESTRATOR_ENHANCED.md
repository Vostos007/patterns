# Translation Orchestrator Enhanced - KPS v2.0

> **Production-ready batch translation with retry logic, progress tracking, and cost estimation**

## Overview

The enhanced Translation Orchestrator provides production-grade features for batch processing large knitting pattern documents with OpenAI GPT models. It handles API rate limits, provides real-time progress tracking, and estimates translation costs.

## Features

### 1. Batch Processing

Splits large document translations into manageable batches to stay within OpenAI API token limits (8K tokens per request).

**Benefits:**
- Prevents API token limit errors
- Enables parallel processing of multiple batches
- Better memory management for large documents

**Configuration:**
```python
orchestrator = TranslationOrchestrator(
    model="gpt-4o-mini",
    max_batch_size=50,  # Default: 50 segments per batch
)
```

### 2. Retry Logic with Exponential Backoff

Automatically retries failed API calls with intelligent backoff strategy.

**Retry Triggers:**
- **429 Rate Limit Error**: Exponential backoff (1s → 2s → 4s)
- **Transient Errors (500, 502, 503)**: Exponential backoff
- **Other Errors**: Fail immediately (no retry)

**Configuration:**
```python
orchestrator = TranslationOrchestrator(
    max_retries=3,      # Default: 3 attempts
    retry_delay=1.0,    # Default: 1.0s initial delay
)
```

**Retry Sequence:**
```
Attempt 1: Failed (429 Rate Limit)
Wait 1.0s...
Attempt 2: Failed (429 Rate Limit)
Wait 2.0s... (exponential backoff: 1.0 × 2)
Attempt 3: Success!
```

### 3. Progress Tracking

Real-time progress updates via callback function.

**Progress Information:**
- Current batch number and total batches
- Segments completed and total segments
- Current target language being processed
- Estimated cost so far
- Elapsed time
- Estimated time remaining

**Example:**
```python
def progress_callback(progress: TranslationProgress):
    print(f"Batch {progress.current_batch}/{progress.total_batches}")
    print(f"Language: {progress.current_language}")
    print(f"Cost: ${progress.estimated_cost:.4f}")
    print(f"ETA: {progress.estimated_time_remaining:.1f}s")

result = orchestrator.translate_with_batching(
    segments=segments,
    target_languages=["en", "fr"],
    progress_callback=progress_callback,
)
```

**Output:**
```
Batch 1/6
Language: en
Cost: $0.0020
ETA: 12.5s

Batch 2/6
Language: en
Cost: $0.0040
ETA: 10.0s
```

### 4. Cost Estimation

Tracks token usage and estimates translation costs in real-time.

**Model Pricing (per 1M tokens):**
| Model | Input | Output |
|-------|-------|--------|
| gpt-4o-mini | $0.15 | $0.60 |
| gpt-4o | $2.50 | $10.00 |
| gpt-4-turbo | $10.00 | $30.00 |

**Token Counting:**
- Uses heuristic: ~4 characters per token
- Caches token counts for repeated text
- For production, consider using `tiktoken` library for exact counts

**Cost Breakdown:**
```python
result = orchestrator.translate_with_batching(...)

print(f"Total input tokens: {result.total_input_tokens:,}")
print(f"Total output tokens: {result.total_output_tokens:,}")
print(f"Total cost: ${result.total_cost:.4f}")
```

**Example Cost Scenarios:**

| Document Size | Segments | Input Tokens | Output Tokens | Cost (gpt-4o-mini) |
|---------------|----------|--------------|---------------|--------------------|
| Small | 100 | 1,000 | 2,000 | $0.0014 |
| Medium | 500 | 5,000 | 10,000 | $0.0068 |
| Large | 2,000 | 20,000 | 40,000 | $0.0270 |
| Very Large | 10,000 | 100,000 | 200,000 | $0.1350 |

### 5. Glossary Integration

Smart glossary term selection with scoring algorithm.

**Term Selection:**
- **Exact match**: Score 3 (highest priority)
- **Prefix match**: Score 2
- **Substring match** (≥4 chars): Score 1
- **Max terms**: 50 per batch (configurable)

**Usage:**
```python
from kps.translation.glossary import GlossaryManager

glossary = GlossaryManager()  # Auto-loads from config/glossaries/*.yaml

result = orchestrator.translate_with_batching(
    segments=segments,
    target_languages=["en"],
    glossary_manager=glossary,  # Enable smart term selection
)
```

**How it works:**
1. Extract all words from segments
2. Score each glossary entry against document terms
3. Select top 50 entries by score
4. Build glossary context string
5. Inject into system prompt

**Example Glossary Context:**
```
Glossary (use these exact translations):

Abbreviations:
  п. → st (stitch)
  лиц. → k (knit)
  изн. → p (purl)
  см → cm (centimeter)

Terms:
  спицы → needles
  пряжа → yarn
  резинка → ribbing
```

## API Reference

### TranslationOrchestrator

```python
class TranslationOrchestrator:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        max_batch_size: int = 50,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    )
```

**Parameters:**
- `model`: OpenAI model ("gpt-4o-mini", "gpt-4o", "gpt-4-turbo")
- `api_key`: API key (uses OPENAI_API_KEY env var if None)
- `max_batch_size`: Maximum segments per batch (default: 50)
- `max_retries`: Maximum retry attempts (default: 3)
- `retry_delay`: Initial retry delay in seconds (default: 1.0)

### translate_with_batching()

```python
def translate_with_batching(
    self,
    segments: List[TranslationSegment],
    target_languages: List[str],
    glossary_manager: Optional[GlossaryManager] = None,
    progress_callback: Optional[Callable[[TranslationProgress], None]] = None,
) -> BatchTranslationResult
```

**Parameters:**
- `segments`: List of TranslationSegment objects to translate
- `target_languages`: Target language codes (e.g., ["en", "fr"])
- `glossary_manager`: Optional GlossaryManager for term selection
- `progress_callback`: Optional callback function for progress updates

**Returns:**
- `BatchTranslationResult` with:
  - `detected_source_language`: Auto-detected source language
  - `translations`: Dict of {lang: TranslationResult}
  - `total_cost`: Estimated cost in USD
  - `total_input_tokens`: Total input tokens used
  - `total_output_tokens`: Total output tokens used

## Data Structures

### TranslationProgress

```python
@dataclass
class TranslationProgress:
    current_batch: int          # Current batch number (1-indexed)
    total_batches: int          # Total number of batches
    segments_completed: int     # Segments translated so far
    total_segments: int         # Total segments to translate
    current_language: str       # Current target language ("en", "fr")
    estimated_cost: float       # Estimated cost so far (USD)
    elapsed_time: float         # Elapsed time (seconds)
    estimated_time_remaining: float  # Estimated time remaining (seconds)
```

### BatchTranslationResult

```python
@dataclass
class BatchTranslationResult:
    detected_source_language: str
    translations: Dict[str, TranslationResult]
    total_cost: float           # Total estimated cost (USD)
    total_input_tokens: int     # Total input tokens
    total_output_tokens: int    # Total output tokens
```

## Usage Examples

### Example 1: Basic Batch Translation

```python
from kps.translation import TranslationOrchestrator, TranslationSegment

# Create segments
segments = [
    TranslationSegment(
        segment_id="p.materials.001.seg0",
        text="Пряжа: 100% шерсть, спицы 4 мм.",
        placeholders={},
    ),
    # ... more segments
]

# Initialize orchestrator
orchestrator = TranslationOrchestrator(model="gpt-4o-mini")

# Translate
result = orchestrator.translate_with_batching(
    segments=segments,
    target_languages=["en", "fr"],
)

# Print results
print(f"Cost: ${result.total_cost:.4f}")
for lang, translation in result.translations.items():
    print(f"{lang}: {translation.segments[0]}")
```

### Example 2: With Progress Tracking

```python
def show_progress(progress: TranslationProgress):
    percent = (progress.current_batch / progress.total_batches) * 100
    print(f"[{percent:.0f}%] Batch {progress.current_batch}/{progress.total_batches} "
          f"({progress.current_language}) - ${progress.estimated_cost:.4f}")

result = orchestrator.translate_with_batching(
    segments=segments,
    target_languages=["en", "fr"],
    progress_callback=show_progress,
)
```

**Output:**
```
[17%] Batch 1/6 (en) - $0.0020
[33%] Batch 2/6 (en) - $0.0040
[50%] Batch 3/6 (en) - $0.0060
[67%] Batch 4/6 (fr) - $0.0080
[83%] Batch 5/6 (fr) - $0.0100
[100%] Batch 6/6 (fr) - $0.0120
```

### Example 3: With Glossary Integration

```python
from kps.translation.glossary import GlossaryManager

# Load glossary
glossary = GlossaryManager()

# Translate with glossary
result = orchestrator.translate_with_batching(
    segments=segments,
    target_languages=["en"],
    glossary_manager=glossary,
)

# Glossary terms automatically selected based on document content
# Top 50 most relevant terms injected into translation prompt
```

### Example 4: Custom Configuration

```python
# High-quality, conservative configuration
orchestrator = TranslationOrchestrator(
    model="gpt-4o",           # Higher quality model
    max_batch_size=30,        # Smaller batches for complex docs
    max_retries=5,            # More retries for reliability
    retry_delay=2.0,          # Longer initial delay
)

# Fast, cost-effective configuration
orchestrator = TranslationOrchestrator(
    model="gpt-4o-mini",      # Cost-effective model
    max_batch_size=50,        # Larger batches
    max_retries=2,            # Fewer retries
    retry_delay=0.5,          # Shorter delay
)
```

## Integration with KPS Pipeline

The enhanced orchestrator integrates seamlessly with the KPS v2.0 translation pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: Anchoring + Marker Injection                      │
│  Output: Text with [[img-abc123-p3-occ1]] markers           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: Translation (Enhanced Orchestrator)                │
│                                                               │
│  1. Protect [[markers]] as <ph> placeholders                 │
│  2. Split into batches (50 segments)                         │
│  3. For each batch:                                          │
│     a. Select glossary terms (smart scoring)                 │
│     b. Translate with retry logic                            │
│     c. Track progress and cost                               │
│  4. Decode placeholders                                      │
│  5. Return translations + cost report                        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
        Translated KPSDocument (3 languages) + Cost Report
```

## Performance Characteristics

### Batch Size Recommendations

| Document Size | Segments | Recommended Batch Size | Batches | Approx Time |
|---------------|----------|------------------------|---------|-------------|
| Small | < 100 | 50 | 1-2 | 10-20s |
| Medium | 100-500 | 50 | 2-10 | 20-100s |
| Large | 500-2000 | 50 | 10-40 | 100-400s |
| Very Large | 2000+ | 30-50 | 40+ | 400s+ |

### Memory Usage

- **Per Segment**: ~500 bytes
- **Per Batch (50 segments)**: ~25 KB
- **Token Cache**: ~1 KB per unique text
- **Total Overhead**: < 1 MB

### API Rate Limits

**OpenAI Limits:**
- Free Tier: 3 RPM (requests per minute), 40K TPM (tokens per minute)
- Tier 1: 500 RPM, 10M TPM
- Tier 2: 5000 RPM, 100M TPM

**Orchestrator Handling:**
- Automatic retry on 429 errors
- Exponential backoff: 1s → 2s → 4s
- Max 3 retries (configurable)

## Error Handling

### Retry Logic

**Errors that trigger retry:**
```python
429 Rate Limit Error → Retry with backoff
500 Internal Server Error → Retry with backoff
502 Bad Gateway → Retry with backoff
503 Service Unavailable → Retry with backoff
```

**Errors that fail immediately:**
```python
400 Bad Request → Fail (invalid input)
401 Unauthorized → Fail (invalid API key)
403 Forbidden → Fail (insufficient permissions)
Other → Fail (unknown error)
```

### Fallback Behavior

If translation fails after all retries:
```python
# Fallback: Return original text
if len(translated_segments) != len(segments):
    translated_segments = [s.text for s in segments]
```

## Testing

Run the comprehensive test suite:

```bash
cd /Users/vostos/Dev/Hollywool\ patterns/dev/PDF_PARSER_2.0
python3 test_orchestrator_enhanced.py
```

**Test Coverage:**
- ✓ Batch splitting algorithm
- ✓ Exponential backoff calculation
- ✓ Token counting heuristic
- ✓ Cost calculation accuracy
- ✓ Progress tracking data flow
- ✓ Configuration validation

## Production Checklist

Before deploying to production:

- [ ] Set `OPENAI_API_KEY` environment variable
- [ ] Configure batch size based on document size
- [ ] Set appropriate retry limits (3-5 for production)
- [ ] Implement progress callback for UI updates
- [ ] Monitor token usage and costs
- [ ] Load glossary files from config/glossaries/
- [ ] Test with sample documents (small, medium, large)
- [ ] Validate cost estimates against actual usage
- [ ] Set up error logging and alerting
- [ ] Configure rate limit handling

## Best Practices

1. **Batch Size:**
   - Use 50 segments for standard documents
   - Use 30 segments for complex documents with long text
   - Use 100 segments for simple documents (single sentences)

2. **Retry Strategy:**
   - Use 3 retries for production (balance reliability vs latency)
   - Use 5+ retries for critical translations
   - Monitor retry rates to detect API issues

3. **Cost Control:**
   - Start with gpt-4o-mini for prototyping
   - Use gpt-4o only for final production translations
   - Monitor total_cost field in BatchTranslationResult
   - Set cost alerts for large documents

4. **Progress Tracking:**
   - Always implement progress_callback for long-running translations
   - Display progress to users (UI updates)
   - Log progress for debugging and monitoring

5. **Glossary Usage:**
   - Always provide glossary_manager for domain-specific documents
   - Keep glossary files updated (config/glossaries/*.yaml)
   - Monitor glossary term selection quality

## Troubleshooting

### High Cost

**Problem:** Translation costs are higher than expected

**Solutions:**
- Check `total_input_tokens` and `total_output_tokens` in result
- Reduce batch size to minimize token overhead
- Use gpt-4o-mini instead of gpt-4o
- Optimize segment splitting (fewer, longer segments)

### Rate Limit Errors

**Problem:** Frequent 429 rate limit errors despite retries

**Solutions:**
- Increase `retry_delay` (e.g., 2.0s or 5.0s)
- Reduce batch size to decrease tokens per request
- Upgrade OpenAI API tier (Tier 1 → Tier 2)
- Add delay between batches (time.sleep(0.5))

### Slow Translation

**Problem:** Translation takes too long

**Solutions:**
- Increase batch size (50 → 100) for simple documents
- Use gpt-4o-mini for faster responses
- Reduce retry_delay (1.0s → 0.5s)
- Process multiple languages in parallel (future enhancement)

### Glossary Not Working

**Problem:** Glossary terms not appearing in translations

**Solutions:**
- Verify glossary files exist: `config/glossaries/*.yaml`
- Check glossary_manager is passed to translate_with_batching()
- Ensure document contains matching terms (check term selection)
- Verify glossary YAML format is correct

## Related Documentation

- **Translation Pipeline**: See `docs/TRANSLATION_PIPELINE.md`
- **Glossary Manager**: See `kps/translation/glossary/manager.py`
- **Glossary Selector**: See `kps/translation/glossary/selector.py`
- **Master Plan**: See `docs/KPS_MASTER_PLAN.md` (Section: Translation Pipeline)

## Summary

The enhanced Translation Orchestrator provides production-grade features for batch processing large documents:

- **Batch Processing**: Split into 50-segment batches, stay within token limits
- **Retry Logic**: Exponential backoff for rate limits and transient errors
- **Progress Tracking**: Real-time updates with cost and time estimates
- **Cost Estimation**: Token counting and model-specific pricing
- **Glossary Integration**: Smart term selection with scoring algorithm

**Result**: Reliable, cost-effective, and observable translation pipeline for KPS v2.0.
