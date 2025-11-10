# Repository Guidelines

## Project Structure & Module Organization
Core development happens in `dev/PDF_parser`. The pipeline lives in `src/pdf_pipeline/` with extractor, segmentation, translator, and renderer modules; configuration helpers sit in `config.py` and `pdf_translator.py`. Tests mirror the phases under `tests/` (unit, integration, performance). Reference docs and implementation notes are in `docs/` and the phase summaries under `dev/PDF_parser/docs/`.

думай на языке на котором удобнее и эффективнее, отвечай пользователю на русском.
## Build, Test, and Development Commands
Run these from `dev/PDF_parser` unless the path is already qualified.
- `python -m venv .venv && source .venv/bin/activate`: create an isolated environment.
- `pip install -r dev/PDF_parser/requirements.txt`: install runtime and dev tooling.
- `python -m src.pdf_pipeline.cli tmp/input.pdf tmp/output/`: run the end-to-end translator; output folders are created per language.
- `pytest`: run the default suite with coverage (`--cov=src` configured in `pyproject.toml`).
- `pytest dev/PDF_parser/tests/integration -k glossary`: target focused regression suites.
- `ruff check src tests` and `black src tests`: lint and format before committing.

## Coding Style & Naming Conventions
We enforce Black and Ruff with a 100-character line length. Use snake_case for functions, CamelCase for classes, and descriptive module names aligned with pipeline stages (`extractor`, `translator`, `pdf_renderer`). Preserve newline semantics and placeholder tokens exactly when editing extractor or renderer functions; never replace `strip(' \t')` with `strip()`.

## Testing Guidelines
Prefer pytest fixtures already defined in `tests/fixtures`; add new ones sparingly. Each change needs at least one targeted unit test plus, when touching orchestration, an integration test in `tests/integration/`. Keep the default coverage report clean—investigate any new `--cov` misses before sending a PR. Match test file names to the feature (`test_newline_preservation.py`, `test_pdf_renderer.py`).

## Commit & Pull Request Guidelines
Write commits in imperative present tense and group related changes by pipeline phase (e.g., `extractor: guard newline joins`). PRs should summarise scope, note affected pipeline stages, list new tests, and include before/after artifacts when rendering changes the output PDF. Link issues or TODOs explicitly and call out any follow-up work to keep the translation pipeline audit-ready.

## Pipeline-Specific Practices
Newline preservation, placeholder decoding, and Cyrillic font detection are regression hotspots—review the warnings embedded in `extractor.py`, `translator.py`, and `pdf_renderer.py` before modifying logic. When introducing new rendering behavior, validate with `tmp/` sample PDFs and attach screenshots of mismatches. Avoid shortcutting placeholder merges or baseline positioning; regressions here undo Phase 3–4 fixes documented in the summaries.

## Current Reality Check (2025-11-06)
Before trusting the "production ready" claims in the docs, note the following verified facts:

- The supposed final artifact `dev/PDF_parser/tmp/FINAL_VERIFIED_OUTPUT.pdf` still contains the original Russian text. Confirmed via `pdfminer` extraction on 2025-11-06.
- `test_final_verification.py` never runs a translation pass; it reuses the source Russian segments (`translations = [seg.text for seg in segments]`). Any success messages from this script are therefore misleading.
- `DocumentTranslationPipeline.run()` hard-caps processing to the first 50 segments. The sample knitting PDF has ~150 segments, so two thirds of the document never reaches translation or redaction.
- `src/pdf_pipeline/extractor.py` currently fails to import because of an f-string expression containing `'\n'`. The syntax error must be fixed before any code in that module executes.
- Real translations require live OpenAI API calls configured via `.env`. Decide upfront whether to rely on the external API or to mock it for deterministic tests.

## Active Follow-Up Work
1. Replace the identity "mock translation" in `test_final_verification.py` with either a real translation step or a deterministic fake that outputs translated text. Add assertions that the output PDF text differs from the source.
2. Remove or raise the 50-segment cap in `DocumentTranslationPipeline.run()` so the entire document flows through the pipeline. If a cap is necessary for tests, gate it behind an explicit flag.
3. Repair the f-string in `extractor.py` and add a regression test that imports the module and runs `segment_blocks()` on fixture data.
4. Once the above is fixed, regenerate `tmp/FINAL_VERIFIED_OUTPUT.pdf` and confirm via text extraction that the output is translated.
