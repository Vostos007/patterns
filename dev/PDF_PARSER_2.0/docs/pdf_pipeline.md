# PDF Export Pipeline (Snapshot – Nov 2025)

## 1. Purpose
- Keep the existing Docling → HTML → PDF chain intact.
- Capture the reference layout (HTML + CSS) we feed into Playwright fallback so we can diff future changes.
- Provide an optional overlay mode (`--layout-preserve`) that swaps текст прямо в исходном PDF, не трогая фон/таблицы.

## 2. Required environment
- `OPENAI_API_KEY` loaded (via `.env`).
- `uv` 0.9+ and Python 3.11 are used everywhere.
- WeasyPrint is optional; when it is missing, we fall back to Playwright.
- Playwright dependencies:
  ```bash
  uv pip install --python 3.11 playwright>=1.45.0
  uv run --python 3.11 playwright install chromium
  ```
- **Overlay dependencies:**
  ```bash
  pip install "pymupdf>=1.26" langdetect argostranslate pymupdf-fonts
  python scripts/install_argos_models.py  # один раз, скачивает ru/en/fr модели
  ```

## 3. Running the full CLI
```bash
cd dev/PDF_PARSER_2.0
uv run --python 3.11 -m kps.cli translate \
  "runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf" \
  --lang en \
  --format docx,pdf,markdown \
  --skip-translation-qa \
  --verbose
```
- По умолчанию CLI сам находит `runtime/` относительно корня репозитория. Для нестандартной структуры задавайте `--root /abs/path/to/layout`.
- Output root: `runtime/output/<slug>/v00X/` (HTML snapshot, DOCX, PDF, Markdown).
- Overlay режим (ru/en/fr) включается так:
  ```bash
  uv run --python 3.11 -m kps.cli translate \
    "runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf" \
    --lang en,fr \
    --format docx,pdf,markdown \
    --layout-preserve
  ```
  Результат: помимо стандартных экспортов, появится папка `runtime/output/.../layout/` с PDF, где текст заменён в исходной разметке.
- When WeasyPrint fails you will see `PDF fallback renderer used: pdf-browser`.

## 4. Layout snapshot
- HTML snapshots are written via `_write_docling_html`.
- Latest reference (as of `v001`):
  `runtime/output/csr-report-jan-1-2025-to-jul-30-2025-1---page1/v001/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1_en.html`
- CSS contract lives in `styles/pdf.css` (plus style map referenced by `_resolve_pdf_css`).
- Any layout change should diff this HTML + CSS pair before/after.

## 5. Verification checklist (manual for now)
1. Ensure Markdown export still contains the expected table header rows.
2. Compare `_en.html` snapshot with previous version (e.g., `git diff` or visual diff tool).
3. Render PDF (already produced) and eyeball vs original CSR PDF.
4. Log warnings in CLI output – no unresolved warnings except "Docling export missing" (known) and "PDF fallback" (expected when WeasyPrint absent).

### Automated checks (Nov 2025)
- `uv run --python 3.11 pytest tests/integration/test_csr_table_regression.py -q`
  * Guarantees Docling extraction still yields the CSR summary table.
- `uv run --python 3.11 pytest tests/unit/test_pdf_browser_smoke.py -q`
  * Smoke-tests the Playwright fallback and ensures produced PDF is non-empty.

## 6. Next steps (tracked separately)
- Regression test for table presence.
- Smoke test for PDF fallback binary.
- Automated visual diff helper (planned).
