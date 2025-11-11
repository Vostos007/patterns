# Translation Platform Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a translation pipeline that rewrites inputs via Docling, enforces QA/TBX validations, and exposes the flow through the shadcn UI + FastAPI so users can upload and download finished artifacts.

**Architecture:** Keep DoclingDocument as the source of truth, push translations back into it, and let Docling's backends (DOCX/HTML) generate outputs that inherit the original layout + style contract. QA operates as a fail-closed layer before export, and the FastAPI job runner orchestrates CLI executions while the Next.js dashboard polls for downloadable files.

**Tech Stack:** Python 3.11, Docling 2.x, FastAPI, typer CLI, pytest, Next.js 14 (App Router, shadcn/ui), Tailwind.

---

### Task 1: Persist DoclingDocument through extraction → pipeline (foundation for Docling writer)

**Files:**
- Modify: `dev/PDF_PARSER_2.0/kps/core/document.py`
- Modify: `dev/PDF_PARSER_2.0/kps/extraction/docling_extractor.py`
- Modify: `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`
- Test: `dev/PDF_PARSER_2.0/tests/test_segmentation.py` (or new `tests/unit/test_docling_capture.py`)

**Step 1: Write failing test**

```python
# dev/PDF_PARSER_2.0/tests/unit/test_docling_capture.py
from kps.extraction.docling_extractor import DoclingExtractor

def test_extractor_retains_docling_document(tmp_path):
    extractor = DoclingExtractor()
    doc = extractor.extract_document(tmp_path / "sample.docx", slug="sample")
    assert doc.docling_document is not None  # placeholder expectations
```

**Step 2: Run test to see failure**

`PYTHONPATH=dev/PDF_PARSER_2.0 dev/PDF_PARSER_2.0/.venv/bin/python -m pytest dev/PDF_PARSER_2.0/tests/unit/test_docling_capture.py -q`

Expected: fails because `KPSDocument` lacks `docling_document`.

**Step 3: Implement minimal code**
- Extend `ContentBlock`/`KPSDocument` dataclasses with optional `docling_document` field (likely via composition or new wrapper `ExtractedDocument`).
- Update `DoclingExtractor.extract_document` to attach `self.last_docling_document` onto the object returned.
- Extend `UnifiedPipeline.process` to store `self.docling_document` per run (e.g., `self.last_docling_document = getattr(document, "docling_document", None)`).

**Step 4: Re-run test**

Same pytest command; expect PASS.

**Step 5: Commit**

```bash
git add dev/PDF_PARSER_2.0/kps/core/document.py \
        dev/PDF_PARSER_2.0/kps/extraction/docling_extractor.py \
        dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py \
        dev/PDF_PARSER_2.0/tests/unit/test_docling_capture.py
git commit -m "feat: retain docling document in extraction pipeline"
```

---

### Task 2: Apply translations back into DoclingDocument via doc_ref map

**Files:**
- Create: `dev/PDF_PARSER_2.0/kps/export/docling_writer.py`
- Modify: `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`
- Test: `dev/PDF_PARSER_2.0/tests/unit/test_docling_writer.py`

**Step 1: Write failing tests**

```python
# dev/PDF_PARSER_2.0/tests/unit/test_docling_writer.py
from kps.export.docling_writer import apply_translations

def test_apply_translations_updates_text_nodes(docling_doc_fixture, segments):
    apply_translations(docling_doc_fixture, segments, ["Translated"])
    assert docling_doc_fixture.resolve_ref("#/texts/0").text == "Translated"
```

Include fixtures mapping `doc_ref` to `TranslationSegment`.

**Step 2: Run pytest**

`PYTHONPATH=dev/PDF_PARSER_2.0 dev/PDF_PARSER_2.0/.venv/bin/python -m pytest dev/PDF_PARSER_2.0/tests/unit/test_docling_writer.py -q`

Expect failure (module missing).

**Step 3: Implement**

- Build helper that deep-copies DoclingDocument, iterates `segments` list, resolves each `segment.doc_ref` using `RefItem.resolve` or `docling_doc.resolve_ref`, and assigns new `.text`.
- Handle missing refs via warnings and metrics.
- Return tuple `(updated_docling_doc, missing_refs)` for logging.

**Step 4: Re-run pytest** – expect pass.

**Step 5: Commit** with message `feat: map translations back into docling document`.

---

### Task 3: Route exports through Docling backends + style contract

**Files:**
- Create: `dev/PDF_PARSER_2.0/kps/export/docling_renderer.py`
- Modify: `dev/PDF_PARSER_2.0/kps/export/__init__.py`
- Modify: `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`
- Modify: `dev/PDF_PARSER_2.0/kps/export/docx_renderer.py` (deprecate or fallback)
- Config: `dev/PDF_PARSER_2.0/styles/style_map.yml` (ensure reference doc paths)
- Test: `dev/PDF_PARSER_2.0/tests/integration/test_cli_docling_export.py`

**Step 1: Write failing integration test** verifying CLI produce DOCX/PDF with zero Cyrillic for sample fixture and that `.docx` roundtrips (inspect docx paragraphs for Cyrillic).

**Step 2: Run test** – expect failure due to current exporter.

**Step 3: Implement renderer**
- `DoclingRenderer` should accept DoclingDocument + formats array, call Docling `MsWordDocumentBackend` to emit DOCX (optionally referencing `styles/reference.docx`).
- Use HTML backend output → existing `render_pdf` for PDF; use Markdown backend for `.md`.
- Update `UnifiedPipeline._export_translation_for_format` to branch: if `self.docling_document` present, call new renderer; else fallback.

**Step 4: Run CLI integration test + smoke command**

```
PYTHONPATH=dev/PDF_PARSER_2.0 dev/PDF_PARSER_2.0/.venv/bin/python -m pytest dev/PDF_PARSER_2.0/tests/integration/test_cli_docling_export.py -q
PYTHONPATH=dev/PDF_PARSER_2.0 dev/PDF_PARSER_2.0/.venv/bin/python -m kps.cli translate "КАРДИГАН peer gynt.docx" --lang en --output tmp/verify_en
```

**Step 5: Commit** `feat: export via docling renderer`.

---

### Task 4: Harden QA/validators (TermValidator integration, structured retry, TBX gate)

**Files:**
- Modify: `dev/PDF_PARSER_2.0/kps/translation/orchestrator.py`
- Modify: `dev/PDF_PARSER_2.0/kps/qa/translation_qa.py`
- Modify: `dev/PDF_PARSER_2.0/kps/interop/tbx_validator.py`
- CLI: `dev/PDF_PARSER_2.0/kps/cli.py`
- Tests: `dev/PDF_PARSER_2.0/tests/test_orchestrator_enhanced.py`, new `tests/integration/test_tbx_validator.py`, new `tests/integration/test_translation_qa.py`

**Steps per sub-feature:**
1. **Structured retry**
   - Write test verifying orchestrator retries with structured schema when term missing.
   - Implement `_retry_with_structure` using OpenAI `response_format` (already stubbed) and ensure fallback `enforce` runs.
2. **QA enforcement**
   - Add test for `TranslationQAGate` blocking missing protected term.
   - In pipeline, if QA fails, mark job failed and emit JSON report.
3. **TBX CLI gate**
   - Add CLI command `validate-tbx` and auto-run before glossary import; tests assert invalid files exit with error.
4. **Run targeted pytest** + `kps.cli` sample translation (should pass QA automatically with new rules).
5. **Commit** `feat: enforce terminology QA and TBX validation`.

---

### Task 5: Wire FastAPI + shadcn UI for upload → download flow

**Files:**
- Backend: `dev/ui_service/app/api.py`, `dev/ui_service/app/jobs.py`, `dev/ui_service/tests/test_jobs_api.py`
- Frontend: `dev/ui_dashboard/src/app/page.tsx`, `src/components/upload-panel.tsx`, `src/components/jobs-table.tsx`, `src/lib/api.ts`
- Styles: `dev/ui_dashboard/src/app/globals.css`

**Steps:**
1. **Backend enrichment**
   - Write FastAPI test ensuring `/jobs` POST stores metadata (source file, target lang) and `/jobs/{id}` returns download URLs when artifacts exist.
   - Implement background task invoking CLI with `PYTHONPATH=...` env + `DOCROOT/tmp/jobs/{job_id}` output, watching for completion.
   - Ensure API_BASE defaults to `http://localhost:9000` and CORS allows dashboard origin.
2. **Frontend upload panel**
   - Use shadcn `Card`, `Input`, and `Button` to build drag/drop + language select; call `POST /jobs` via `fetch` that streams status.
   - After submit, poll `/jobs/{id}` every 5s (existing `JobsTable` hook) and display download buttons for docx/pdf/md/json.
   - Fix console error by exporting `API_BASE` from `src/lib/api.ts` and handling fetch errors with toast.
3. **Tests**
   - Backend: `pytest dev/ui_service/tests/test_jobs_api.py -q`
   - Frontend: `cd dev/ui_dashboard && npm run lint && npm run test`
4. **Manual verification**
   - Start API (`uvicorn app.main:app --reload`) and Next.js dev server (`npm run dev -- --port 3050`), upload sample DOCX, confirm downloads.
5. **Commit** `feat: add job uploads and download UI flow`.

---

### Task 6: End-to-end verification + cleanup

**Steps:**
1. Run full CLI translation on provided DOCX, inspect `tmp/output_en/` docx/pdf for Cyrillic (python script scanning paragraphs).
2. Capture artifacts for UI download demo; ensure FastAPI logs show QA pass.
3. Final test suites: `pytest dev/PDF_PARSER_2.0/tests -q`, `pytest dev/ui_service/tests -q`, `cd dev/ui_dashboard && npm run lint && npm run test`.
4. Summarize results, note any flaky areas.
5. Commit `chore: verify pipeline e2e`.

---

Plan complete and saved. Defaulting to Subagent-Driven execution in this session using superpowers:executing-plans instructions.
