# Root Declutter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the repo root minimal: only `README.md`, `docs/`, `dev/`, `to_translate/`, `translations/`, `глоссарий.json`, `.git*` should be visible. All other auxiliary artifacts (coverage, backup data, misc configs) need to move into dedicated subdirectories or be ignored.

**Architecture:** Create a `support/` folder to host optional data (e.g., `.coverage`, `htmlcov`, `.serena`, `.claude`), expand `.gitignore`, and document the layout in README + runbook. Ensure automation still finds glossary and the only user touchpoints remain the IO dirs.

**Tech Stack:** shell, git, markdown.

### Task 1: Inventory non-whitelisted root entries

**Files:** n/a

Steps:
1. `ls -a` and identify everything beyond {`.git*`, `.github/`, `.gitignore`, `.coverage`, `.claude`, `.serena`, `.ci`, `README.md`, `docs/`, `dev/`, `to_translate/`, `translations/`, `глоссарий.json`}. Specifically note `data/`, `htmlcov/`, `.coverage`, `.claude/`, `.serena/`, etc.
2. Decide for each entry: delete? move under `support/`? keep (document why).

### Task 2: Create `support/` bundle and move auxiliary dirs/files

**Files:**
- Create directory: `support`
- Move: `.claude`, `.serena`, `htmlcov`, `data/translation_memory.db` (if reintroduced later), `.coverage` file (rename `support/coverage/.coverage`).

Steps:
1. `mkdir -p support/meta support/coverage`.
2. `git mv .claude support/meta/.claude` (if tracked; otherwise update ignores and move).
3. Same for `.serena`. If directories are not tracked, just move and add to `.gitignore` after.
4. Move `htmlcov` and `.coverage` into `support/coverage/` or delete if regenerateable. (Since coverage should be ignored, best to remove and ensure `.gitignore` catches.)

### Task 3: Address `data/` and other strays

**Files:**
- If `data/` only needed for scratch, move contents into `support/data/` or delete.
- Ensure `глоссарий.json` stays in root.
- Document final location of translation memory (already under `dev/PDF_PARSER_2.0/data`).

Steps:
1. Inspect `data/`; delete if empty. If not, move into support (e.g., `support/data/archive/`).
2. Update `.gitignore` to ignore `support/` contents except README.

### Task 4: Update documentation

**Files:**
- Modify `README.md` root layout section.
- Add short note to `docs/runbooks/repo-hygiene.md` about new `support/` folder.

Content:
- Explain that support artifacts live under `support/` (not synced) and that root remains minimal.
- Mention that `support/` is optional for local tooling; safe to delete/regenerate.

### Task 5: Verification

Steps:
1. `ls -a` to confirm root now only has allowed entries.
2. `git status -sb` clean (apart from tracked moves/updates).
3. `python3 -m pytest ...` not strictly necessary unless code changed; skip unless touched.
4. Summary for user.
