# PDF Layout Overhaul Plan (2025-11-06)

## Goal

Deliver deterministic translation outputs with a rigid HTML layout that mirrors the source PDF, so translated text, images, and schematics of any size slot into predictable containers. The PDF renderer must consume the same normalized structure without artifacts (no stray Cyrillic, broken fonts, or truncated lines).

## Current Issues

- TextWriter output retains untranslated header/footer fragments (e.g., `варов для вязания`) because those blocks are either skipped or redaction misses vector glyphs.
- Fallback fonts produce garbled glyphs (`f / k i i / O`) for decorative text due to missing explicit font selection.
- `_merge_segments_per_block` collapses line breaks (`" ".join`), causing hard line wraps (`Any distri`).
- Pipeline only emits Markdown/PDF; there is no canonical HTML structure to reuse across translations.

## Guiding Principles

1. **Single source of truth:** Build an intermediate HTML representation (strict CSS grid/flex layout per page) and use it for both downstream PDF rendering and web previews.
2. **Layered cleanup:** Strip/translate header/footer blocks before rendering; ensure redaction removes all original glyphs.
3. **Font determinism:** Provide explicit font mapping per language and fallbacks for symbols.
4. **Testable pipeline:** Add regression tests for layout preservation, header/footer replacement, and HTML generation.

## Work Breakdown

### 1. Extraction & Segmentation Audit
- Preserve per-line text verbatim when merging segments (no space-joining newlines).
- Ensure header/footer blocks are represented as segments so they reach the translator.
- Add metadata flags for block roles (header, body, footer) to support HTML templates.

### 2. HTML Renderer
- Introduce `src/pdf_pipeline/html_renderer.py` that consumes `PDFBlock` data + translated text and emits page-by-page `<div class="page">` structures with positioned containers.
- Generate `<div class="block">` wrappers preserving bounding boxes as CSS variables for easy styling.
- Provide CLI hook to emit HTML alongside Markdown/PDF.

### 3. PDF TextWriter Enhancements
- Feed translated header/footer into TextWriter; if block is marked decorative, translate but allow font override.
- Configure explicit font map (e.g., `helv` → `NotoSans-Regular`, `decorative` → `NotoSansDisplay`) per language.
- Replace newline-flattening joins with newline-preserving rendering and ensure redaction covers vector glyphs.

### 4. Pipeline Integration
- Update `DocumentTranslationPipeline` to:
  - Use enhanced merge preserving newlines.
  - Produce HTML output directory mirroring language slug.
  - Pass block metadata into renderers.

### 5. Testing & QA
- Add unit tests for `_merge_segments_per_block` to verify newline parity.
- Add HTML snapshot test using fixture PDF to check structural output.
- Integration test to assert header/footer text is translated and no Cyrillic remains in English PDF (via PyMuPDF text extraction).

## Deliverables

- Updated pipeline modules (`extractor`, `pipeline`, `pdf_textwriter_renderer`, new `html_renderer`).
- HTML output for each translation (`output/<doc>/<lang>/<doc>_<lang>.html`).
- Regression tests under `tests/` covering merge, rendering, and HTML generation.
- Documentation note in `docs/` describing the new HTML layout contract.

