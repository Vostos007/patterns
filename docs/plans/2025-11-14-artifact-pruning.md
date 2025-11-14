# Artifact Pruning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove stale binary artifacts, nested runtimes, and unused production dumps so that only source code, configs, and canonical IO folders remain tracked.

**Architecture:** We will (1) inventory tracked heavy files (PDF/DOCX/JSON dumps) inside `dev/PDF_PARSER_2.0`, (2) delete obvious leftovers (duplicate runtimes, production_artifacts, old build/doc exports, tracked test outputs), (3) expand `.gitignore` patterns so the same noise cannot reappear, and (4) update documentation/runbooks to reflect the leaner folder layout.

**Tech Stack:** Python 3.9 (scripts), Bash, Git, Markdown docs.

### Task 1: Inventory large/tracked binary artifacts

**Files:**
- n/a (read-only)

**Step 1:** Run discovery script to list tracked files over 50KB with extensions `.pdf`, `.docx`, `.html`, `.json` outside runtime paths.
```bash
python3 - <<'PY'
from pathlib import Path
repo = Path('.')
target_ext = {'.pdf', '.docx', '.html', '.json'}
for path in repo.rglob('*'):
    if path.is_file() and path.suffix.lower() in target_ext:
        if 'runtime' in path.parts:
            continue
        size = path.stat().st_size / 1024
        print(f"{size:9.1f} KB  {path}")
PY
```
**Step 2:** Mark candidates for deletion (expected: `dev/PDF_PARSER_2.0/production_artifacts/*`, `dev/PDF_PARSER_2.0/build/doc.*`, tracked `test_*_output.pdf`, `.docx`, `.md` dumps, nested `dev/PDF_PARSER_2.0/dev/...`).

### Task 2: Delete duplicate runtimes and production dumps

**Files:**
- Remove directory: `dev/PDF_PARSER_2.0/dev/PDF_PARSER_2.0`
- Remove directory: `dev/PDF_PARSER_2.0/production_artifacts`
- Remove directory: `dev/PDF_PARSER_2.0/build`

**Steps:**
1. `rm -rf dev/PDF_PARSER_2.0/dev/PDF_PARSER_2.0`
2. `rm -rf dev/PDF_PARSER_2.0/production_artifacts`
3. `rm -rf dev/PDF_PARSER_2.0/build`
4. `git status -sb` to confirm deletions staged.

### Task 3: Drop tracked test/demo outputs and tmp files

**Files:**
- Remove: `dev/PDF_PARSER_2.0/test_*_output.pdf`, `test_enhanced_docx.docx`, `test_output.md`, `tmp.docx`
- Remove: `dev/PDF_PARSER_2.0/csr_page1_pipeline_test_report.md`? (Only if obsolete; confirm Step 1 notes.)
- Modify `.gitignore` (root + subproject) to block these patterns (`test_*_output.pdf`, `tmp.docx`, `/production_artifacts/`, `/build/`).

**Steps:**
1. For each tracked artifact run `rg` to ensure no code imports it (only script self references). Document results.
2. `git rm dev/PDF_PARSER_2.0/test_exact_flow_output.pdf ...` (list all). Include `.docx/.md` sample outputs.
3. Update `.gitignore` files with new patterns.

### Task 4: Update docs & runbooks referencing removed folders

**Files:**
- Modify: `docs/plans/2025-11-12-production-deployment-guide.md`
- Modify: `dev/PDF_PARSER_2.0/README.md`
- Any other doc referencing `production_artifacts` or nested runtime.

**Steps:**
1. Search `rg -n "production_artifacts" -n` and rewrite instructions to point to `translations/` outputs or new cleanup script.
2. Search for `dev/PDF_PARSER_2.0/dev/PDF_PARSER_2.0` references (should be none; if found, update).
3. Mention cleanup policy from repo hygiene runbook.

### Task 5: Verification

**Files:**
- n/a (commands)

**Steps:**
1. `git status -sb` ensure only intended deletions/modifications.
2. `python3 -m pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -vv` (sanity after file removals).
3. Document results in final summary.
