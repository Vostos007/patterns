# HTML Output Format

The translation pipeline now produces an HTML rendition for every language alongside Markdown and PDF outputs. The HTML layout mirrors the source PDF page geometry and provides stable containers for downstream rendering or manual adjustments.

## File Location

HTML files are written to `tmp/<document>/output/<slug>/<lang>/<slug>_<lang>.html` (the same folder as the translated PDF/Markdown files).

## Page Structure

- Each PDF page becomes a `<section class="page">` with inline dimensions (CSS pixels converted from the PDF point units).
- Original block geometry is preserved via absolutely positioned `<div class="block">` containers. Each block exposes:
  - `data-role` – `header`, `body`, or `footer`.
  - `data-block-id` – original block identifier.
  - additional `data-*` attributes sourced from the extractor metadata.
- Inside each block every translated line is rendered as a `<div class="line">` with `white-space: pre-wrap` to keep newlines and schematic spacing.

## Styling

A minimal embedded stylesheet provides predictable typography and page shadows. Consumers can append their own stylesheet or inject the markup into external templates.

## Usage Notes

- Images and schematic overlays remain in the background PDF; the HTML focuses on text placement. When additional assets are needed, reference the block coordinates stored as inline styles.
- Since the HTML mirrors the underlying geometry, arbitrary length translations may need manual scaling for print-oriented PDFs. Future work will add responsive fallbacks.
