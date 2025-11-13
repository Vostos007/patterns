#!/usr/bin/env python3
"""Test with small fontsizes like our code uses."""
import fitz

doc = fitz.open()

# Test different small fontsizes
for fs in [4.0, 5.0, 6.0, 6.4, 7.0, 8.0]:
    page = doc.new_page(width=595, height=842)
    
    # Redaction
    page.add_redact_annot(page.rect)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
    
    # Insert font
    font = fitz.Font("notos")
    page.insert_font(fontname="MultiLang", fontbuffer=font.buffer)
    
    # Insert text with small fontsize
    leftover = page.insert_textbox(
        fitz.Rect(100, 100, 300, 120),  # 20pt tall rect
        "Тест",
        fontname="MultiLang",
        fontsize=fs,
        color=(0, 0, 0)
    )
    
    blocks = len([b for b in page.get_text('dict').get('blocks', []) if b.get('type') == 0])
    status = "✅" if (leftover >= 0 and blocks == 1) else "❌"
    
    print(f"{status} Fontsize {fs:.1f}pt: leftover={leftover:.2f}, blocks={blocks}")

doc.save("test_small_fontsize_output.pdf")
doc.close()
