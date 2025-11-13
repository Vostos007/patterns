#!/usr/bin/env python3
"""Test table column alignment after fix."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz

# Paths
input_pdf = Path("runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf")
output_pdf = Path("runtime/output/csr-report-jan-1-2025-to-jul-30-2025-1---page1/v014/layout/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1_ru.pdf")

if not input_pdf.exists():
    print(f"❌ Original not found: {input_pdf}")
    exit(1)

if not output_pdf.exists():
    print(f"❌ Output not found: {output_pdf}")
    exit(1)

print("=" * 80)
print("📊 TABLE COLUMN ALIGNMENT TEST")
print("=" * 80)

# Load PDFs
orig_doc = fitz.open(input_pdf)
orig_page = orig_doc[0]

out_doc = fitz.open(output_pdf)
out_page = out_doc[0]

# Extract text with position info
orig_dict = orig_page.get_text("dict", sort=True)
out_dict = out_page.get_text("dict", sort=True)

def find_table_header_spans(page_dict, header_keyword="Available"):
    """Find spans containing table headers (same Y-coordinate)."""
    all_spans = []

    for block in page_dict["blocks"]:
        if block.get("type") != 0:  # Text blocks only
            continue

        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if header_keyword in text or "Доступн" in text:  # English or Russian
                    # Get all spans from this line (same Y-coordinate)
                    all_spans_in_line = line.get("spans", [])
                    return all_spans_in_line

    return []

# Find table header rows
orig_header_spans = find_table_header_spans(orig_dict, "Available")
out_header_spans = find_table_header_spans(out_dict, "Доступн")

print(f"\n📋 ORIGINAL TABLE HEADERS:")
print(f"   Found {len(orig_header_spans)} spans in header row")

if orig_header_spans:
    for i, span in enumerate(orig_header_spans):
        text = span.get("text", "")
        origin = span.get("origin", (0, 0))
        bbox = span.get("bbox", (0, 0, 0, 0))

        print(f"   Column {i+1}: X={origin[0]:.1f}  \"{text}\"")
        print(f"            BBox: ({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})")

print(f"\n📋 TRANSLATED TABLE HEADERS (after fix):")
print(f"   Found {len(out_header_spans)} spans in header row")

if out_header_spans:
    for i, span in enumerate(out_header_spans):
        text = span.get("text", "")
        origin = span.get("origin", (0, 0))
        bbox = span.get("bbox", (0, 0, 0, 0))

        print(f"   Column {i+1}: X={origin[0]:.1f}  \"{text}\"")
        print(f"            BBox: ({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})")

# Check alignment
print(f"\n{'='*80}")
print("✅ COLUMN ALIGNMENT ANALYSIS:")
print("=" * 80)

if len(orig_header_spans) > 0 and len(out_header_spans) > 0:
    # Extract X-coordinates
    orig_x_coords = [span.get("origin", (0, 0))[0] for span in orig_header_spans]
    out_x_coords = [span.get("origin", (0, 0))[0] for span in out_header_spans]

    print(f"\nOriginal X-coordinates: {[f'{x:.1f}' for x in orig_x_coords]}")
    print(f"Output X-coordinates:   {[f'{x:.1f}' for x in out_x_coords]}")

    # Check if columns are at similar positions (within 20 pixels tolerance)
    tolerance = 20.0
    columns_aligned = True

    for i in range(min(len(orig_x_coords), len(out_x_coords))):
        orig_x = orig_x_coords[i]
        out_x = out_x_coords[i]
        diff = abs(orig_x - out_x)

        aligned = diff < tolerance
        symbol = "✅" if aligned else "❌"

        print(f"  Column {i+1}: {symbol} Δ={diff:.1f}px (tolerance: {tolerance}px)")

        if not aligned:
            columns_aligned = False

    if columns_aligned:
        print(f"\n🎉 SUCCESS: Table columns are properly aligned!")
        print(f"   All columns positioned within {tolerance}px of original")
    else:
        print(f"\n⚠️  ISSUE: Some columns are misaligned")
        print(f"   Check if translated text is too long for column width")
else:
    print("⚠️  Could not find table headers in one or both PDFs")

orig_doc.close()
out_doc.close()
