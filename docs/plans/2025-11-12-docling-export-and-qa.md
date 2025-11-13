# Docling Export & QA Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a translation pipeline that always translates via docling, exports DOCX/PDF through controlled templates, and enforces QA using `/Users/vostos/Dev/Hollywool patterns/глоссарий.json` as the terminology source.

**Architecture:** Docling handles extraction for DOCX/PDF alike; translations are written back into DoclingDocument, then rendered either via pandoc+reference DOCX or HTML+WeasyPrint. QA runs both before export (glossary/term checks) and after export (re-Docling the output to guarantee nothing was lost). Fallbacks emit degraded statuses but never silently drop content.

**Tech Stack:** Python 3.11, Docling 2.x, pandoc CLI, WeasyPrint, python-docx, pytest, Next.js (for QA reporting in UI).

---

### Task 1: Wire glossary.json into GlossaryManager

**Files:**
- Modify: `dev/PDF_PARSER_2.0/kps/translation/glossary/manager.py`
- Modify: `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`
- Test: `dev/PDF_PARSER_2.0/tests/unit/test_glossary_manager.py`

**Steps:**
1. Write failing test ensuring `GlossaryManager(gjson)` loads JSON entries (including protected tokens) and `get_all_entries()` returns them.
2. Run test (expect fail because JSON unsupported).
3. Implement loader that detects `.json`, strips comments, maps entries into `GlossaryEntry`.
4. Update pipeline config default to `/Users/vostos/Dev/Hollywool patterns/глоссарий.json` and log loaded count.
5. Re-run pytest; git commit `feat: support json glossary`.

### Task 2: Stable Docling exporter (DOCX/PDF)

**Files:**
- Create: `dev/PDF_PARSER_2.0/kps/export/docling_pipeline.py`
- Modify: `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`
- Modify: `dev/PDF_PARSER_2.0/kps/export/__init__.py`
- Test: `dev/PDF_PARSER_2.0/tests/integration/test_docling_exports.py`

**Steps:**
1. Write integration test stubs for `render_docx_from_docling` (skips if pandoc absent) and `render_pdf_from_docling` (ensures order of tables/images preserved).
2. Implement docling pipeline: HTML export, pandoc call with reference doc, WeasyPrint PDF, plus fallbacks (structure builder, ReportLab placeholder) with warnings.
3. Expose new API via `__all__`, update pipeline to branch per format (docx/pdf/html/markdown) and drop legacy `render_docx_inplace` except as final fallback.
4. Run integration tests (expect PASS/pandoc skip). Commit `feat: add docling export pipeline`.

### Task 3: Post-export QA module

**Files:**
- Create: `dev/PDF_PARSER_2.0/kps/qa/export_validation.py`
- Modify: `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`
- Tests: `dev/PDF_PARSER_2.0/tests/unit/test_export_validation.py`

**Steps:**
1. Write tests covering `assert_no_cyrillic(docling_doc)`, `assert_asset_counts_match(original, exported)`, `assert_segments_match(original_segments, exported_docling)`.
2. Implement functions using Docling re-parse of exported files.
3. After each export, re-run validation; on failure raise and mark job as error; on success log "QA passed".
4. Run unit tests + targeted CLI; commit `feat: add export QA validators`.

### Task 4: Translation QA improvements & structured retries

**Files:**
- Modify: `dev/PDF_PARSER_2.0/kps/translation/orchestrator.py`
- Modify: `dev/PDF_PARSER_2.0/kps/qa/translation_qa.py`
- Tests: `dev/PDF_PARSER_2.0/tests/test_orchestrator_enhanced.py`, `dev/PDF_PARSER_2.0/tests/unit/test_translation_qa.py`

**Steps:**
1. Add tests verifying that violations trigger `_retry_with_structure`, and QA gate catches missing glossary tokens.
2. Implement structured retry payload using JSON schema, fallback `enforce()`; ensure QA results bubble up (pipeline stops on fail).
3. Run tests; commit `feat: enforce glossary with retries`.

### Task 5: PDF layout fallback (ReportLab)

**Files:**
- Create: `dev/PDF_PARSER_2.0/kps/export/pdf_reportlab.py`
- Modify: `dev/PDF_PARSER_2.0/kps/export/docling_pipeline.py`
- Test: `dev/PDF_PARSER_2.0/tests/integration/test_pdf_reportlab.py`

**Steps:**
1. Write test using synthetic DoclingDocument with bbox; ensure fallback produces PDF with same number of paragraphs/images when WeasyPrint unavailable.
2. Implement simple ReportLab renderer (A4, iterate blocks, draw strings/images by bbox proportions).
3. Wire fallback: if WeasyPrint raises → call ReportLab; log warning.
4. Re-run tests; commit `feat: add PDF fallback renderer`.

### Task 6: CLI/UI surfacing + docs

**Files:**
- Modify: `dev/PDF_PARSER_2.0/kps/cli.py`
- Backend UI service: `dev/ui_service/app/api.py`
- Frontend: `dev/ui_dashboard/src/components/jobs-table.tsx`
- Docs: `docs/QA_EXPORT_CHECKLIST.md`

**Steps:**
1. Update CLI output to show export path (primary/fallback) + QA status.
2. API: include export report (warnings/errors) in job payload; UI: show badges (OK / degraded / failed) and highlight missing pandoc/WeasyPrint.
3. Add doc describing pandoc requirement + fallback semantics.
4. Run backend tests (`pytest dev/ui_service/tests -q`) + frontend lint/tests.
5. Commit `feat: surface export QA in CLI/UI`.

---

Plan complete and saved to `docs/plans/2025-11-12-docling-export-and-qa.md`. Two execution options:
1. **Subagent-Driven (this session)**
2. **Parallel Session (new executing-plans run)**
