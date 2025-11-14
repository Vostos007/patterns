#!/usr/bin/env python3
"""Simple test: redaction then font insertion."""
import fitz

doc = fitz.open()
page = doc.new_page(width=595, height=842)

# Add text to be redacted
page.insert_text((100, 100), "Original", fontsize=12)

# Apply redaction
page.add_redact_annot(page.rect)
page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)

print("After redaction - blocks:", len([b for b in page.get_text('dict').get('blocks', []) if b.get('type') == 0]))

# Insert font AFTER redaction (like our code does)
font = fitz.Font("notos")
ref = page.insert_font(fontname="MultiLang", fontbuffer=font.buffer)
print(f"Font inserted after redaction, ref: {ref}")

# Insert text
leftover = page.insert_textbox(
    fitz.Rect(100, 100, 300, 150),
    "Тест после редакции",
    fontname="MultiLang",
    fontsize=12,
    color=(0, 0, 0)
)

print(f"insert_textbox returned: {leftover}")
print(f"Blocks: {len([b for b in page.get_text('dict').get('blocks', []) if b.get('type') == 0])}")

if leftover and leftover < 0:
    print("❌ FAILED")
else:
    print("✅ SUCCESS")

doc.save("test_simple_output.pdf")
doc.close()
