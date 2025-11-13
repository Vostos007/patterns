#!/usr/bin/env python3
"""Test PyMuPDF's actual line height."""
import fitz

doc = fitz.open()
page = doc.new_page(width=595, height=842)

# Insert font
font = fitz.Font("notos")
page.insert_font(fontname="Test", fontbuffer=font.buffer)

# Test different rect heights for 1 line at different fontsizes
for fontsize in [6.0, 7.0, 8.0, 10.0, 12.0]:
    text = "Test line"
    
    # Try increasingly larger heights until text fits
    for height_multiplier in [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]:
        rect_height = fontsize * height_multiplier
        rect = fitz.Rect(100, 100, 300, 100 + rect_height)
        
        # Create new page for each test
        test_page = doc.new_page(width=595, height=842)
        test_page.insert_font(fontname="Test", fontbuffer=font.buffer)
        
        leftover = test_page.insert_textbox(
            rect, text, fontname="Test", fontsize=fontsize, color=(0, 0, 0)
        )
        
        doc.delete_page(doc.page_count - 1)  # Remove test page
        
        if leftover >= 0:  # Success (positive or zero)
            print(f"Fontsize {fontsize}pt: needs {height_multiplier:.2f}x height (min: {rect_height:.1f}pt)")
            break
    else:
        print(f"Fontsize {fontsize}pt: FAILED even at 1.5x")

doc.close()
