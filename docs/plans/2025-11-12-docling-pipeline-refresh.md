# Docling Pipeline Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure the translation pipeline (DOCX/PDF) uses Docling end-to-end, exports via controlled templates, runs QA, and consumes `/Users/vostos/Dev/Hollywool patterns/глоссарий.json` as the authoritative glossary (currently 86 entries across ~730 JSON lines).

**Architecture:** Convert the JSON glossary into YAML automatically (so GlossaryManager keeps working) and keep both files in the repo. After translation, reinsert text into DoclingDocument and drive exports via pandoc (DOCX) or WeasyPrint (PDF) with fallbacks. QA re-parses exports to confirm nothing is lost, and CLI/UI surface warnings. All inputs/outputs stay inside `dev/PDF_PARSER_2.0`.

**Tech Stack:** Python 3.11, Docling 2.x, pandoc CLI, WeasyPrint, python-docx, ReportLab (fallback), pytest, Next.js frontend.

---

### Task 1: Glossary sync (JSON → YAML)

**Files:**
- Create: `dev/PDF_PARSER_2.0/scripts/sync_glossary.py`
- Add data: `dev/PDF_PARSER_2.0/data/glossary.json`
- Output: `dev/PDF_PARSER_2.0/config/glossaries/knitting_custom.yaml`
- Tests: `dev/PDF_PARSER_2.0/tests/unit/glossary/test_sync_script.py`

**Steps:**
1. Write failing test that runs script on sample JSON and asserts YAML structure matches categories/protected tokens.
2. Implement script: read JSON, drop comments, group by `category`, dump YAML.
3. Update docs (`README` or `docs/QA_EXPORT_CHECKLIST.md`) explaining how to run script before commits and reiterate that `/Users/vostos/Dev/Hollywool patterns/глоссарий.json` is the master file.
4. Run pytest for the new tests.
5. Commit `feat: add glossary sync script`.

### Task 2: Wire glossary into pipeline

**Files:**
- Modify: `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`
- Modify: `dev/PDF_PARSER_2.0/kps/translation/glossary/manager.py`
- Tests: `dev/PDF_PARSER_2.0/tests/unit/glossary/test_manager_yaml.py`

**Steps:**
1. Write tests ensuring pipeline loads `config/glossaries/knitting_custom.yaml` and logs loaded count.
2. Update config defaults to point to the synced YAML; fallback to auto-run script if file missing.
3. Ensure GlossaryManager exposes `loaded_files` to QA report.
4. Run tests; commit `feat: load synced glossary`.

### Task 3: Docling export module

**Files:**
- Create: `dev/PDF_PARSER_2.0/kps/export/docling_pipeline.py`
- Modify: `dev/PDF_PARSER_2.0/kps/export/__init__.py`
- Modify: `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`
- Tests: `dev/PDF_PARSER_2.0/tests/integration/test_docling_exports.py`

**Steps:**
1. Write integration test placeholders (skipping docx test if pandoc absent) to assert tables/images survive.
2. Implement functions: `render_docx_from_docling` (HTML→pandoc→merge reference), `render_pdf_from_docling` (HTML→WeasyPrint), `render_markdown_from_docling`, plus graceful fallbacks (structure builder, ReportLab placeholder).
3. Update pipeline `_export_translation_for_format` to prefer docling renderer.
4. Run tests; commit `feat: add docling export module`.

### Task 3.6: IO layout overhaul

**Files:**
- Create: `dev/PDF_PARSER_2.0/kps/io/layout.py`, `dev/PDF_PARSER_2.0/runtime/*`, `docs/guides/io_layout.md`
- Modify: `dev/PDF_PARSER_2.0/kps/cli.py`, `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`

**Steps:**
1. Introduce `IOLayout`/`RunContext` to enforce the `input/`, `inter/json`, `inter/markdown`, `output/<slug>/vXXX`, `tmp/` hierarchy inspired by Docling + PaddleOCR pipelines.citeturn0search0turn1search0
2. Update CLI to stage originals, version outputs automatically, and expose `--root`/`--tmp` options.
3. Have `UnifiedPipeline` dump Docling JSON/Markdown intermediates per run before translation.

### Task 4: Post-export QA

**Files:**
- Create: `dev/PDF_PARSER_2.0/kps/qa/export_validation.py`
- Modify: `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`
- Tests: `dev/PDF_PARSER_2.0/tests/unit/qa/test_export_validation.py`

**Steps:**
1. Write tests for `assert_no_cyrillic`, `assert_assets_match`, `assert_segments_match` using synthetic Docling docs.
2. Hook validations after each export; on failure mark job as `needs_review` and skip file registration.
3. Run tests; commit `feat: add export QA`.

### Task 5: Structured retry & QA enforcement

**Files:**
- Modify: `dev/PDF_PARSER_2.0/kps/translation/orchestrator.py`
- Modify: `dev/PDF_PARSER_2.0/kps/qa/translation_qa.py`
- Tests: `dev/PDF_PARSER_2.0/tests/test_orchestrator_glossary.py`, `dev/PDF_PARSER_2.0/tests/unit/qa/test_translation_gate.py`

**Steps:**
1. Write tests proving that missing glossary term triggers structured retry and QA failure stops pipeline.
2. Implement JSON-schema retry + final `TermValidator.enforce` fallback.
3. Run pytest; commit `feat: enforce glossary during translation`.

### Task 6: CLI/UI surfacing & path hygiene

**Files:**
- Modify: `dev/PDF_PARSER_2.0/kps/cli.py`
- Backend UI: `dev/ui_service/app/api.py`
- Frontend: `dev/ui_dashboard/src/components/jobs-table.tsx`
- Docs: `docs/QA_EXPORT_CHECKLIST.md`

**Steps:**
1. Ensure CLI writes outputs to `dev/PDF_PARSER_2.0/tmp/...` by default and prints export/QA status (primary/fallback).
2. API returns export report (list of files + warnings); UI shows badges (OK/degraded) and links.
3. Update docs describing pandoc/WeasyPrint requirements and glossary sync routine.
4. Run backend/frontend tests; commit `feat: surface export status in CLI/UI`.

---

Plan complete and saved to `docs/plans/2025-11-12-docling-pipeline-refresh.md`. Two execution options:
1. **Subagent-Driven (this session)**
2. **Parallel Session (new executing-plans run)**
