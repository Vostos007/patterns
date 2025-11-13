# Quick Fix Guide: PDF Overlay Problem

## Problem
`get_text("dict")` extracts both original AND translated text because original text is still in PDF (just hidden under white rectangles).

## Solution
Use PyMuPDF redaction annotations to **remove original text** while keeping images/graphics, then add translated text.

---

## Code Changes for `/Users/vostos/Dev/Hollywool patterns/dev/PDF_PARSER_2.0/kps/layout_preserver.py`

### 1. Add new function (after line 272)

```python
def create_graphics_only_page(src_page: fitz.Page, dest_doc: fitz.Document) -> fitz.Page:
    """Create a new page with only images and graphics (no text) from source.

    This solves the overlay problem by removing ALL text layers before
    adding translated text, ensuring no duplicate/overlapping text.

    Args:
        src_page: Source page to copy from
        dest_doc: Destination document to add page to

    Returns:
        New page with images/graphics but no text
    """
    # Create new page with same dimensions as source
    dest_page = dest_doc.new_page(
        width=src_page.rect.width,
        height=src_page.rect.height
    )

    # Copy entire page content (images, graphics, and text)
    dest_page.show_pdf_page(
        dest_page.rect,      # Fill entire page
        src_page.parent,     # Source document
        src_page.number      # Source page number
    )

    # Remove ALL text while preserving images and graphics
    dest_page.add_redact_annot(dest_page.rect)
    dest_page.apply_redactions(
        images=fitz.PDF_REDACT_IMAGE_NONE,  # Keep images (constant = 0)
        # For PyMuPDF 1.23.0+ also add:
        # graphics=fitz.PDF_REDACT_GRAPHICS_NONE  # Keep vector graphics
    )

    return dest_page
```

### 2. Simplify `rebuild_page` function (replace lines 273-314)

```python
def rebuild_page(orig_page: fitz.Page, dest_page: fitz.Page, src_lang: str, tgt_lang: str) -> None:
    """Add translated text to a clean (graphics-only) page.

    Since dest_page has NO text layers (created by create_graphics_only_page),
    we just insert translated text without needing to paint white rectangles.
    """
    page_dict = orig_page.get_text("dict", sort=True)
    text_blocks = [block for block in page_dict.get("blocks", []) if block.get("type") == 0]

    # Pick font once for the entire page (with Cyrillic support if needed)
    font_alias = pick_font(dest_page, target_lang=tgt_lang)

    for block in text_blocks:
        original_text = block_text(block)
        if not original_text.strip():
            continue

        try:
            translated = translate_text(original_text, src_lang, tgt_lang)
        except Exception:
            translated = original_text
        translated = clean_text(translated)

        rect = fitz.Rect(block["bbox"]) & dest_page.rect
        if rect.is_empty:
            continue

        # Simply insert translated text - no need to paint over anything!
        _insert_textbox_auto(
            dest_page,
            rect,
            translated,
            font_alias,
            average_font_size(block),
            color=(0, 0, 0),
        )
```

### 3. Update `process_pdf` function (replace lines 316-352)

```python
def process_pdf(
    input_path: Path,
    output_dir: Path,
    target_langs: list[str] | None = None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    src_doc = fitz.open(input_path)
    try:
        sample_text = read_text_sample(src_doc)
        src_lang = detect_language(sample_text)
        targets = (
            [lang for lang in target_langs if lang != src_lang]
            if target_langs
            else [lang for lang in LANGS if lang != src_lang]
        )
        if not targets:
            raise ValueError("No target languages specified for layout preserver")

        produced: list[Path] = []

        for tgt in targets:
            ensure_argos_model(src_lang, tgt)
            dest_doc = fitz.open()  # Create empty document

            # Process each page with clean approach
            for page_index in range(src_doc.page_count):
                orig_page = src_doc.load_page(page_index)

                # KEY FIX: Create page with only graphics/images (no text)
                dest_page = create_graphics_only_page(orig_page, dest_doc)

                # Add translated text to clean page (no overlap!)
                rebuild_page(orig_page, dest_page, src_lang, tgt)

            out_path = output_dir / f"{input_path.stem}_{tgt}.pdf"
            dest_doc.save(out_path, deflate=True, garbage=3)
            dest_doc.close()
            produced.append(out_path)

        return produced
    finally:
        src_doc.close()
```

### 4. Remove `_paint_over_block` function (lines 248-271)

This function is no longer needed since we're not painting white rectangles.

---

## Summary of Changes

| Change | Lines | Action |
|--------|-------|--------|
| Remove `_paint_over_block()` | 248-271 | Delete function |
| Add `create_graphics_only_page()` | After 272 | Add new function |
| Simplify `rebuild_page()` | 273-314 | Replace with simpler version |
| Update `process_pdf()` | 316-352 | Replace with new logic |

**Key differences:**
- ❌ OLD: `dest_doc.insert_pdf(src_doc)` → copies all pages at once
- ✅ NEW: Per-page creation with `create_graphics_only_page()`
- ❌ OLD: Paint white rectangles over text
- ✅ NEW: Text already removed by redaction
- ✅ RESULT: Only ONE text layer in output PDF

---

## Testing

### Quick test
```bash
cd /Users/vostos/Dev/Hollywool\ patterns/dev/PDF_PARSER_2.0

# Test the solution
python3 test_redaction_solution.py

# Test on real PDF
python3 scripts/pdf_translate_preserve_layout.py \
    --in tests/fixtures/layout_preserve_sample.pdf \
    --out tmp/test_output \
    --langs en
```

### Verify fix
```python
import fitz

# Check output PDF
doc = fitz.open("tmp/test_output/layout_preserve_sample_en.pdf")
page = doc[0]

# Should only have translated text (not original + translated)
text_dict = page.get_text("dict")
text_blocks = [b for b in text_dict["blocks"] if b.get("type") == 0]

print(f"Text blocks: {len(text_blocks)}")
print(f"Images: {len(page.get_images())}")  # Should be preserved
print(f"Drawings: {len(page.get_drawings())}")  # Should be preserved
```

---

## PyMuPDF Version Check

```python
import fitz
print(f"PyMuPDF version: {fitz.version}")

# Check if graphics parameter available (1.23.0+)
import inspect
sig = inspect.signature(fitz.Page.apply_redactions)
has_graphics = 'graphics' in sig.parameters
print(f"Graphics parameter available: {has_graphics}")
```

If `graphics` parameter not available, the code still works (removes text, keeps images).

---

## References

- **Main solution doc**: `SOLUTION_PDF_OVERLAY_PROBLEM.md`
- **Test script**: `test_redaction_solution.py`
- **PyMuPDF docs**: https://pymupdf.readthedocs.io/en/latest/page.html#Page.apply_redactions
- **GitHub discussion**: https://github.com/pymupdf/PyMuPDF/discussions/3425
