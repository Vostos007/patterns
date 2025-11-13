#!/usr/bin/env python3
"""Test exact flow from our code."""
import fitz
from pathlib import Path
import sys

# Add kps to path
sys.path.insert(0, str(Path(__file__).parent))

from kps.layout_preserver import choose_font_for_page, insert_textbox_smart, clean_text

input_pdf = Path("runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf")

if not input_pdf.exists():
    print(f"❌ File not found: {input_pdf}")
    exit(1)

src_doc = fitz.open(input_pdf)
src_page = src_doc[0]

# Extract one text block to test with
page_dict = src_page.get_text("dict", sort=True)
text_blocks = [b for b in page_dict.get("blocks", []) if b.get("type") == 0]
test_block = text_blocks[0]  # Use first block

print("Original block:")
print(f"  BBox: {test_block['bbox']}")
lines = []
for line in test_block.get("lines", []):
    fragments = [span.get("text", "") for span in line.get("spans", [])]
    lines.append("".join(fragments))
original_text = "\n".join(lines)
print(f"  Text: {original_text[:60]}...")

# Create dest page exactly like our code
dest_doc = fitz.open()
dest_page = dest_doc.new_page(width=src_page.rect.width, height=src_page.rect.height)
dest_page.show_pdf_page(dest_page.rect, src_doc, 0)

# Apply redaction exactly like our code
dest_page.add_redact_annot(dest_page.rect)
dest_page.apply_redactions(
    images=fitz.PDF_REDACT_IMAGE_NONE,
    graphics=fitz.PDF_REDACT_LINE_ART_NONE
)

# Get font exactly like our code
font_alias, font = choose_font_for_page(dest_page, target_lang="ru")
print(f"\nFont: alias={font_alias}, font={font}")

# Prepare text (simulate translation - just use original for now)
translated = clean_text(original_text)
print(f"\nTranslated text: {translated[:60]}...")

# Get rect
rect = fitz.Rect(test_block["bbox"]) & dest_page.rect
print(f"Rect: {rect}")

# Calculate base fontsize
sizes = []
for line in test_block.get("lines", []):
    for span in line.get("spans", []):
        try:
            sizes.append(float(span.get("size", 0)))
        except (TypeError, ValueError):
            continue
base_fontsize = sum(sizes) / len(sizes) if sizes else 11.0
print(f"Base fontsize: {base_fontsize:.1f}")

# Call insert_textbox_smart exactly like our code
print("\nCalling insert_textbox_smart...")
fs_used = insert_textbox_smart(
    dest_page,
    rect,
    translated,
    font_alias,
    font,
    base_fontsize,
)

print(f"Fontsize used: {fs_used:.1f}")

# Check blocks
blocks_final = [b for b in dest_page.get_text("dict").get("blocks", []) if b.get("type") == 0]
print(f"Final blocks: {len(blocks_final)}")

# Save
out_path = Path("test_exact_flow_output.pdf")
dest_doc.save(out_path)
print(f"\n📄 Saved to: {out_path}")

dest_doc.close()
src_doc.close()

if len(blocks_final) == 1:
    print("\n✅ SUCCESS: 1 block created!")
else:
    print(f"\n❌ PROBLEM: {len(blocks_final)} blocks instead of 1")
