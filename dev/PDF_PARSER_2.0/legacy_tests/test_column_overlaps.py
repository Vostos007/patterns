#!/usr/bin/env python3
"""Test for column text overlaps after fontsize scaling fix."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz

output_pdf = Path("runtime/output/csr-report-jan-1-2025-to-jul-30-2025-1---page1/v016/layout/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1_ru.pdf")

if not output_pdf.exists():
    print(f"❌ Output not found: {output_pdf}")
    exit(1)

doc = fitz.open(output_pdf)
page = doc[0]
page_dict = page.get_text("dict", sort=True)

print("=" * 80)
print("🔍 COLUMN OVERLAP DETECTION (v016 with fontsize scaling)")
print("=" * 80)

# Find table header and data rows
table_spans = []

keywords = ["Доступн", "Удержан", "евро", "USD"]

for block_idx, block in enumerate(page_dict["blocks"]):
    if block.get("type") != 0:
        continue

    for line_idx, line in enumerate(block.get("lines", [])):
        line_text = "".join(span.get("text", "") for span in line.get("spans", []))

        # Check if this is table-related
        if any(kw in line_text for kw in keywords):
            for span in line.get("spans", []):
                text = span.get("text", "")
                bbox = span.get("bbox", (0, 0, 0, 0))
                size = span.get("size", 0)

                if text.strip():
                    table_spans.append({
                        "text": text,
                        "bbox": fitz.Rect(bbox),
                        "size": size,
                        "block": block_idx,
                        "line": line_idx
                    })

print(f"\nFound {len(table_spans)} table text spans\n")

# Check for overlaps
overlaps = []
for i, span_a in enumerate(table_spans):
    for j, span_b in enumerate(table_spans[i+1:], start=i+1):
        # Check if bboxes overlap
        if span_a["bbox"].intersects(span_b["bbox"]):
            intersection = span_a["bbox"] & span_b["bbox"]

            # Ignore tiny overlaps (< 2px, likely rounding errors)
            if intersection.width > 2.0 and intersection.height > 2.0:
                overlaps.append({
                    "span_a": span_a,
                    "span_b": span_b,
                    "intersection": intersection
                })

                print(f"❌ OVERLAP DETECTED:")
                print(f"   Span A: \"{span_a['text'][:30]}\" ({span_a['size']:.1f}pt)")
                print(f"     BBox: ({span_a['bbox'].x0:.1f}, {span_a['bbox'].y0:.1f}, {span_a['bbox'].x1:.1f}, {span_a['bbox'].y1:.1f})")
                print(f"   Span B: \"{span_b['text'][:30]}\" ({span_b['size']:.1f}pt)")
                print(f"     BBox: ({span_b['bbox'].x0:.1f}, {span_b['bbox'].y0:.1f}, {span_b['bbox'].x1:.1f}, {span_b['bbox'].y1:.1f})")
                print(f"   Overlap area: {intersection.width:.1f}px × {intersection.height:.1f}px")
                print()

print("=" * 80)
print("📋 SUMMARY:")
print("=" * 80)

if len(overlaps) == 0:
    print(f"\n🎉 SUCCESS: No text overlaps detected!")
    print(f"   All {len(table_spans)} table spans properly constrained within columns")
else:
    print(f"\n⚠️  Found {len(overlaps)} overlapping span pairs")
    print(f"   Fontsize scaling may need adjustment")

# Check minimum fontsize
print(f"\n{'='*80}")
print("📏 FONTSIZE ANALYSIS:")
print("=" * 80)

fontsizes = [span["size"] for span in table_spans]
min_size = min(fontsizes) if fontsizes else 0
max_size = max(fontsizes) if fontsizes else 0
avg_size = sum(fontsizes) / len(fontsizes) if fontsizes else 0

print(f"\n  Minimum fontsize: {min_size:.1f}pt")
print(f"  Maximum fontsize: {max_size:.1f}pt")
print(f"  Average fontsize: {avg_size:.1f}pt")

below_threshold = [s for s in fontsizes if s < 7.0]
if below_threshold:
    print(f"\n  ⚠️  {len(below_threshold)} spans below 7pt threshold!")
else:
    print(f"\n  ✅ All spans ≥ 7pt (readability threshold)")

doc.close()

exit(0 if len(overlaps) == 0 else 1)
