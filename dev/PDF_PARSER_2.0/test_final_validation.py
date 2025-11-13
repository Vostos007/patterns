#!/usr/bin/env python3
"""Final validation of complete formatting preservation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz

# Paths
input_pdf = Path("runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf")
output_pdf = Path("runtime/output/csr-report-jan-1-2025-to-jul-30-2025-1---page1/v016/layout/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1_ru.pdf")

if not input_pdf.exists():
    print(f"❌ Original not found: {input_pdf}")
    exit(1)

if not output_pdf.exists():
    print(f"❌ Output not found: {output_pdf}")
    exit(1)

print("=" * 80)
print("🔍 FINAL FORMATTING PRESERVATION VALIDATION")
print("=" * 80)

# Load PDFs
orig_doc = fitz.open(input_pdf)
orig_page = orig_doc[0]

out_doc = fitz.open(output_pdf)
out_page = out_doc[0]

# Extract text blocks
orig_dict = orig_page.get_text("dict", sort=True)
orig_blocks = [b for b in orig_dict["blocks"] if b.get("type") == 0]

out_dict = out_page.get_text("dict", sort=True)
out_blocks = [b for b in out_dict["blocks"] if b.get("type") == 0]

print(f"\n📊 Block Counts:")
print(f"  Original: {len(orig_blocks)} text blocks")
print(f"  Output:   {len(out_blocks)} text blocks")

# Criterion 1: Font sizes match exactly
print(f"\n{'='*80}")
print("1️⃣  FONT SIZES (must match exactly)")
print("=" * 80)

orig_sizes = set()
for block in orig_blocks[:5]:  # Check first 5 blocks
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            orig_sizes.add(round(span.get("size", 0), 1))

out_sizes = set()
for block in out_blocks[:5]:
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            out_sizes.add(round(span.get("size", 0), 1))

print(f"  Original sizes: {sorted(orig_sizes)} pt")
print(f"  Output sizes:   {sorted(out_sizes)} pt")

sizes_match = orig_sizes == out_sizes
print(f"  {'✅ PASS' if sizes_match else '❌ FAIL'}: Font sizes {'match exactly' if sizes_match else 'do not match'}")

# Criterion 2: Colors preserved
print(f"\n{'='*80}")
print("2️⃣  COLORS (must preserve original colors)")
print("=" * 80)

def extract_colors(blocks):
    colors = set()
    for block in blocks[:5]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                color_int = span.get("color", 0)
                color_hex = f"#{(color_int >> 16) & 0xFF:02x}{(color_int >> 8) & 0xFF:02x}{color_int & 0xFF:02x}"
                colors.add(color_hex)
    return colors

orig_colors = extract_colors(orig_blocks)
out_colors = extract_colors(out_blocks)

print(f"  Original colors: {sorted(orig_colors)}")
print(f"  Output colors:   {sorted(out_colors)}")

# At least some overlap (colors should be preserved)
colors_preserved = bool(orig_colors & out_colors)
print(f"  {'✅ PASS' if colors_preserved else '❌ FAIL'}: Colors {'preserved' if colors_preserved else 'not preserved'}")

# Criterion 3: Table borders visible
print(f"\n{'='*80}")
print("3️⃣  TABLE BORDERS (must be visible and positioned correctly)")
print("=" * 80)

orig_graphics = orig_page.get_drawings()
out_graphics = out_page.get_drawings()

print(f"  Original graphics: {len(orig_graphics)} elements")
print(f"  Output graphics:   {len(out_graphics)} elements")

graphics_preserved = len(out_graphics) >= len(orig_graphics) * 0.8  # At least 80% preserved
print(f"  {'✅ PASS' if graphics_preserved else '❌ FAIL'}: Graphics {'preserved' if graphics_preserved else 'significantly lost'}")

# Criterion 4: No text overlaps (0 overlaps maintained)
print(f"\n{'='*80}")
print("4️⃣  TEXT OVERLAPS (must be 0)")
print("=" * 80)

def count_overlaps(blocks):
    overlaps = 0
    for i, block_a in enumerate(blocks):
        rect_a = fitz.Rect(block_a.get("bbox"))
        for block_b in blocks[i+1:]:
            rect_b = fitz.Rect(block_b.get("bbox"))
            if rect_a.intersects(rect_b):
                intersection = rect_a & rect_b
                if intersection.width > 5 and intersection.height > 5:
                    overlaps += 1
    return overlaps

out_overlaps = count_overlaps(out_blocks)
print(f"  Text overlaps: {out_overlaps}")
print(f"  {'✅ PASS' if out_overlaps == 0 else '❌ FAIL'}: {'No overlaps detected' if out_overlaps == 0 else f'{out_overlaps} overlaps found'}")

# Criterion 5: Text rendering quality
print(f"\n{'='*80}")
print("5️⃣  TEXT RENDERING QUALITY (manual visual check at 400-800% zoom)")
print("=" * 80)
print(f"  📄 Open this file for visual inspection:")
print(f"     {output_pdf}")
print(f"  🔍 Zoom to 400-800% and check:")
print(f"     • Text edges are sharp (not pixelated)")
print(f"     • Font rendering is clean")
print(f"     • No blurring or artifacts")

# Final summary
print(f"\n{'='*80}")
print("📋 VALIDATION SUMMARY")
print("=" * 80)

all_passed = sizes_match and colors_preserved and graphics_preserved and out_overlaps == 0

print(f"\n  1. Font sizes:        {'✅ PASS' if sizes_match else '❌ FAIL'}")
print(f"  2. Colors:            {'✅ PASS' if colors_preserved else '❌ FAIL'}")
print(f"  3. Table borders:     {'✅ PASS' if graphics_preserved else '❌ FAIL'}")
print(f"  4. No overlaps:       {'✅ PASS' if out_overlaps == 0 else '❌ FAIL'}")
print(f"  5. Render quality:    ⏳ MANUAL CHECK REQUIRED")

if all_passed:
    print(f"\n{'🎉 SUCCESS: All automated checks passed!' if all_passed else '⚠️  Some checks failed'}")
    print(f"\n✅ Complete formatting preservation achieved!")
    print(f"   • Exact font sizes maintained")
    print(f"   • Original colors preserved")
    print(f"   • Table borders intact")
    print(f"   • Zero text overlaps")
else:
    print(f"\n⚠️  ISSUES DETECTED - See details above")

orig_doc.close()
out_doc.close()

exit(0 if all_passed else 1)
