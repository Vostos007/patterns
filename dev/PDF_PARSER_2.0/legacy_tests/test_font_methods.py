#!/usr/bin/env python3
"""Test different font insertion methods."""
import fitz

doc = fitz.open()

print("=" * 70)
print("TEST 1: Font buffer with custom alias")
print("=" * 70)
page1 = doc.new_page(width=595, height=842)
font = fitz.Font("notos")
ref1 = page1.insert_font(fontname="CustomAlias", fontbuffer=font.buffer)
print(f"insert_font returned: {ref1}")

leftover1 = page1.insert_textbox(
    fitz.Rect(100, 100, 300, 150),
    "Test text Тест",
    fontname="CustomAlias",
    fontsize=12,
    color=(0, 0, 0)
)
print(f"insert_textbox returned: {leftover1}")
print(f"Blocks created: {len([b for b in page1.get_text('dict').get('blocks', []) if b.get('type') == 0])}")

print("\n" + "=" * 70)
print("TEST 2: Using the reference returned by insert_font")
print("=" * 70)
page2 = doc.new_page(width=595, height=842)
font2 = fitz.Font("notos")
ref2 = page2.insert_font(fontbuffer=font2.buffer)  # No fontname parameter
print(f"insert_font returned: {ref2}")

leftover2 = page2.insert_textbox(
    fitz.Rect(100, 100, 300, 150),
    "Test text Тест",
    fontname=ref2,  # Use the returned reference
    fontsize=12,
    color=(0, 0, 0)
)
print(f"insert_textbox returned: {leftover2}")
print(f"Blocks created: {len([b for b in page2.get_text('dict').get('blocks', []) if b.get('type') == 0])}")

print("\n" + "=" * 70)
print("TEST 3: Built-in helv font")
print("=" * 70)
page3 = doc.new_page(width=595, height=842)
leftover3 = page3.insert_textbox(
    fitz.Rect(100, 100, 300, 150),
    "Test text",  # No Cyrillic since helv doesn't support it
    fontname="helv",
    fontsize=12,
    color=(0, 0, 0)
)
print(f"insert_textbox returned: {leftover3}")
print(f"Blocks created: {len([b for b in page3.get_text('dict').get('blocks', []) if b.get('type') == 0])}")

doc.save("test_font_methods_output.pdf")
doc.close()

print("\n✅ Saved to: test_font_methods_output.pdf")
