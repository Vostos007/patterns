#!/usr/bin/env python3
"""Debug the actual block structure."""
import fitz
from pathlib import Path

input_pdf = Path("runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf")
doc = fitz.open(input_pdf)
page = doc[0]

page_dict = page.get_text("dict", sort=True)
text_blocks = [b for b in page_dict.get("blocks", []) if b.get("type") == 0]

print(f"Total text blocks: {len(text_blocks)}\n")

for i, block in enumerate(text_blocks[:3]):  # First 3 blocks
    bbox = block.get("bbox", [0, 0, 0, 0])
    height = bbox[3] - bbox[1]
    lines = block.get("lines", [])
    
    print(f"Block {i}:")
    print(f"  BBox: {tuple(round(x, 1) for x in bbox)}")
    print(f"  Height: {height:.1f}pt")
    print(f"  Lines in block: {len(lines)}")
    
    for j, line in enumerate(lines):
        line_bbox = line.get("bbox", [0, 0, 0, 0])
        line_height = line_bbox[3] - line_bbox[1]
        spans = line.get("spans", [])
        line_text = "".join(span.get("text", "") for span in spans)
        
        print(f"    Line {j}:")
        print(f"      BBox: {tuple(round(x, 1) for x in line_bbox)}")
        print(f"      Height: {line_height:.1f}pt")
        print(f"      Spans: {len(spans)}")
        print(f"      Text: {line_text}")
        
        if len(spans) > 0:
            fontsize = spans[0].get("size", 0)
            print(f"      Fontsize: {fontsize:.1f}pt")
    
    print()

doc.close()
