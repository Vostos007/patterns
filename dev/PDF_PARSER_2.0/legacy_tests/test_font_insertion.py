#!/usr/bin/env python3
"""Test font insertion after redaction."""
import fitz

# Create test doc
doc = fitz.open()
page = doc.new_page(width=595, height=842)

# Insert some initial text (will be redacted)
page.insert_text((100, 100), "Original text", fontsize=12)

print("Before redaction:")
blocks_before = [b for b in page.get_text("dict").get("blocks", []) if b.get("type") == 0]
print(f"  Blocks: {len(blocks_before)}")

# Apply page-level redaction
page.add_redact_annot(page.rect)
page.apply_redactions(
    images=fitz.PDF_REDACT_IMAGE_NONE,
    graphics=fitz.PDF_REDACT_LINE_ART_NONE
)

print("\nAfter redaction:")
blocks_after = [b for b in page.get_text("dict").get("blocks", []) if b.get("type") == 0]
print(f"  Blocks: {len(blocks_after)}")

# Now try to insert font and text
print("\nInserting font...")
try:
    font = fitz.Font("notos")
    # Get the actual fontname reference that PyMuPDF assigns
    fontname_ref = page.insert_font(fontname="TestFont", fontbuffer=font.buffer)
    print(f"  Font inserted, reference: {fontname_ref}")
except Exception as e:
    print(f"  Font insertion failed: {e}")
    fontname_ref = "TestFont"

# Try to insert text
print("\nInserting text...")
rect = fitz.Rect(100, 100, 400, 200)
leftover = page.insert_textbox(
    rect,
    "Test text after redaction",
    fontname="TestFont",  # Use the alias we provided
    fontsize=12,
    color=(0, 0, 0)
)

print(f"  insert_textbox returned: {leftover}")

blocks_final = [b for b in page.get_text("dict").get("blocks", []) if b.get("type") == 0]
print(f"  Final blocks: {len(blocks_final)}")

doc.close()

if leftover and leftover < 0:
    print("\n❌ NEGATIVE RETURN VALUE = ERROR!")
    print("Font is not available on the page!")
elif blocks_final == 1:
    print("\n✅ SUCCESS: Text inserted correctly!")
else:
    print(f"\n❌ PROBLEM: Expected 1 block, got {len(blocks_final)}")
