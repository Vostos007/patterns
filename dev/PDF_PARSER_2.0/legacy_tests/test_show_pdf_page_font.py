#!/usr/bin/env python3
"""Test font insertion on pages created via show_pdf_page."""
import fitz
from pathlib import Path

input_pdf = Path("runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf")

if not input_pdf.exists():
    print(f"❌ File not found: {input_pdf}")
    exit(1)

src_doc = fitz.open(input_pdf)
src_page = src_doc[0]

# Create destination using show_pdf_page (like our code does)
dest_doc = fitz.open()
dest_page = dest_doc.new_page(width=src_page.rect.width, height=src_page.rect.height)

print("Created blank page via new_page()")
print(f"  Page rect: {dest_page.rect}")

# Import content via show_pdf_page
dest_page.show_pdf_page(dest_page.rect, src_doc, 0)
print("\nImported content via show_pdf_page()")

# Apply redaction
dest_page.add_redact_annot(dest_page.rect)
dest_page.apply_redactions(
    images=fitz.PDF_REDACT_IMAGE_NONE,
    graphics=fitz.PDF_REDACT_LINE_ART_NONE
)
print("Applied page-level redaction")

blocks_after_redaction = [b for b in dest_page.get_text("dict").get("blocks", []) if b.get("type") == 0]
print(f"  Blocks after redaction: {len(blocks_after_redaction)}")

# Now try to insert font
print("\nInserting NotoSans font...")
try:
    font = fitz.Font("notos")
    ref = dest_page.insert_font(fontname="MultiLang", fontbuffer=font.buffer)
    print(f"  ✅ Font inserted successfully, ref: {ref}")
except Exception as e:
    print(f"  ❌ Font insertion failed: {e}")
    exit(1)

# Try to insert text
print("\nInserting Russian text...")
text = "Тестовый текст на русском языке"
rect = fitz.Rect(100, 100, 400, 200)

leftover = dest_page.insert_textbox(
    rect,
    text,
    fontname="MultiLang",
    fontsize=12,
    color=(0, 0, 0)
)

print(f"  insert_textbox returned: {leftover}")

if leftover and leftover < 0:
    print(f"  ❌ NEGATIVE RETURN VALUE = ERROR CODE!")
else:
    print(f"  ✅ Positive/zero return value (normal)")

blocks_final = [b for b in dest_page.get_text("dict").get("blocks", []) if b.get("type") == 0]
print(f"  Final blocks: {len(blocks_final)}")

# Save for inspection
out_path = Path("test_output_show_pdf_page.pdf")
dest_doc.save(out_path)
print(f"\n📄 Saved to: {out_path}")

dest_doc.close()
src_doc.close()

if leftover and leftover < 0:
    print("\n❌ Font insertion issue detected!")
elif blocks_final >= 1:
    print("\n✅ Text inserted successfully!")
else:
    print(f"\n❌ No blocks created!")
