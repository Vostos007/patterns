#!/usr/bin/env python3
"""Test multiline that actually fits."""
import fitz

doc = fitz.open()
page = doc.new_page(width=595, height=842)

# Insert font
font = fitz.Font("notos")
page.insert_font(fontname="Test", fontbuffer=font.buffer)

# Insert 3 lines with plenty of room
text = "Line 1\nLine 2\nLine 3"
rect = fitz.Rect(100, 100, 300, 200)  # Plenty of room

print("Inserting 3 lines with plenty of room...")
leftover = page.insert_textbox(
    rect,
    text,
    fontname="Test",
    fontsize=10,
    color=(0, 0, 0)
)

blocks = [b for b in page.get_text("dict").get("blocks", []) if b.get("type") == 0]

print(f"Leftover: {leftover}")
print(f"Blocks created: {len(blocks)}")

for i, block in enumerate(blocks):
    lines = block.get("lines", [])
    print(f"\nBlock {i}: {len(lines)} lines")

doc.close()

print(f"\n{'✅' if len(blocks) == 1 else '❌'} Result: {len(blocks)} block(s)")
