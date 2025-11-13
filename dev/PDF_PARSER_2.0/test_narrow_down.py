#!/usr/bin/env python3
"""Narrow down the cause."""
import fitz

text = "Идентификатор торгового счета: M66WS2ZDL8GHS  PayPal ID: info@hollywool.eu  01/01/2025 - 29/07/2025"

def test_params(rect, fontsize, desc):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.add_redact_annot(page.rect)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
    font = fitz.Font("notos")
    page.insert_font(fontname="MultiLang", fontbuffer=font.buffer)
    
    leftover = page.insert_textbox(rect, text, fontname="MultiLang", fontsize=fontsize, align=fitz.TEXT_ALIGN_LEFT, color=(0, 0, 0))
    blocks = len([b for b in page.get_text('dict').get('blocks', []) if b.get('type') == 0])
    
    status = "✅" if (leftover >= 0 and blocks == 1) else "❌"
    print(f"{status} {desc}")
    print(f"   Rect: {rect.width:.0f} x {rect.height:.0f}, fs={fontsize:.1f}, leftover={leftover:.2f}, blocks={blocks}")
    doc.close()

# Original failing params
test_params(fitz.Rect(40, 75, 555, 83), 6.4, "Original (FAILING)")

# Same rect, larger fontsize
test_params(fitz.Rect(40, 75, 555, 83), 8.0, "Same rect, fs=8.0")

# Same rect, smaller fontsize  
test_params(fitz.Rect(40, 75, 555, 83), 5.0, "Same rect, fs=5.0")

# Taller rect, same fontsize
test_params(fitz.Rect(40, 75, 555, 95), 6.4, "Taller rect (20pt), fs=6.4")

# Much taller rect
test_params(fitz.Rect(40, 75, 555, 105), 6.4, "Much taller rect (30pt), fs=6.4")

# Shorter text, same rect
short_text = "Test"
doc = fitz.open()
page = doc.new_page(width=595, height=842)
page.add_redact_annot(page.rect)
page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
font = fitz.Font("notos")
page.insert_font(fontname="MultiLang", fontbuffer=font.buffer)
leftover = page.insert_textbox(fitz.Rect(40, 75, 555, 83), short_text, fontname="MultiLang", fontsize=6.4, align=fitz.TEXT_ALIGN_LEFT, color=(0, 0, 0))
blocks = len([b for b in page.get_text('dict').get('blocks', []) if b.get('type') == 0])
status = "✅" if (leftover >= 0 and blocks == 1) else "❌"
print(f"{status} Short text, same rect")
print(f"   Rect: 515 x 8, fs=6.4, leftover={leftover:.2f}, blocks={blocks}")
doc.close()
