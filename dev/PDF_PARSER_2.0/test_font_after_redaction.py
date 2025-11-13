#!/usr/bin/env python3
"""Test if font persists after redaction."""
import fitz

doc = fitz.open()
page = doc.new_page(width=595, height=842)

# Insert some text that will be redacted
page.insert_text((100, 100), "Original text to be redacted", fontsize=12)

print("Before redaction:")
print(f"  Blocks: {len([b for b in page.get_text('dict').get('blocks', []) if b.get('type') == 0])}")

# Insert custom font BEFORE redaction
print("\nInserting font BEFORE redaction...")
font = fitz.Font("notos")
ref1 = page.insert_font(fontname="TestFont", fontbuffer=font.buffer)
print(f"  Font inserted, ref: {ref1}")

# Apply page-level redaction
print("\nApplying redaction...")
page.add_redact_annot(page.rect)
page.apply_redactions(
    images=fitz.PDF_REDACT_IMAGE_NONE,
    graphics=fitz.PDF_REDACT_LINE_ART_NONE
)

print("After redaction:")
print(f"  Blocks: {len([b for b in page.get_text('dict').get('blocks', []) if b.get('type') == 0])}")

# Try to use the font that was inserted BEFORE redaction
print("\nTrying to use font inserted BEFORE redaction...")
leftover1 = page.insert_textbox(
    fitz.Rect(100, 100, 300, 150),
    "Test with old font ref Тест",
    fontname="TestFont",
    fontsize=12,
    color=(0, 0, 0)
)
print(f"  insert_textbox returned: {leftover1}")
if leftover1 < 0:
    print("  ❌ FAILED - font not available!")
else:
    print("  ✅ SUCCESS")

blocks1 = len([b for b in page.get_text('dict').get('blocks', []) if b.get('type') == 0])
print(f"  Blocks: {blocks1}")

# Now insert font AFTER redaction
print("\nInserting font AFTER redaction...")
font2 = fitz.Font("notos")
ref2 = page.insert_font(fontname="TestFont2", fontbuffer=font2.buffer)
print(f"  Font inserted, ref: {ref2}")

leftover2 = page.insert_textbox(
    fitz.Rect(100, 200, 300, 250),
    "Test with new font ref Тест",
    fontname="TestFont2",
    fontsize=12,
    color=(0, 0, 0)
)
print(f"  insert_textbox returned: {leftover2}")
if leftover2 < 0:
    print("  ❌ FAILED!")
else:
    print("  ✅ SUCCESS")

blocks2 = len([b for b in page.get_text('dict').get('blocks', []) if b.get('type') == 0])
print(f"  Blocks: {blocks2}")

doc.save("test_font_redaction_output.pdf")
doc.close()

print("\n📄 Saved to: test_font_redaction_output.pdf")
