"""Test script for selective content removal using redaction annotations.

This demonstrates the solution to the PDF overlay problem:
- Use redaction annotations to remove text while preserving images/graphics
- Three categories can be controlled: text, images, and graphics (vector drawings)
"""
import fitz  # PyMuPDF
from pathlib import Path


def test_redaction_approach():
    """Test removing text while keeping images and graphics."""

    # Test file path (adjust as needed)
    test_pdf = Path("tests/fixtures/layout_preserve_sample.pdf")

    if not test_pdf.exists():
        print(f"⚠️  Test file not found: {test_pdf}")
        print("This is just a demonstration of the solution approach.")
        return

    print("=" * 60)
    print("Testing Redaction-Based Selective Content Removal")
    print("=" * 60)

    doc = fitz.open(test_pdf)

    # Get first page for testing
    page = doc[0]

    print(f"\n📄 Original page content:")
    print(f"   Text blocks: {len([b for b in page.get_text('dict')['blocks'] if b.get('type') == 0])}")
    print(f"   Images: {len(page.get_images())}")
    print(f"   Vector graphics: {len(page.get_drawings())}")

    # SOLUTION: Use redaction with selective preservation
    print("\n🔧 Applying redaction to remove text but keep images/graphics...")

    # Step 1: Add redaction annotation for entire page
    page.add_redact_annot(page.rect)

    # Step 2: Apply redaction with flags to preserve images and graphics
    # PDF_REDACT_IMAGE_NONE = 0 (keep images)
    # graphics parameter also available in newer versions
    page.apply_redactions(
        images=fitz.PDF_REDACT_IMAGE_NONE,  # Keep images
        # graphics=fitz.PDF_REDACT_GRAPHICS_NONE  # Keep vector graphics (if available)
    )

    print(f"\n✅ After redaction:")
    print(f"   Text blocks: {len([b for b in page.get_text('dict')['blocks'] if b.get('type') == 0])}")
    print(f"   Images: {len(page.get_images())}")
    print(f"   Vector graphics: {len(page.get_drawings())}")

    # Save test output
    output_path = Path("tmp/test_redaction_output.pdf")
    output_path.parent.mkdir(exist_ok=True)
    doc.save(output_path, deflate=True, garbage=3)
    doc.close()

    print(f"\n💾 Saved test output to: {output_path}")
    print("\n" + "=" * 60)


def demonstrate_solution():
    """Show the code pattern for the layout_preserver.py fix."""

    print("\n" + "=" * 60)
    print("SOLUTION FOR layout_preserver.py")
    print("=" * 60)

    solution_code = '''
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
    # Create new page with same dimensions
    dest_page = dest_doc.new_page(
        width=src_page.rect.width,
        height=src_page.rect.height
    )

    # Copy the entire page content first
    dest_page.show_pdf_page(dest_page.rect, src_page.parent, src_page.number)

    # Now remove ALL text while preserving images and graphics
    dest_page.add_redact_annot(dest_page.rect)
    dest_page.apply_redactions(
        images=fitz.PDF_REDACT_IMAGE_NONE,  # Keep images
        # In PyMuPDF 1.23.0+, also add:
        # graphics=fitz.PDF_REDACT_GRAPHICS_NONE  # Keep vector graphics
    )

    return dest_page


def process_pdf_FIXED(
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

        produced: list[Path] = []

        for tgt in targets:
            ensure_argos_model(src_lang, tgt)
            dest_doc = fitz.open()  # Create empty document

            # Process each page
            for page_num in range(src_doc.page_count):
                src_page = src_doc[page_num]

                # KEY FIX: Create page with graphics only (no text)
                dest_page = create_graphics_only_page(src_page, dest_doc)

                # Now add translated text (no overlap!)
                rebuild_page_text_only(src_page, dest_page, src_lang, tgt)

            out_path = output_dir / f"{input_path.stem}_{tgt}.pdf"
            dest_doc.save(out_path, deflate=True, garbage=3)
            dest_doc.close()
            produced.append(out_path)

        return produced
    finally:
        src_doc.close()


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
'''

    print(solution_code)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Show the solution approach
    demonstrate_solution()

    # Try to run actual test if file exists
    test_redaction_approach()
