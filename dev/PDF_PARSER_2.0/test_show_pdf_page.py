#!/usr/bin/env python3
"""Test to verify show_pdf_page behavior with text blocks."""
import fitz
from pathlib import Path

input_pdf = Path("runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf")

if not input_pdf.exists():
    print(f"❌ File not found: {input_pdf}")
    exit(1)

# Open source PDF
src_doc = fitz.open(input_pdf)
src_page = src_doc[0]

print("=" * 70)
print("ORIGINAL PDF")
print("=" * 70)
orig_blocks = [b for b in src_page.get_text("dict", sort=True).get("blocks", []) if b.get("type") == 0]
print(f"Text blocks: {len(orig_blocks)}")

# Method 1: insert_pdf (old approach)
print("\n" + "=" * 70)
print("METHOD 1: insert_pdf()")
print("=" * 70)

dest1 = fitz.open()
dest1.insert_pdf(src_doc)
page1 = dest1[0]

blocks1 = [b for b in page1.get_text("dict", sort=True).get("blocks", []) if b.get("type") == 0]
print(f"After insert_pdf: {len(blocks1)} text blocks")

dest1.close()

# Method 2: show_pdf_page (new approach)
print("\n" + "=" * 70)
print("METHOD 2: show_pdf_page()")
print("=" * 70)

dest2 = fitz.open()
page2 = dest2.new_page(width=src_page.rect.width, height=src_page.rect.height)
page2.show_pdf_page(page2.rect, src_doc, 0)

blocks2 = [b for b in page2.get_text("dict", sort=True).get("blocks", []) if b.get("type") == 0]
print(f"After show_pdf_page: {len(blocks2)} text blocks")

# Now apply redaction
print("\nApplying page-level redaction...")
page2.add_redact_annot(page2.rect)
page2.apply_redactions(
    images=fitz.PDF_REDACT_IMAGE_NONE,
    graphics=fitz.PDF_REDACT_LINE_ART_NONE
)

blocks2_after = [b for b in page2.get_text("dict", sort=True).get("blocks", []) if b.get("type") == 0]
print(f"After redaction: {len(blocks2_after)} text blocks")

if blocks2_after == 0:
    print("✅ SUCCESS: Page is clean!")
else:
    print(f"❌ PROBLEM: {len(blocks2_after)} residual blocks remain")

dest2.close()
src_doc.close()

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
print(f"Original: {len(orig_blocks)} blocks")
print(f"Method 1 (insert_pdf): {len(blocks1)} blocks")
print(f"Method 2 (show_pdf_page): {len(blocks2)} blocks → {len(blocks2_after)} blocks after redaction")
