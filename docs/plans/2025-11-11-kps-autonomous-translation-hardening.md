# KPS Autonomous Translation Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire glossary guarantees, translation QA, style contracts, TBX validation, and e2e safeguards so KPS truly delivers autonomous high-quality translations.

**Architecture:** Extend the existing KPS pipeline by plugging TermValidator + Structured Outputs into the orchestrator, adding a translation QA gate before export, loading shared style contracts for DOCX/PDF, validating TBX files before touching the DB, and covering everything with an end-to-end regression test.

**Tech Stack:** Python 3.11, PyMuPDF/Docling, Pandoc, WeasyPrint, pytest, Prometheus client, YAML configs.

---

### Task 1: Enforce glossary compliance in TranslationOrchestrator

**Files:**
- Modify: `dev/PDF_PARSER_2.0/kps/translation/orchestrator.py`
- Modify: `dev/PDF_PARSER_2.0/kps/translation/glossary_translator.py`
- Add test: `dev/PDF_PARSER_2.0/tests/unit/translation/test_orchestrator_term_validation.py`

**Step 1: Write the failing test**
```python
# dev/PDF_PARSER_2.0/tests/unit/translation/test_orchestrator_term_validation.py
from kps.translation.term_validator import TermRule, TermValidator
from kps.translation.orchestrator import TranslationOrchestrator, TranslationSegment

class StubClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
    def chat(self, text):
        self.calls.append(text)
        return self.responses.pop(0)

def test_orchestrator_enforces_terms(monkeypatch):
    rules = [TermRule(src_lang="ru", tgt_lang="en", src="Rowan", tgt="Rowan", protected=True)]
    validator = TermValidator(rules)
    orch = TranslationOrchestrator(term_validator=validator, model="gpt-4o-mini")
    segment = TranslationSegment(segment_id="p.test.001.seg0", text="Пихта Rowan", placeholders={})
    # monkeypatch OpenAI calls so first response omits Rowan, second returns it
    ...
    result = orch.translate([segment], doc_slug="demo")
    assert "Rowan" in result.translations[0].segments[0]
```

**Step 2: Run test to verify it fails**
Run: `pytest dev/PDF_PARSER_2.0/tests/unit/translation/test_orchestrator_term_validation.py -k enforce -vv`
Expected: FAIL with assertion that "Rowan" missing.

**Step 3: Write minimal implementation**
```python
# orchestrator.translate loop
violations = []
if self.term_validator:
    violations = self.term_validator.validate(segment.text, translated, source_lang, target_language)
if violations:
    translated = self._retry_with_structured_outputs(...)
    if self.term_validator.validate(...):
        translated = self.term_validator.enforce(translated, source_lang, target_language)
```
Also ensure `GlossaryTranslator` passes `self.term_validator` into orchestrator when constructing chunks.

**Step 4: Run test to verify it passes**
Run: `pytest dev/PDF_PARSER_2.0/tests/unit/translation/test_orchestrator_term_validation.py -vv`
Expected: PASS.

**Step 5: Commit**
```bash
git add dev/PDF_PARSER_2.0/kps/translation/orchestrator.py \
        dev/PDF_PARSER_2.0/kps/translation/glossary_translator.py \
        dev/PDF_PARSER_2.0/tests/unit/translation/test_orchestrator_term_validation.py
git commit -m "feat: enforce glossary via term validator"
```

---

### Task 2: Implement translation QA gate before export

**Files:**
- Add: `dev/PDF_PARSER_2.0/kps/qa/translation_qa.py`
- Modify: `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`
- Add test: `dev/PDF_PARSER_2.0/tests/unit/qa/test_translation_qa.py`

**Step 1: Write the failing test**
```python
# dev/PDF_PARSER_2.0/tests/unit/qa/test_translation_qa.py
from kps.qa.translation_qa import TranslationQAGate
from kps.translation.term_validator import TermRule, TermValidator

def test_translation_qa_blocks_missing_terms():
    validator = TermValidator([TermRule("ru","en","петли","stitches")])
    gate = TranslationQAGate(validator, min_pass_rate=1.0)
    batch = [{
        "id": "seg1",
        "src": "сделайте петли",
        "tgt": "do the thing",
        "src_lang": "ru",
        "tgt_lang": "en"
    }]
    result = gate.check_batch(batch)
    assert not result.passed
    assert result.findings[0].kind == "term_missing"
```

**Step 2: Run test to verify it fails**
Run: `pytest dev/PDF_PARSER_2.0/tests/unit/qa/test_translation_qa.py -k translation_qa -vv`
Expected: Module import error / class not found.

**Step 3: Write minimal implementation**
```python
# dev/PDF_PARSER_2.0/kps/qa/translation_qa.py
from dataclasses import dataclass
class TranslationQAGate:
    def __init__(self, term_validator, min_pass_rate=0.95, ...): ...
    def check_batch(self, segments):
        findings = []
        # validate via term_validator
        # check length ratios, protected tokens, token length
        return QABatchResult(...)
```
Hook it in `UnifiedPipeline.process` right after translations: build batch payloads, run gate, if not passed -> raise/append error and skip export.

**Step 4: Run test to verify it passes**
Run: `pytest dev/PDF_PARSER_2.0/tests/unit/qa/test_translation_qa.py -vv`
Expected: PASS.

**Step 5: Commit**
```bash
git add dev/PDF_PARSER_2.0/kps/qa/translation_qa.py \
        dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py \
        dev/PDF_PARSER_2.0/tests/unit/qa/test_translation_qa.py
git commit -m "feat: add translation QA gate"
```

---

### Task 3: Introduce style contract for DOCX/PDF export

**Files:**
- Add: `dev/PDF_PARSER_2.0/styles/style_map.yml`
- Add: `dev/PDF_PARSER_2.0/styles/pdf.css`
- Add: `dev/PDF_PARSER_2.0/styles/reference.docx`
- Modify: `dev/PDF_PARSER_2.0/kps/export/pandoc_renderer.py`
- Modify: `dev/PDF_PARSER_2.0/kps/cli.py`
- Add test fixture doc: `dev/PDF_PARSER_2.0/tests/fixtures/sample.md`

**Step 1: Write the failing test**
```python
# dev/PDF_PARSER_2.0/tests/integration/test_export_contract.py
from kps.export.pandoc_renderer import render_docx, render_pdf
from pathlib import Path

def test_export_uses_style_contract(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# Heading\n\nBody text\n", encoding="utf-8")
    render_docx(str(md), "styles/style_map.yml", tmp_path / "out.docx")
    assert (tmp_path / "out.docx").exists()
```

**Step 2: Run test to verify it fails**
Run: `pytest dev/PDF_PARSER_2.0/tests/integration/test_export_contract.py -vv`
Expected: FAIL because renderer signature not updated.

**Step 3: Write minimal implementation**
- Create `styles/style_map.yml` describing reference doc + CSS + typographic roles.
- Drop curated `styles/pdf.css` implementing page/typography.
- Add `styles/reference.docx` (copy Pandoc default and checked in Git LFS if large).
- Update `kps/export/pandoc_renderer.py` so `render_docx` reads `style_map.yml`, fetches `reference_docx`, and uses Pandoc `--reference-doc` while `render_pdf` uses WeasyPrint with CSS path from map.
- Update CLI `kps export` command to load `style_map.yml` if not provided and pass both assets.

**Step 4: Run test to verify it passes**
Run: `pytest dev/PDF_PARSER_2.0/tests/integration/test_export_contract.py -vv`
Expected: PASS with doc created.

**Step 5: Commit**
```bash
git add dev/PDF_PARSER_2.0/styles/style_map.yml \
        dev/PDF_PARSER_2.0/styles/pdf.css \
        dev/PDF_PARSER_2.0/styles/reference.docx \
        dev/PDF_PARSER_2.0/kps/export/pandoc_renderer.py \
        dev/PDF_PARSER_2.0/kps/cli.py \
        dev/PDF_PARSER_2.0/tests/integration/test_export_contract.py
git commit -m "feat: add style contract for docx/pdf"
```

---

### Task 4: Validate TBX files before import

**Files:**
- Add: `dev/PDF_PARSER_2.0/kps/interop/tbx_validator.py`
- Modify: `dev/PDF_PARSER_2.0/kps/interop/tbx.py`
- Add test: `dev/PDF_PARSER_2.0/tests/unit/interop/test_tbx_validator.py`

**Step 1: Write the failing test**
```python
# dev/PDF_PARSER_2.0/tests/unit/interop/test_tbx_validator.py
from kps.interop.tbx_validator import validate_tbx_file

def test_invalid_tbx_reports_missing_term_entries(tmp_path):
    tbx = tmp_path / "bad.tbx"
    tbx.write_text("<martif></martif>", encoding="utf-8")
    result = validate_tbx_file(str(tbx))
    assert not result.is_valid
    assert any("termEntry" in issue.message for issue in result.issues)
```

**Step 2: Run test to verify it fails**
Run: `pytest dev/PDF_PARSER_2.0/tests/unit/interop/test_tbx_validator.py -vv`
Expected: FAIL: module missing.

**Step 3: Write minimal implementation**
- Implement `validate_tbx_file()` to parse XML, ensure `<martif>` root, `<termEntry>/<langSet xml:lang>/<term>` combos, check ISO-like language codes, produce dataclass result.
- In `kps/interop/tbx.py`, call validator at start of `import_tbx_to_db`; abort with RuntimeError if invalid.

**Step 4: Run test to verify it passes**
Run: `pytest dev/PDF_PARSER_2.0/tests/unit/interop/test_tbx_validator.py -vv`
Expected: PASS.

**Step 5: Commit**
```bash
git add dev/PDF_PARSER_2.0/kps/interop/tbx_validator.py \
        dev/PDF_PARSER_2.0/kps/interop/tbx.py \
        dev/PDF_PARSER_2.0/tests/unit/interop/test_tbx_validator.py
git commit -m "feat: add tbx validation"
```

---

### Task 5: Add end-to-end regression proving translation and QA work

**Files:**
- Add: `dev/PDF_PARSER_2.0/tests/e2e/test_translation_pipeline.py`
- Modify: `dev/PDF_parser/manual_tests/test_final_verification.py`

**Step 1: Write the failing test**
```python
# dev/PDF_PARSER_2.0/tests/e2e/test_translation_pipeline.py
from kps.translation.orchestrator import TranslationOrchestrator, TranslationSegment
from kps.translation.term_validator import TermValidator, TermRule
from kps.qa.translation_qa import TranslationQAGate

def test_pipeline_translates_and_passes_qa(monkeypatch):
    validator = TermValidator([TermRule("ru","en","петля","stitch")])
    orch = TranslationOrchestrator(term_validator=validator)
    segs = [TranslationSegment("p.demo.seg0", "Свяжите петлю Rowan", {})]
    # monkeypatch openai call to deterministic output missing term first time, fixed on retry
    result = orch.translate(segs, doc_slug="demo")
    gate = TranslationQAGate(validator)
    batch = [{"id": segs[0].segment_id, "src": segs[0].text, "tgt": result.translations[0].segments[0], "src_lang": "ru", "tgt_lang": "en"}]
    qa = gate.check_batch(batch)
    assert qa.passed
    assert result.translations[0].segments[0] != segs[0].text
```

**Step 2: Run test to verify it fails**
Run: `pytest dev/PDF_PARSER_2.0/tests/e2e/test_translation_pipeline.py -vv`
Expected: FAIL because orchestrator still copies segments without validator integration.

**Step 3: Write minimal implementation**
- Update e2e test scaffolding to patch OpenAI client responses and assert translation differs.
- Update legacy manual test `dev/PDF_parser/manual_tests/test_final_verification.py` to call the new orchestrator (or at minimum assert `translated != source`).

**Step 4: Run test to verify it passes**
Run: `pytest dev/PDF_PARSER_2.0/tests/e2e/test_translation_pipeline.py -vv`
Expected: PASS.

**Step 5: Commit**
```bash
git add dev/PDF_PARSER_2.0/tests/e2e/test_translation_pipeline.py \
        dev/PDF_parser/manual_tests/test_final_verification.py
git commit -m "test: cover translation qa e2e"
```

---

### Task 6: Wire CI to guard the new surface

**Files:**
- Add: `.github/workflows/kps-ci.yml`

**Step 1: Write the failing test**
```yaml
# .github/workflows/kps-ci.yml
name: kps-ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r dev/PDF_PARSER_2.0/requirements.txt
      - run: pip install weasyprint pandocfilters pytest
      - run: pytest dev/PDF_PARSER_2.0/tests -vv
```

**Step 2: Run test to verify it fails**
Run: `act push` (if available) or validate via `yamllint`. Expected: failure because workflow missing.

**Step 3: Write minimal implementation**
- Save the workflow file above.

**Step 4: Run test to verify it passes**
Run: `act push` or `gh workflow list` (spot-check). Expected: workflow recognized.

**Step 5: Commit**
```bash
git add .github/workflows/kps-ci.yml
git commit -m "chore: add CI for kps"
```

---

Plan complete and saved to `docs/plans/2025-11-11-kps-autonomous-translation-hardening.md`. Two execution options:

1. **Subagent-Driven (this session)** – dispatch fresh subagent per task with reviews between steps.
2. **Parallel Session (separate)** – open a new session using superpowers:executing-plans to process tasks in batches.

Which approach should we take?
