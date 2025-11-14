# Repo Grooming Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove stale artifacts, consolidate shared assets, and document a clean workspace layout so the translation stack runs predictably.

**Architecture:** Canonical runtime assets live inside `dev/PDF_PARSER_2.0`, while user-facing IO stays at repo root. We will route every implicit file path through project-root aware helpers, prune previous run artifacts (keeping the latest sample only), and document/automate cleanup. `.gitignore` rules will enforce the structure going forward.

**Tech Stack:** Python 3.11 (kps pipeline, utility scripts), shell (cleanup), Git, Markdown docs.

### Task 1: Document workspace hygiene

**Files:**
- Modify: `README.md`
- Create: `docs/runbooks/repo-hygiene.md`

**Step 1: Draft repo hygiene runbook**
- Describe canonical directories (`to_translate/`, `translations/`, `dev/PDF_PARSER_2.0/runtime`).
- Document policy: keep only latest verified outputs (v044), prune `runtime/inter/*`, store sample input under `to_translate/`.
- Include commands for running the cleanup utility (Task 3) and expectations for CI/tests.

**Step 2: Update root README**
- Summarize new cleanup policy (1 paragraph + bullet list under “Translation IO”).
- Link to the runbook for detailed steps.

**Step 3: Proofread docs**
- `vale` or manual read; ensure Markdown lint passes (`markdownlint` optional).

**Step 4: Commit-ready check**
- `git status -sb` to confirm only intended doc changes.

### Task 2: Consolidate translation memory path

**Files:**
- Modify: `dev/PDF_PARSER_2.0/kps/core/unified_pipeline.py`
- Modify: `dev/PDF_PARSER_2.0/docs/SEMANTIC_MEMORY_ARCHITECTURE.md`
- Modify: `dev/PDF_PARSER_2.0/docs/runbooks/semantic-memory.md`
- Remove: `data/translation_memory.db` (root duplicate)

**Step 1: Implement project-root aware default**
- In `unified_pipeline.py`, introduce `PROJECT_ROOT = Path(__file__).resolve().parents[2]` and `DEFAULT_MEMORY_PATH = PROJECT_ROOT / "data" / "translation_memory.db"`.
- Update `PipelineConfig.memory_path` default and logic to coerce to `str(DEFAULT_MEMORY_PATH)` when `None`.

**Step 2: Adjust docs**
- Mention absolute-path behavior and clarify commands assume execution from `dev/PDF_PARSER_2.0`.

**Step 3: Remove duplicate DB**
- Delete root `data/translation_memory.db` after confirming canonical file exists under `dev/PDF_PARSER_2.0/data`.

**Step 4: Tests**
- `cd dev/PDF_PARSER_2.0 && python3 -m pytest tests/test_translation_system.py -vv`.

### Task 3: Runtime cleanup + automation

**Files:**
- Modify: `dev/PDF_PARSER_2.0/runtime/*` (delete stale artifacts; add `.gitkeep` placeholders)
- Create: `dev/PDF_PARSER_2.0/runtime/.gitkeep`, plus `.gitkeep` inside `input/`, `inter/`, `inter/baselines`, `inter/json`, `inter/markdown`, `output/peer-gynt`, `tmp`.
- Create: `dev/PDF_PARSER_2.0/scripts/cleanup_runtime.py`

**Step 1: Move sample doc**
- Move `КАРДИГАН peer gynt.docx` from repo root (and runtime/input copy) into `to_translate/`.
- Ensure `.gitignore` still keeps contents ignored.

**Step 2: Purge runtime artifacts**
- Delete `dev/PDF_PARSER_2.0/runtime/inter/*`, `runtime/output/*` except `peer-gynt/v044`, remove `runtime/tmp/*`, `runtime/input/*` (since source now under `to_translate/`).

**Step 3: Add `.gitkeep`**
- Drop placeholder files so directories stay in repo despite `.gitignore`.

**Step 4: Implement cleanup utility**
- Script accepts `--keep-latest N` (default 1) for `peer-gynt` outputs, wipes `inter/*`, `tmp/*`, and empties `runtime/input`.
- Include safety checks (confirm path exists, require `peer-gynt` subdir). Use `pathlib` + `shutil.rmtree`.

**Step 5: Dry-run**
- Run `python3 scripts/cleanup_runtime.py --keep-latest 1 --dry-run` (should only report actions).
- Run without `--dry-run` to ensure directories cleaned.

**Step 6: Verify pipeline still runs**
- `cd dev/PDF_PARSER_2.0 && python3 -m pytest tests/test_translation_system.py -vv` (reuse from Task 2 if close).

### Task 4: Expand ignore rules & housekeeping

**Files:**
- Modify: `.gitignore`
- Modify: `dev/PDF_PARSER_2.0/.gitignore`
- Remove: `htmlcov/` (root) and `dev/PDF_PARSER_2.0/htmlcov/`
- Remove: `dev/PDF_PARSER_2.0/tmp/*` leftovers after Task 3 (redundant but ensure)

**Step 1: Root ignores**
- Ignore `/htmlcov/`, `/data/translation_memory.db` (since canonical lives in subproject), `/dev/PDF_PARSER_2.0/runtime/**` except `.gitkeep`, `/translations/*`, `/to_translate/*`, `/logs/`, etc.

**Step 2: Subproject ignores**
- Ensure runtime subtree ignored there as well (mirror `.gitkeep` exceptions), add `/runtime/tmp/`, `/runtime/input/`, `/runtime/inter/`, coverage reports, `/tmp/`.

**Step 3: Delete existing coverage dirs**
- Remove root `htmlcov` and `dev/PDF_PARSER_2.0/htmlcov` directories to reduce clutter.

**Step 4: Final git status**
- `git status -sb` to ensure only intended changes.
- Document summary in commit message later.

