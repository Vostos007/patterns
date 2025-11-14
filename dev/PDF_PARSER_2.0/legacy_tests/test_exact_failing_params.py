#!/usr/bin/env python3
"""Test with EXACT parameters from failing block."""
import fitz

doc = fitz.open()
page = doc.new_page(width=595, height=842)

# Redaction
page.add_redact_annot(page.rect)
page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)

# Insert font
font = fitz.Font("notos")
page.insert_font(fontname="MultiLang", fontbuffer=font.buffer)

# EXACT parameters from failing Block 0
rect = fitz.Rect(40.0, 75.78441619873047, 554.9979858398438, 83.78441619873047)
text = "Идентификатор торгового счета: M66WS2ZDL8GHS  PayPal ID: info@hollywool.eu  01/01/2025 - 29/07/2025"
fontsize = 6.40

print(f"Rect: {rect.width:.1f} x {rect.height:.1f}")
print(f"Text: {text[:60]}...")
print(f"Fontsize: {fontsize}pt")
print(f"Text length: {len(text)} chars")

leftover = page.insert_textbox(
    rect,
    text,
    fontname="MultiLang",
    fontsize=fontsize,
    align=fitz.TEXT_ALIGN_LEFT,
    color=(0, 0, 0)
)

blocks = len([b for b in page.get_text('dict').get('blocks', []) if b.get('type') == 0])

print(f"\nResult:")
print(f"  insert_textbox returned: {leftover}")
print(f"  Blocks created: {blocks}")

if leftover < 0:
    print("  ❌ FAILED - same as production!")
elif blocks == 1:
    print("  ✅ SUCCESS - works in test!")
else:
    print(f"  ⚠️  Unexpected: {blocks} blocks")

doc.save("test_exact_params_output.pdf")
doc.close()
