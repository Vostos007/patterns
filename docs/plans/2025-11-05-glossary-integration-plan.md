# Glossary-Aware Translation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the PDF translation pipeline consult `docs/glossary.json` so domain terms map to canonical EN/FR strings while respecting protected tokens.

**Architecture:** Load the glossary once per run, select only entries relevant to the current chunk, and inject them into translation prompts as structured context. Maintain placeholder decoding and chunked requests to OpenAI.

**Tech Stack:** Python 3.11+, PyMuPDF (fitz), OpenAI Chat Completions, `docs/glossary.json` (comment-stripped JSON).

---

### Task 1: Glossary loader utility

**Files:**
- Create: `src/pdf_pipeline/glossary.py`
- Create: `tests/test_glossary.py`

**Step 1:** Write failing tests describing loader behavior (strip `//` comments, cache entries, expose helper to match RU terms).

```bash
./venv/bin/python -m pytest tests/test_glossary.py::test_loads_glossary_without_comments -q
```
Expected: FAIL (file missing / function missing).

**Step 2:** Implement loader module with:
- `load_glossary(path: Path | None = None) -> dict`
- `select_entries(terms: Sequence[str], glossary: dict, max_terms: int = 25)` matching RU terms by substring
- Cache via `functools.lru_cache` for default path `docs/glossary.json`.

**Step 3:** Re-run targeted tests expecting PASS.

---

### Task 2: Integrate glossary into TranslationOrchestrator

**Files:**
- Modify: `src/pdf_pipeline/translator.py`
- Modify: `tests/test_translator.py`

**Step 1:** Add failing tests to assert that translation calls include glossary context and that protected tokens survive. Use monkeypatched `_call_chat_completion` to capture `messages` payload.

`tests/test_translator.py` additions:
- When RU segment contains "лицевая петля", system prompt should mention "knit stitch (k)".
- Ensure `protected_tokens` appear in prompt instructions.

Run:
```bash
./venv/bin/python -m pytest tests/test_translator.py::test_translation_includes_glossary -q
```
Expected: FAIL.

**Step 2:** Update `TranslationOrchestrator`:
- Load glossary once at init using new helper.
- For each chunk, gather matching entries (fallback to top N core abbreviations if none found).
- Build system prompt with concise bullet list, preserving protected tokens.
- Ensure decode_placeholders still runs on final output.

**Step 3:** Re-run updated translator tests, ensure PASS.

---

### Task 3: End-to-end smoke + renderer regression

**Files:**
- Modify: `tests/test_pdf_renderer.py` (if prompt text footprint changes)
- Create: `tests/integration/test_pipeline_glossary.py` (mock end-to-end)

**Step 1:** Add integration-style test that simulates translation run, verifying Markdown/PDF pipeline receives glossary-informed translation (mock completion returning known strings).

Run selective pytest for new scenario.

**Step 2:** Execute focused test suite to ensure no regressions:
```bash
./venv/bin/python -m pytest tests/test_glossary.py tests/test_translator.py tests/test_pdf_renderer.py tests/integration/test_pipeline_glossary.py -q
```
Expected: PASS.

---

### Task 4: Documentation & .env guidance

**Files:**
- Modify: `README.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `.env.example` (if glossary toggle needed)

**Step 1:** Note glossary enforcement in changelog and README (short instructions on updating `docs/glossary.json`).

**Step 2:** If new env vars introduced (e.g., to disable glossary), document them.

**Step 3:** Run lint/test quick sweep and stage changes.

---

Plan complete and saved to `docs/plans/2025-11-05-glossary-integration-plan.md`. Two execution options:

1. **Subagent-Driven (this session)** – run tasks sequentially with reviews after each.
2. **Parallel Session** – open new session and use superpowers:executing-plans for batched execution.

Which approach?
