# P5: Hybrid Retrieval & Context Compression

## Overview

P5 implements advanced search and context optimization for the KPS translation system:

1. **Hybrid Search**: Combines BM25 (keyword-based) and vector similarity (semantic) for improved retrieval accuracy
2. **Context Compression**: Extractive summarization to reduce token usage in LLM prompts by 30-70%
3. **Text Canonicalization**: NFKC normalization to prevent duplicate entries from Unicode variants

## Architecture

```
Query → [BM25 Search (ts_rank)]     → Top 200 results
     ↓                                    ↓
     → [Vector Search (pgvector)]   → Top 200 results
                                           ↓
                                    [Alpha Weighting]
                                           ↓
                                    [Context Compression]
                                           ↓
                                    Compressed context (≤2K tokens)
```

### Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| `kps/text/normalize.py` | Text canonicalization | Unicode NFKC, regex |
| `kps/search/hybrid.py` | Hybrid BM25+vector search | PostgreSQL ts_rank, pgvector |
| `kps/search/snippets.py` | Context compression | Extractive summarization |

## Text Canonicalization

### Problem

Different Unicode representations create false duplicates:

```
"кафе́" (U+0301 combining accent)
"кафе"  (U+00E9 precomposed)
"café"  (different quote styles: ' ' ` '')
```

### Solution

```python
from kps.text.normalize import canon

# NFKC normalization + apostrophe/quote normalization + whitespace collapse
text1 = "café"     # U+0301
text2 = "café"     # U+00E9
assert canon(text1) == canon(text2)

text3 = "it's   a   test"
assert canon(text3) == "it's a test"
```

### Usage in Database

Apply canonicalization before insertion:

```python
from kps.text.normalize import canon
import hashlib

src_text = "Провяжите  лицевую петлю"
canonical = canon(src_text)
text_hash = hashlib.md5(canonical.encode()).hexdigest()

cur.execute("""
    insert into glossary_terms(src_term, src_term_canonical, src_term_hash, ...)
    values (%s, %s, %s, ...)
    on conflict(src_term_hash, tgt_term_hash) do nothing
""", (src_text, canonical, text_hash, ...))
```

## Hybrid Search

### Problem

Single search methods have limitations:

- **BM25 only**: Misses semantic similarity (e.g., "лицевая петля" vs "knit stitch")
- **Vector only**: Misses exact keyword matches (e.g., model numbers, SKUs)

### Solution

Combine both with alpha weighting:

```python
from kps.search.hybrid import hybrid_search

results = hybrid_search(
    db_url="postgresql://user:pass@localhost/kps",
    query="лицевая петля",
    k=12,           # Return top 12 results
    alpha=0.5       # 0.5 = balanced, 0.0 = pure vector, 1.0 = pure BM25
)

for r in results:
    print(f"Score: {r['score']:.3f}")
    print(f"Text: {r['src_text']}")
    print(f"Translation: {r['translated_text']}")
```

### Alpha Tuning

| Alpha | Use Case | Example |
|-------|----------|---------|
| 0.0 | Pure semantic search | "Explain knitting techniques" |
| 0.3 | Semantic-focused | "What is a purl stitch?" |
| 0.5 | Balanced (default) | "лицевая петля translation" |
| 0.7 | Keyword-focused | "SKU: KPS-2024-001" |
| 1.0 | Pure keyword search | Exact pattern codes |

### Performance

```sql
-- BM25 search (ts_rank)
with q as (select plainto_tsquery('simple', 'лицевая петля') as qq)
select s.id, ts_rank(sc.text, (select qq from q)) as bm25
from search_corpus sc
join segments s on s.id = sc.segment_id
where sc.text @@ (select qq from q)
order by bm25 desc limit 200;

-- Vector search (pgvector)
select segment_id, 1 - (vec <=> %s::vector) as sim
from embeddings
order by vec <=> %s::vector limit 200;

-- Combined (alpha weighting)
-- score = alpha * (bm25/bm25_max) + (1-alpha) * (sim/sim_max)
```

**Typical latency**:
- BM25 search: 20-50ms
- Vector search: 30-80ms (with HNSW index)
- Hybrid combination: 60-150ms

## Context Compression

### Problem

RAG systems often exceed token limits or waste tokens on repetitive context:

```
# Before compression (5000 tokens)
[Full segment 1 - 800 tokens]
[Full segment 2 - 750 tokens]
[Full segment 3 - 820 tokens]
...
[Full segment 10 - 600 tokens]
```

### Solution

Extract key paragraphs with citations:

```python
from kps.search.snippets import compress_segments

results = hybrid_search(db_url, query="лицевая петля", k=12)

# Compress to ≤2000 chars (~500 tokens)
compressed = compress_segments(results, max_chars=2000)

print(compressed)
# Output:
# Провяжите лицевую петлю в каждую петлю предыдущего ряда.
# [doc:42/seg:108]
# ---
# Лицевая петля (knit stitch) — основной элемент вязания.
# [doc:43/seg:15]
# ---
# ...
```

### Token Reduction

| Method | Avg Tokens | Cost Reduction |
|--------|------------|----------------|
| No compression (top 10 full segments) | ~1500 | Baseline |
| Top 5 full segments | ~750 | 50% |
| Compressed snippets (2000 chars) | ~500 | 67% |
| Compressed snippets (1000 chars) | ~250 | 83% |

### Usage in Translation Pipeline

```python
from kps.search.hybrid import hybrid_search
from kps.search.snippets import compress_segments

# Find relevant context
results = hybrid_search(db_url, query=src_text, k=12, alpha=0.5)

# Compress for LLM prompt
context = compress_segments(results, max_chars=1500)

# Build prompt
prompt = f"""Translate the following text using these reference translations:

{context}

Now translate:
{src_text}
"""

# Send to OpenAI
response = openai.ChatCompletion.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)
```

## Success Criteria

### P5.1: Hybrid Search Accuracy

- **Metric**: nDCG@10 (normalized discounted cumulative gain)
- **Baseline**: 0.65 (pure BM25 or pure vector)
- **Target**: ≥0.75 (+15% improvement)
- **Validation**: Run benchmark on 100 test queries with human-annotated relevance scores

### P5.2: Context Compression Efficiency

- **Metric**: Average tokens per query
- **Baseline**: 1500 tokens (top 10 full segments)
- **Target**: ≤500 tokens (67% reduction)
- **Quality**: Manual review shows no critical information loss

### P5.3: Latency

- **Metric**: p95 search latency
- **Target**: ≤200ms for hybrid search + compression
- **Infrastructure**: Single PostgreSQL instance with pgvector HNSW index

## Integration Examples

### Example 1: Document Translation

```python
from kps.pipeline import translate_document
from kps.search.hybrid import hybrid_search
from kps.search.snippets import compress_segments

def translate_with_context(doc_id: int, db_url: str):
    # Extract segments
    segments = extract_segments(doc_id)

    for seg in segments:
        # Find relevant context
        results = hybrid_search(db_url, seg.text, k=12, alpha=0.5)
        context = compress_segments(results, max_chars=1500)

        # Translate with context
        translation = call_openai(seg.text, context)

        # Save translation
        save_translation(seg.id, translation)
```

### Example 2: Interactive Search

```bash
# CLI search with hybrid retrieval
kps search "лицевая петля" --method hybrid --alpha 0.5 --limit 10

# Output:
# Score: 0.892 | Provyazhite litcevuyu petlyu... [doc:42/seg:108]
# Score: 0.845 | Litcevaya petlya (knit stitch)... [doc:43/seg:15]
# ...
```

### Example 3: Batch Processing

```python
from kps.search.hybrid import hybrid_search
from kps.text.normalize import canon
import csv

# Load query batch
queries = ["лицевая петля", "изнаночная петля", "накид"]

# Process with hybrid search
results_batch = []
for q in queries:
    q_canon = canon(q)
    results = hybrid_search(db_url, q_canon, k=12, alpha=0.5)
    results_batch.append(results)

# Export to CSV
with open("search_results.csv", "w") as f:
    writer = csv.DictWriter(f, fieldnames=["query", "score", "text"])
    writer.writeheader()
    for q, results in zip(queries, results_batch):
        for r in results:
            writer.writerow({"query": q, "score": r["score"], "text": r["src_text"]})
```

## Monitoring

### Prometheus Metrics

```python
from kps.metrics import (
    record_kb_search,
    KB_SEARCHES,
)

# Record search
record_kb_search(category="hybrid", language="ru")

# Grafana query
# rate(kps_kb_searches_total[5m])
```

### Grafana Dashboard Queries

```promql
# Search throughput
rate(kps_kb_searches_total{category="hybrid"}[5m])

# Average search latency (requires custom histogram)
histogram_quantile(0.95, rate(kps_search_duration_seconds_bucket[5m]))

# Cache hit rate improvement (if caching search results)
kps_translation_cache_hit_rate{source_lang="ru", target_lang="en"}
```

## Performance Tuning

### PostgreSQL Configuration

```sql
-- Create HNSW index for vector search
create index embeddings_vec_hnsw_idx on embeddings
using hnsw (vec vector_cosine_ops)
with (m = 16, ef_construction = 64);

-- Create GIN index for BM25 search
create index search_corpus_text_gin on search_corpus using gin(text);

-- Vacuum and analyze
vacuum analyze embeddings;
vacuum analyze search_corpus;
```

### Environment Variables

```bash
# Hybrid search defaults
export KPS_SEARCH_ALPHA=0.5          # Default alpha weighting
export KPS_SEARCH_K=12                # Default top-K results
export KPS_CONTEXT_MAX_CHARS=2000     # Default compression limit
```

## Testing

### Unit Tests

```bash
# Run P5 tests
pytest tests/unit/search/test_hybrid.py -v
pytest tests/unit/search/test_snippets.py -v
pytest tests/unit/text/test_normalize.py -v
```

### Integration Tests

```bash
# End-to-end search pipeline
pytest tests/integration/test_search_pipeline.py -v

# Benchmark hybrid search accuracy
python scripts/benchmark_search.py --queries test_queries.json
```

### Manual Validation

```bash
# Test canonicalization
python -c "from kps.text.normalize import canon; print(canon('café'))"

# Test hybrid search
kps search "лицевая петля" --method hybrid --alpha 0.5

# Test compression
kps search "лицевая петля" --compress --max-chars 1500
```

## Migration from P4

No breaking changes. P5 is purely additive:

1. Text canonicalization is optional (add `_canonical` and `_hash` columns to existing tables)
2. Hybrid search is a new API alongside existing search methods
3. Context compression is a post-processing step

### Optional Schema Updates

```sql
-- Add canonicalization support to glossary_terms
alter table glossary_terms
  add column if not exists src_term_canonical text,
  add column if not exists tgt_term_canonical text,
  add column if not exists src_term_hash char(32),
  add column if not exists tgt_term_hash char(32);

-- Add unique constraint on hash
create unique index if not exists glossary_terms_hash_uniq
  on glossary_terms(src_term_hash, tgt_term_hash);
```

## References

- [BM25 Algorithm](https://en.wikipedia.org/wiki/Okapi_BM25)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [HNSW Index](https://arxiv.org/abs/1603.09320)
- [Unicode NFKC Normalization](https://unicode.org/reports/tr15/)
- [Extractive Summarization](https://arxiv.org/abs/1704.04368)

## Support

For issues or questions:
- Check logs: `tail -f logs/kps.log`
- Monitor metrics: `http://localhost:9108/metrics`
- Run diagnostics: `kps diagnose search`
