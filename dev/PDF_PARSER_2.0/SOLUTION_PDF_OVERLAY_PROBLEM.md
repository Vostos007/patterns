# Solution: PDF Text Overlay Problem

## Problem Summary

The current `layout_preserver.py` implementation creates PDFs with **overlapping text layers**:

1. `insert_pdf(src_doc)` copies ALL content including text
2. `rebuild_page()` paints white rectangles over text and adds translated text
3. Result: Two text layers (original hidden, translated visible)
4. `get_text("dict")` sees BOTH layers causing issues

**Visual representation:**
```
Current PDF Structure:
┌─────────────────────────────┐
│ Layer 3: Translated text    │ ← Visible
├─────────────────────────────┤
│ Layer 2: White rectangles   │ ← Hides layer 1
├─────────────────────────────┤
│ Layer 1: Original text      │ ← Hidden but still in PDF
├─────────────────────────────┤
│ Layer 0: Images & graphics  │ ← Always visible
└─────────────────────────────┘

Problem: get_text() extracts from Layer 1 AND Layer 3!
```

## Solution: Selective Content Redaction

PyMuPDF provides **redaction annotations** that can selectively remove content types:
- Remove text ✅
- Preserve images ✅
- Preserve vector graphics (lines, shapes, logos) ✅

### Key PyMuPDF Methods

```python
import fitz

# Add redaction annotation for an area
page.add_redact_annot(rect)  # rect can be entire page or specific area

# Apply redaction with selective preservation
page.apply_redactions(
    images=fitz.PDF_REDACT_IMAGE_NONE,      # Keep images (value = 0)
    graphics=fitz.PDF_REDACT_GRAPHICS_NONE   # Keep vector graphics (value = 0)
)
# Default behavior removes text from redacted area
```

**Redaction flags:**
- `images=fitz.PDF_REDACT_IMAGE_NONE` (0) → Keep images
- `images=fitz.PDF_REDACT_IMAGE_REMOVE` (1) → Remove images
- Similar flags for `graphics` parameter (available in PyMuPDF 1.23.0+)

### Reference
- [GitHub Discussion #3425](https://github.com/pymupdf/PyMuPDF/discussions/3425)
- PyMuPDF docs: Redaction annotations

---

## Implementation Solution

### Option 1: Clean Page Creation (Recommended)

Create each destination page with only graphics/images, then add translated text:

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
    # Step 1: Create new page with same dimensions
    dest_page = dest_doc.new_page(
        width=src_page.rect.width,
        height=src_page.rect.height
    )

    # Step 2: Copy the entire page content
    dest_page.show_pdf_page(
        dest_page.rect,           # Fill entire page
        src_page.parent,          # Source document
        src_page.number           # Source page number
    )

    # Step 3: Remove ALL text while preserving images and graphics
    dest_page.add_redact_annot(dest_page.rect)
    dest_page.apply_redactions(
        images=fitz.PDF_REDACT_IMAGE_NONE,  # Keep images (=0)
        # For PyMuPDF 1.23.0+:
        # graphics=fitz.PDF_REDACT_GRAPHICS_NONE  # Keep vector graphics (=0)
    )

    return dest_page


def rebuild_page_text_only(
    src_page: fitz.Page,
    dest_page: fitz.Page,
    src_lang: str,
    tgt_lang: str
) -> None:
    """Add translated text to a clean (graphics-only) page.

    Since dest_page has NO text layers, we just insert translated text
    without needing to paint white rectangles.
    """
    page_dict = src_page.get_text("dict", sort=True)
    text_blocks = [block for block in page_dict.get("blocks", []) if block.get("type") == 0]

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

        # Simply insert text - no need to paint over anything!
        _insert_textbox_auto(
            dest_page,
            rect,
            translated,
            font_alias,
            average_font_size(block),
            color=(0, 0, 0),
        )


def process_pdf(
    input_path: Path,
    output_dir: Path,
    target_langs: list[str] | None = None,
) -> list[Path]:
    """Fixed version using redaction-based approach."""
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
            dest_doc = fitz.open()  # Empty document

            # Process each page
            for page_num in range(src_doc.page_count):
                src_page = src_doc[page_num]

                # KEY FIX: Create page with graphics only (no text)
                dest_page = create_graphics_only_page(src_page, dest_doc)

                # Add translated text (no overlap!)
                rebuild_page_text_only(src_page, dest_page, src_lang, tgt)

            out_path = output_dir / f"{input_path.stem}_{tgt}.pdf"
            dest_doc.save(out_path, deflate=True, garbage=3)
            dest_doc.close()
            produced.append(out_path)

        return produced
    finally:
        src_doc.close()
```

**New PDF structure:**
```
Fixed PDF Structure:
┌─────────────────────────────┐
│ Layer 1: Translated text    │ ← Visible, ONLY text layer
├─────────────────────────────┤
│ Layer 0: Images & graphics  │ ← Preserved from original
└─────────────────────────────┘

✅ get_text() only extracts from Layer 1!
```

---

### Option 2: In-Place Redaction (Alternative)

If you prefer to keep the `insert_pdf` approach, apply redaction after copying:

```python
def process_pdf_alternative(
    input_path: Path,
    output_dir: Path,
    target_langs: list[str] | None = None,
) -> list[Path]:
    """Alternative: Use insert_pdf then clean up with redaction."""
    output_dir.mkdir(parents=True, exist_ok=True)

    src_doc = fitz.open(input_path)
    try:
        # ... (same setup as before) ...

        for tgt in targets:
            ensure_argos_model(src_lang, tgt)
            dest_doc = fitz.open()
            dest_doc.insert_pdf(src_doc)  # Copy everything

            # Clean up: remove text from all pages
            for page_num in range(dest_doc.page_count):
                dest_page = dest_doc[page_num]

                # Remove ALL text while keeping images/graphics
                dest_page.add_redact_annot(dest_page.rect)
                dest_page.apply_redactions(
                    images=fitz.PDF_REDACT_IMAGE_NONE
                )

                # Now add translated text
                src_page = src_doc[page_num]
                rebuild_page_text_only(src_page, dest_page, src_lang, tgt)

            out_path = output_dir / f"{input_path.stem}_{tgt}.pdf"
            dest_doc.save(out_path, deflate=True, garbage=3)
            dest_doc.close()
            produced.append(out_path)

        return produced
    finally:
        src_doc.close()
```

---

## Advantages of This Solution

1. **Clean text layer**: Only translated text exists in output PDF
2. **Preserves graphics**: Images and vector graphics (logos, lines, shapes) remain intact
3. **Better text extraction**: Tools like `get_text()` only see translated text
4. **No white rectangles**: Don't need to paint over original text
5. **Canonical PyMuPDF approach**: Uses built-in redaction system designed for this

---

## Version Compatibility

**PyMuPDF versions:**
- **1.19.0+**: `apply_redactions(images=...)` available
- **1.23.0+**: `apply_redactions(graphics=...)` added for vector graphics control

**Check version:**
```python
import fitz
print(fitz.version)  # e.g., (1, 24, 2) or similar
```

**Fallback for older versions:**
If `graphics` parameter not available, it will still remove text and keep images:
```python
# Works in older versions
dest_page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
```

---

## Testing

Run the test script to verify:
```bash
cd /Users/vostos/Dev/Hollywool\ patterns/dev/PDF_PARSER_2.0
python3 test_redaction_solution.py
```

Or test on actual PDF:
```python
import fitz

doc = fitz.open("input.pdf")
page = doc[0]

# Before
print(f"Before: {len(page.get_text('dict')['blocks'])} blocks")

# Apply redaction
page.add_redact_annot(page.rect)
page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

# After
print(f"After: {len(page.get_text('dict')['blocks'])} blocks")
print(f"Images: {len(page.get_images())} (should be preserved)")
print(f"Drawings: {len(page.get_drawings())} (should be preserved)")

doc.save("output_no_text.pdf")
doc.close()
```

---

## Migration Steps

1. **Backup current implementation** (it works, just has the overlay issue)
2. **Add `create_graphics_only_page()` function** to `layout_preserver.py`
3. **Rename current `rebuild_page()`** to `rebuild_page_text_only()` and remove white rectangle painting
4. **Update `process_pdf()`** to use new approach:
   - Replace `dest_doc.insert_pdf(src_doc)` with per-page creation
   - Call `create_graphics_only_page()` for each page
   - Call `rebuild_page_text_only()` to add translated text
5. **Test with sample PDFs** that have images/graphics
6. **Verify with diagnostics**: Run `get_text("dict")` to confirm only one text layer

---

## References

- **PyMuPDF Redaction Docs**: https://pymupdf.readthedocs.io/en/latest/recipes-annotations.html#redactions
- **GitHub Discussion**: https://github.com/pymupdf/PyMuPDF/discussions/3425
- **show_pdf_page() method**: https://pymupdf.readthedocs.io/en/latest/page.html#Page.show_pdf_page
- **apply_redactions() API**: https://pymupdf.readthedocs.io/en/latest/page.html#Page.apply_redactions
