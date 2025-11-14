#!/usr/bin/env python3
"""Test if insert_textbox with multiline text creates multiple blocks."""
import fitz

# Create a test PDF
doc = fitz.open()
page = doc.new_page(width=595, height=842)

rect = fitz.Rect(100, 100, 400, 300)

# Insert multiline text
multiline_text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"

print("Inserting multiline text...")
print(f"Text: {repr(multiline_text)}")
print(f"Rect: {rect}")

leftover = page.insert_textbox(
    rect,
    multiline_text,
    fontname="helv",
    fontsize=12,
    align=fitz.TEXT_ALIGN_LEFT
)

print(f"Leftover: {repr(leftover)}")

# Check how many text blocks were created
blocks_dict = page.get_text("dict", sort=True)
text_blocks = [b for b in blocks_dict.get("blocks", []) if b.get("type") == 0]

print(f"\nText blocks created: {len(text_blocks)}")

for i, block in enumerate(text_blocks):
    lines = block.get("lines", [])
    print(f"\nBlock {i}:")
    print(f"  Lines: {len(lines)}")
    print(f"  BBox: {block.get('bbox')}")
    for j, line in enumerate(lines):
        line_text = "".join(span.get("text", "") for span in line.get("spans", []))
        print(f"    Line {j}: {line_text}")

doc.close()

print("\n" + "=" * 70)
if len(text_blocks) == 1:
    print("✅ GOOD: One multiline text block created")
else:
    print(f"❌ PROBLEM: {len(text_blocks)} text blocks created from one insert_textbox call!")
