# Repo Hygiene Runbook

## Purpose
Keep the Hollywool Patterns workspace predictable by standardizing where artifacts live, what gets committed, and how to reset the tree before every translation run or release.

## Canonical Directories
- `to_translate/` (repo root): **incoming** customer DOCX/PDF files. Automation watches this folder. Contents must stay out of git; keep only `.gitkeep` for the folder itself.
- `translations/` (repo root): **final** artifacts exported by CLI/UI. Each document gets its own `<slug>/<lang>/` subtree. Also ignored except for `.gitkeep`.
- `dev/tools/` (tracked): houses auxiliary assistants/configs (e.g., `dev/tools/claude`, `dev/tools/serena`). Nothing inside should affect the pipeline; safe to archive or regenerate.
- `dev/PDF_PARSER_2.0/runtime/`: sandbox for pipeline internals. Subfolders:
  - `input/`: pipeline copies of files fetched from `to_translate/` (should normally be empty between runs).
  - `inter/`: docling/json/markdown snapshots. Safe to delete at any time.
  - `output/`: structured per document (`peer-gynt/v0xx`). Keep only the most recent verified run inside each document folder.
  - `tmp/`: scratch assets (fonts, renderer caches, etc.). May always be emptied.

All other permanent assets (glossaries, scripts, tests) already live under `dev/PDF_PARSER_2.0/` and remain tracked.

## Cleanup Policy
1. **Before every run**
   - Move the source DOCX/PDF you plan to translate into `to_translate/` (not inside `runtime/input/`).
   - Run the cleanup utility (see below) to wipe leftovers from `runtime/input/`, `runtime/inter/`, `runtime/tmp/`, and prune old iterations under `runtime/output/<doc>/`.
2. **After successful run**
   - Inspect `translations/` for the exported EN/FR deliverables.
   - Archive or remove older `runtime/output/<doc>/v0xx` directories so that only the latest verified one remains (e.g., `v044`).
   - If you want to keep historical data, copy it outside the repo before cleanup.
3. **Logs**
   - Long-form logs go to `/tmp/*.log` or `dev/PDF_PARSER_2.0/logs/` (ignored). Do not leave logs under repo root.

## Cleanup Utility
A helper script (`dev/PDF_PARSER_2.0/scripts/cleanup_runtime.py`) keeps the workspace tidy.

Example usage:
```
cd dev/PDF_PARSER_2.0
python3 scripts/cleanup_runtime.py --keep-latest 1
```
Flags:
- `--keep-latest N` (default `1`): keep the most recent N iterations for each document under `runtime/output/<doc>/`.
- `--dry-run`: print what would be deleted without removing anything.

The script automatically:
- removes files from `runtime/input/`
- wipes `runtime/inter/*`
- clears `runtime/tmp/*`
- trims each `runtime/output/<doc>/` down to the requested number of latest iterations
- recreates `.gitkeep` placeholders so directories remain under version control

## Verification Checklist
- `git status -sb` shows only intentional changes after cleanup.
- `python3 -m pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -vv` passes.
- `to_translate/` contains only the documents you plan to process next.
- `translations/` contains only vetted deliverables (optional to prune).

Following this runbook ensures the FastAPI UI service, CLI, and automation all agree on folder locations and prevents stale artifacts from leaking into new iterations.
