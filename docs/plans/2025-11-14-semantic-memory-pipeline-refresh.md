# Semantic Memory Pipeline Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the hash-based embeddings shim with real OpenAI vectors, preload glossary knowledge, and streamline storage/retrieval so RAG stays fast, cheap, and reliable.

**Architecture:** Wrap OpenAI's `/embeddings` endpoint in a reusable client, persist 1536-d vectors (or quantized variants) in semantic memory, batch re-embed historical rows, and keep glossary-derived “seed” segments synchronized. Add a Postgres/pgvector backend behind a feature flag so large memories stop doing SQLite full scans. Adjust GlossaryTranslator to scope RAG queries by detected terms to avoid unnecessary DB hits.

**Tech Stack:** Python 3.11, sqlite3 → PostgreSQL + pgvector, SQLAlchemy-lite helpers, OpenAI Python SDK (v1.68.0), pytest, Click for CLI scripts.

---

### Task 1: Add an Embeddings Client + Config Surface

**Files:**
- Create: `dev/PDF_PARSER_2.0/kps/clients/embeddings.py`
- Modify: `dev/PDF_PARSER_2.0/kps/core/config.py`
- Modify: `dev/PDF_PARSER_2.0/tests/test_translation_system.py`

**Step 1: Write the failing test**

Add `test_embedding_client_round_trip` in `dev/PDF_PARSER_2.0/tests/test_translation_system.py` using pytest`s monkeypatch to stub OpenAI responses and assert that `EmbeddingsClient.create_vector([...])` returns floats of expected length and enforces rate-limit backoff.

```python
def test_embedding_client_round_trip(monkeypatch):
    events = []
    monkeypatch.setattr("kps.clients.embeddings.OpenAI", FakeOpenAI(events))
    client = EmbeddingsClient(model="text-embedding-3-small", max_batch=16)
    vecs = client.create_vectors(["foo", "бар"])
    assert len(vecs) == 2
    assert all(len(v) == 1536 for v in vecs)
    assert events == ["called"]
```

**Step 2: Run the test to verify it fails**

```bash
pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -k embedding_client_round_trip -vv
```

Expected: FAIL (module not found / assertion error).

**Step 3: Write minimal implementation**

- Create `EmbeddingsClient` wrapper that instantiates `OpenAI()` once, handles chunking, optional retries, and returns `List[List[float]]`.
- Extend `PipelineConfig` with `embedding_model`, `embedding_batch`, `embedding_timeout` defaults.
- Wire env overrides using `os.getenv("OPENAI_API_KEY")`.

**Step 4: Run the focused test**

```bash
pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -k embedding_client_round_trip -vv
```

Expect PASS.

**Step 5: Commit**

```bash
git add dev/PDF_PARSER_2.0/kps/clients/embeddings.py \
        dev/PDF_PARSER_2.0/kps/core/config.py \
        dev/PDF_PARSER_2.0/tests/test_translation_system.py
git commit -m "feat: add reusable OpenAI embeddings client"
```

---

### Task 2: Replace Hash-Based `_get_embedding` With Real Vectors + Caching

**Files:**
- Modify: `dev/PDF_PARSER_2.0/kps/translation/semantic_memory.py`
- Modify: `dev/PDF_PARSER_2.0/tests/test_translation_system.py`

**Step 1: Write failing tests**

Add two tests: `test_semantic_memory_persists_real_embeddings` (asserts the DB row stores 1536 floats and retrieval reuses cache) and `test_embedding_cache_eviction` (LRU behavior). Use temporary SQLite DB fixtures.

**Step 2: Run tests to ensure they fail**

```bash
pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -k semantic_memory_persists_real_embeddings -vv
```

Expect FAIL (simulated vector still in place).

**Step 3: Implement**

- Inject `EmbeddingsClient` via constructor (default autoload from PipelineConfig).
- Replace `_get_embedding` with async-safe batching call to client, storing float32 arrays; enforce 1536 dimension.
- Serialize embeddings using `array('f')` or numpy `.astype(np.float32).tobytes()`; store dimension meta for validation.
- Implement LRU cache with `collections.OrderedDict` limited by `embedding_cache_size`.

**Step 4: Run full semantic tests**

```bash
pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -k semantic_memory -vv
```

Expect PASS.

**Step 5: Commit**

```bash
git commit -am "feat: persist real OpenAI embeddings in semantic memory"
```

---

### Task 3: Add CLI Tool To Re-Embed Historical Rows & Quantize Storage

**Files:**
- Create: `dev/PDF_PARSER_2.0/scripts/reindex_semantic_memory.py`
- Modify: `dev/PDF_PARSER_2.0/kps/translation/semantic_memory.py`
- Modify: `dev/PDF_PARSER_2.0/tests/test_translation_system.py`

**Step 1: Write failing integration test**

In tests, create DB with old `embedding_version=0`. Test that running CLI migrates N rows, updates `embedding_version`, and optionally writes quantized `halfvec` bytes to auxiliary column.

**Step 2: Run test (should fail)**

```bash
pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -k reindex_semantic_memory_cli -vv
```

Expect FAIL.

**Step 3: Implement CLI**

- Use Click: `python -m dev.PDF_PARSER_2.0.scripts.reindex_semantic_memory --db data/translation_memory.db --batch 128`.
- For each batch, fetch rows missing `embedding_version=1`, call client, optionally quantize using numpy `astype(np.float16)` before storing in new column `embedding_q16`.
- Update schema (ALTER TABLE) to add `embedding_version` (INTEGER DEFAULT 0) + `embedding_q16` BLOB.

**Step 4: Run new CLI test**

```bash
pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -k reindex_semantic_memory_cli -vv
```

Expect PASS.

**Step 5: Commit**

```bash
git add dev/PDF_PARSER_2.0/scripts/reindex_semantic_memory.py
git commit -am "feat: add semantic memory reindex CLI with quantized storage"
```

---

### Task 4: Seed Semantic Memory From Glossary YAML & Keep In Sync

**Files:**
- Create: `dev/PDF_PARSER_2.0/scripts/seed_glossary_memory.py`
- Modify: `dev/PDF_PARSER_2.0/kps/translation/glossary_translator.py`
- Modify: `dev/PDF_PARSER_2.0/tests/test_translation_system.py`

**Step 1: Write failing test**

Add `test_glossary_seed_creates_semantic_entries` (loads sample YAML, runs seed script, asserts `SemanticTranslationMemory` contains entries tagged with `glossary_terms` and `context="seed"`). Add unit test ensuring translator skips regen when version unchanged.

**Step 2: Run tests (expect fail)**

```bash
pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -k glossary_seed -vv
```

**Step 3: Implement**

- CLI: iterate YAML entries, synthesize pseudo segments like `"Спецсимвол ⟨purl stitch⟩" → "Special symbol ⟨purl stitch⟩"`, call `add_translation` with `quality_score=0.5`, `context="seed"`, `glossary_version` hash.
- In `GlossaryTranslator.__init__`, compare stored `seed_version` in memory (new table or metadata JSON) and re-run script when YAML changes.
- Provide `--dry-run` and `--chunksize` flags.

**Step 4: Run tests**

```bash
pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -k glossary_seed -vv
```

Expect PASS.

**Step 5: Commit**

```bash
git add dev/PDF_PARSER_2.0/scripts/seed_glossary_memory.py
git commit -am "feat: seed semantic memory from glossary YAML"
```

---

### Task 5: Scope RAG Queries & Lower Threshold For Special Symbols

**Files:**
- Modify: `dev/PDF_PARSER_2.0/kps/translation/glossary_translator.py`
- Modify: `dev/PDF_PARSER_2.0/tests/test_translation_system.py`

**Step 1: Write failing test**

New test ensures `GlossaryTranslator` groups segments by shared `glossary_terms` and calls `memory.get_rag_examples` per group with `min_similarity` lowered to 0.6 when `segment_terms` contains `special_symbol` tags.

**Step 2: Run focused test**

```bash
pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -k rag_special_symbols -vv
```

Expect FAIL.

**Step 3: Implement**

- Build helper `_group_segments_by_terms` returning clusters + query text.
- For each cluster, call RAG and append contextual block only for segments in cluster.
- Parameterize thresholds via config (`special_symbol_min_similarity`).
- Log metrics for monitoring (#calls, avg latency).

**Step 4: Run translator tests**

```bash
pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -k rag -vv
```

**Step 5: Commit**

```bash
git commit -am "feat: scope RAG queries by glossary terms"
```

---

### Task 6: Add Optional Postgres/pgvector Backend & Migration Path

**Files:**
- Create: `dev/PDF_PARSER_2.0/kps/translation/semantic_memory_pg.py`
- Modify: `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`
- Modify: `dev/PDF_PARSER_2.0/tests/test_translation_system.py`
- Create: `dev/PDF_PARSER_2.0/migrations/20251114_add_pgvector.sql`

**Step 1: Write failing integration test**

Add `test_semantic_memory_pgvector_search` that spins up ephemeral Postgres (use testcontainer or docker-compose fixture) with pgvector, inserts seed rows, and asserts `SemanticTranslationMemoryPG.find_similar` respects metadata pre-filters (language, glossary term) before ANN search, preventing 5s queries as warned by pgvector practitioners.

**Step 2: Run test (expect fail)**

```bash
pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -k pgvector -vv
```

**Step 3: Implement**

- New class using psycopg/sqlalchemy to store embeddings as `vector(1536)` plus `halfvec` quantized columns.
- Provide `pre_filter_clause` arguments (lang pairs, glossary flags) before `ORDER BY embedding <=> $1` to keep queries in 10-50 ms range.
- Add `PipelineConfig.memory_backend` to choose `sqlite` or `postgres`.
- Supply SQL migration that installs `pgvector`, creates `semantic_translations` table with `ivfflat` & `hnsw` indexes, plus metadata columns for filtering.

**Step 4: Run pg tests**

```bash
pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -k pgvector -vv
```

Expect PASS (skip if Postgres unavailable, but document requirement).

**Step 5: Commit**

```bash
git add dev/PDF_PARSER_2.0/kps/translation/semantic_memory_pg.py \
        dev/PDF_PARSER_2.0/migrations/20251114_add_pgvector.sql \
        dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py
git commit -m "feat: add optional pgvector semantic memory backend"
```

---

### Task 7: Documentation & Operational Runbooks

**Files:**
- Modify: `dev/PDF_PARSER_2.0/docs/SEMANTIC_MEMORY_ARCHITECTURE.md`
- Create: `dev/PDF_PARSER_2.0/docs/runbooks/semantic-memory.md`

**Step 1: Write docs tests (doctest)**

Add doctest snippet ensuring sample CLI invocations produce `usage_bytes` updates and referencing OpenAI embeddings API per 2025-11-14 spec (`client.embeddings.create(model="text-embedding-3-small", input=...)`).

**Step 2: Run doctest**

```bash
pytest dev/PDF_PARSER_2.0/docs -k semantic_memory_architecture --doctest-glob='*.md'
```

Expect FAIL (docs missing).

**Step 3: Update docs**

- Document new client, seeding scripts, Postgres option, referencing TigerData Agentic Postgres hybrid search guidance and pgvector filter order lessons (Nov 2025 sources).
- Include instructions for running seeding/reindex scripts nightly.

**Step 4: Run doctest again**

```bash
pytest dev/PDF_PARSER_2.0/docs -k semantic_memory_architecture --doctest-glob='*.md'
```

Expect PASS.

**Step 5: Commit**

```bash
git add dev/PDF_PARSER_2.0/docs/SEMANTIC_MEMORY_ARCHITECTURE.md \
        dev/PDF_PARSER_2.0/docs/runbooks/semantic-memory.md
git commit -m "docs: refresh semantic memory architecture and runbook"
```

---

### Task 8: Release Checklist

**Files:** none (operational)

1. Run `scripts/seed_glossary_memory.py` and `scripts/reindex_semantic_memory.py` against staging DB.
2. Verify `rag_min_similarity` overrides in `pipeline.yaml` for symbol-heavy locales (set to 0.6) and 0.75 elsewhere.
3. Smoke-test Postgres backend with `scripts/reindex_semantic_memory.py --backend postgres`.
4. Monitor metrics: embedding latency, RAG cache hit rate, Postgres query times (<60 ms target).
5. Tag release `semantic-memory-refresh-2025.11.14`.
