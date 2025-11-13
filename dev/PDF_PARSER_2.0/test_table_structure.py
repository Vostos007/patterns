#!/usr/bin/env python3
"""Analyze table structure in original PDF."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz

# Load original
pdf_path = Path("runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf")

if not pdf_path.exists():
    print(f"❌ File not found: {pdf_path}")
    exit(1)

doc = fitz.open(pdf_path)
page = doc[0]
page_dict = page.get_text("dict", sort=True)

print("=" * 80)
print("📊 ORIGINAL PDF TABLE STRUCTURE ANALYSIS")
print("=" * 80)

# Find the table header block/line
for block_idx, block in enumerate(page_dict["blocks"]):
    if block.get("type") != 0:  # Skip non-text blocks
        continue

    for line_idx, line in enumerate(block.get("lines", [])):
        # Look for line containing "Available beginning"
        line_text = "".join(span.get("text", "") for span in line.get("spans", []))

        if "Available beginning" in line_text:
            print(f"\n🎯 FOUND TABLE HEADER LINE:")
            print(f"   Block: {block_idx}, Line: {line_idx}")
            print(f"   Full text: \"{line_text}\"")
            print(f"   Line BBox: {tuple(round(x, 1) for x in line.get('bbox', []))}")
            print(f"   Line has {len(line.get('spans', []))} span(s)")

            print(f"\n   📌 Individual Spans:")
            for span_idx, span in enumerate(line.get("spans", [])):
                text = span.get("text", "")
                origin = span.get("origin", (0, 0))
                bbox = span.get("bbox", (0, 0, 0, 0))
                size = span.get("size", 0)
                font = span.get("font", "")

                print(f"\n   Span {span_idx}:")
                print(f"      Text:   \"{text}\"")
                print(f"      Origin: ({origin[0]:.1f}, {origin[1]:.1f})")
                print(f"      BBox:   ({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})")
                print(f"      Font:   {font}")
                print(f"      Size:   {size:.1f}pt")

# Also check the EUR row for data cells
for block_idx, block in enumerate(page_dict["blocks"]):
    if block.get("type") != 0:
        continue

    for line_idx, line in enumerate(block.get("lines", [])):
        line_text = "".join(span.get("text", "") for span in line.get("spans", []))

        if "EUR" in line_text and "12" in line_text:
            print(f"\n🎯 FOUND DATA ROW (EUR):")
            print(f"   Block: {block_idx}, Line: {line_idx}")
            print(f"   Full text: \"{line_text}\"")
            print(f"   Line has {len(line.get('spans', []))} span(s)")

            print(f"\n   📌 Individual Spans:")
            for span_idx, span in enumerate(line.get("spans", [])):
                text = span.get("text", "")
                origin = span.get("origin", (0, 0))

                print(f"   Span {span_idx}: X={origin[0]:.1f}  \"{text}\"")

doc.close()

print(f"\n{'='*80}")
print("💡 KEY INSIGHT:")
print("=" * 80)
print("If there are multiple spans with DIFFERENT X-coordinates in the same line,")
print("then they are separate table columns that should be preserved.")
print("Our current code concatenates them into one span during translation.")
