# Dev Folder Declutter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Group all standalone test/demo scripts under themed subdirectories inside `dev/PDF_PARSER_2.0/` so the root of that project contains only maintained modules (`kps/`, `tests/`, `docs/`, etc.).

**Architecture:** Introduce new folders under `dev/PDF_PARSER_2.0/`: `reports/` (markdown analyses), `lab/` (ad-hoc CLI/test experiments), `legacy_tests/` (standalone PyMuPDF demos), `scripts/diagnostics/`. Move each existing `.py` or `.md` file into the right bucket and update README references. Adjust `.gitignore` entries if needed.

**Tech Stack:** Shell + git + markdown.

### Task 1: Classify files

**Steps:**
1. Run `ls dev/PDF_PARSER_2.0/*.py dev/PDF_PARSER_2.0/*.md 2>/dev/null` and map each file to one of: `lab/`, `reports/`, `legacy_tests/`, `scripts/`.
2. Record mapping in a table (can be pasted into plan notes) to avoid confusion during moves.

### Task 2: Create target directories

**Files:**
- Create directories: `dev/PDF_PARSER_2.0/lab`, `dev/PDF_PARSER_2.0/legacy_tests`, `dev/PDF_PARSER_2.0/reports`, `dev/PDF_PARSER_2.0/scripts/diagnostics`

Steps: `mkdir -p ...` (use `git add` after creation).

### Task 3: Move files

**Steps:**
1. Move Markdown reports (`*_report.md`, `*_analysis.md`, `translation_engine_analysis.md`, etc.) into `reports/` via `git mv`.
2. Move experimental single-file tests (e.g., `test_exact_flow.py`, `test_multiline_blocks.py`, `test_output_show_pdf_page.py`, `tmp.docx`) into `legacy_tests/` (rename `tmp.docx` to `legacy_tests/tmp.docx`).
3. Move utility scripts (`compare_blocks.py`, `debug_block_structure.py`, `analyze_latest.py`, etc.) into `scripts/diagnostics/`.
4. Keep production `tests/` package untouched.

### Task 4: Update documentation & tooling

**Files:**
- Modify `dev/PDF_PARSER_2.0/README.md` (add section “Legacy experiments” referencing new folders).
- Update `.gitignore` if new directories need special handling (e.g., `legacy_tests/output/`).

### Task 5: Verification

**Steps:**
1. `ls dev/PDF_PARSER_2.0` ensure only curated directories remain at top level.
2. `pytest` not needed (code unaffected), but run `git status -sb` and confirm no missing references.
