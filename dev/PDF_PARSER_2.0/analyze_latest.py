#!/usr/bin/env python3
"""Analyze latest translated PDF."""
import fitz
from pathlib import Path

latest_pdf = Path("runtime/output/csr-report-jan-1-2025-to-jul-30-2025-1---page1/v008/layout/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1_ru.pdf")

if not latest_pdf.exists():
    print(f"File not found: {latest_pdf}")
    exit(1)

doc = fitz.open(latest_pdf)
page = doc[0]
blocks_dict = page.get_text("dict", sort=True)
text_blocks = [b for b in blocks_dict.get("blocks", []) if b.get("type") == 0]

print(f"Total text blocks: {len(text_blocks)}\n")

for i, block in enumerate(text_blocks):
    bbox = block.get("bbox", [0, 0, 0, 0])
    lines = block.get("lines", [])
    
    # Extract text
    text_lines = []
    for line in lines:
        line_text = "".join(span.get("text", "") for span in line.get("spans", []))
        text_lines.append(line_text)
    
    full_text = " ".join(text_lines)
    
    print(f"Block {i}:")
    print(f"  BBox: {tuple(round(x, 1) for x in bbox)}")
    print(f"  Lines: {len(lines)}")
    print(f"  Text: {full_text[:70]}...")
    print()

# Check for overlaps
overlaps = []
for i, b1 in enumerate(text_blocks):
    bbox1 = fitz.Rect(b1["bbox"])
    for j, b2 in enumerate(text_blocks[i+1:], i+1):
        bbox2 = fitz.Rect(b2["bbox"])
        if bbox1.intersects(bbox2):
            overlap_area = (bbox1 & bbox2).get_area()
            overlaps.append((i, j, overlap_area))

print("=" * 70)
print(f"Overlaps: {len(overlaps)}")
for i, j, area in overlaps:
    print(f"  Block {i} overlaps Block {j} ({area:.1f} sq pt)")

doc.close()
