#!/usr/bin/env python3
"""Test partial fit of multiline text."""
import fitz

doc = fitz.open()
page = doc.new_page(width=595, height=842)

# Insert font
font = fitz.Font("notos")
page.insert_font(fontname="Test", fontbuffer=font.buffer)

# Insert 10 lines but only room for ~4 lines
text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6\nLine 7\nLine 8\nLine 9\nLine 10"
rect = fitz.Rect(100, 100, 300, 180)  # Room for ~4 lines at 10pt (need 20pt/line)

print("Inserting 10 lines into rect with room for ~4...")
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
    print(f"  BBox: {tuple(round(x, 1) for x in block.get('bbox'))}")
    print(f"  Lines in block: {len(lines)}")
    print(f"  Text: {' | '.join(text_lines)}")

doc.save("test_multiline_partial_output.pdf")
doc.close()

if len(blocks) == 1:
    print("\n✅ Single block with partial text (good)")
else:
    print(f"\n⚠️  {len(blocks)} blocks - multiline text was split!")
