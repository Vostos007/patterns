#!/usr/bin/env python3
"""Find minimum height ratio for PyMuPDF insert_textbox."""
import fitz

text = "Test"

for fontsize in [5.0, 6.0, 7.0, 8.0, 10.0]:
    print(f"\nFontsize {fontsize}pt:")
    
    for height_mult in [1.0, 1.5, 2.0, 2.5, 3.0]:
        rect_height = fontsize * height_mult
        
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.add_redact_annot(page.rect)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
        font = fitz.Font("notos")
        page.insert_font(fontname="MultiLang", fontbuffer=font.buffer)
        
        leftover = page.insert_textbox(
            fitz.Rect(100, 100, 300, 100 + rect_height),
            text,
            fontname="MultiLang",
            fontsize=fontsize,
            color=(0, 0, 0)
        )
        
        doc.close()
        
        if leftover >= 0:
            print(f"  ✅ {height_mult}x = {rect_height:.1f}pt height works (leftover={leftover:.2f})")
            break
    else:
        print(f"  ❌ Even 3x height doesn't work!")
