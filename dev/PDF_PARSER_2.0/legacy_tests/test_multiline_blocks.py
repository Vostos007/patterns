#!/usr/bin/env python3
"""Test if insert_textbox creates multiple blocks for multiline text."""
import fitz

doc = fitz.open()
page = doc.new_page(width=595, height=842)

# Insert font
font = fitz.Font("notos")
page.insert_font(fontname="Test", fontbuffer=font.buffer)

# Insert multiline text that will be truncated
text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
rect = fitz.Rect(100, 100, 300, 130)  # Small rect

print("Inserting 5 lines of text into small rect...")
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
    text_lines = []
    for line in lines:
        line_text = "".join(span.get("text", "") for span in line.get("spans", []))
        text_lines.append(line_text)
    
    print(f"\nBlock {i}:")
    print(f"  BBox: {block.get('bbox')}")
    print(f"  Lines in block: {len(lines)}")
    print(f"  Text: {' | '.join(text_lines)}")

doc.close()

if len(blocks) == 1:
    print("\n✅ Single block created (expected)")
else:
    print(f"\n❌ {len(blocks)} blocks created - PyMuPDF splits multiline text!")
