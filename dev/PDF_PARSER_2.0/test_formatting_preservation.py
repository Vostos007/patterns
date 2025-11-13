#!/usr/bin/env python3
"""Test formatting preservation with TextWriter approach."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kps.layout_preserver import process_pdf
import fitz

input_pdf = Path("runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf")
output_dir = Path("runtime/test_formatting")

if not input_pdf.exists():
    print(f"❌ File not found: {input_pdf}")
    exit(1)

# Generate with NEW formatting-preserving mode
print("=" * 70)
print("🎨 Testing TextWriter with formatting preservation")
print("=" * 70)

produced = process_pdf(
    input_pdf,
    output_dir,
    target_langs=["ru"],
    preserve_formatting=True
)

print(f"\n✅ Generated: {produced[0]}")

# Analyze the result
doc = fitz.open(produced[0])
page = doc[0]
page_dict = page.get_text("dict", sort=True)
text_blocks = [b for b in page_dict["blocks"] if b.get("type") == 0]

print(f"\n📊 Analysis:")
print(f"  Text blocks: {len(text_blocks)}")

# Check if formatting is preserved
fonts_used = set()
sizes_used = set()
colors_used = set()

for block in text_blocks[:3]:  # Check first 3 blocks
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            fonts_used.add(span.get("font", "unknown"))
            sizes_used.add(round(span.get("size", 0), 1))
            color_int = span.get("color", 0)
            color_hex = f"#{(color_int >> 16) & 0xFF:02x}{(color_int >> 8) & 0xFF:02x}{color_int & 0xFF:02x}"
            colors_used.add(color_hex)

print(f"\n  Fonts: {', '.join(sorted(fonts_used))}")
print(f"  Sizes: {sorted(sizes_used)} pt")
print(f"  Colors: {sorted(colors_used)}")

doc.close()

# Compare with original
print(f"\n{'='*70}")
print("📋 Comparing with original:")
print(f"{'='*70}")

orig_doc = fitz.open(input_pdf)
orig_page = orig_doc[0]
orig_dict = orig_page.get_text("dict", sort=True)
orig_blocks = [b for b in orig_dict["blocks"] if b.get("type") == 0]

orig_fonts = set()
orig_sizes = set()
orig_colors = set()

for block in orig_blocks[:3]:
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            orig_fonts.add(span.get("font", "unknown"))
            orig_sizes.add(round(span.get("size", 0), 1))
            color_int = span.get("color", 0)
            color_hex = f"#{(color_int >> 16) & 0xFF:02x}{(color_int >> 8) & 0xFF:02x}{color_int & 0xFF:02x}"
            orig_colors.add(color_hex)

print(f"\nOriginal:")
print(f"  Fonts: {', '.join(sorted(orig_fonts))}")
print(f"  Sizes: {sorted(orig_sizes)} pt")
print(f"  Colors: {sorted(orig_colors)}")

orig_doc.close()

# Check preservation
print(f"\n{'='*70}")
print("✅ Formatting Preservation Check:")
print(f"{'='*70}")

sizes_match = orig_sizes == sizes_used
colors_match = bool(colors_used & orig_colors)  # At least some overlap

print(f"  Font sizes preserved: {'✅' if sizes_match else '❌'}")
print(f"  Colors preserved: {'✅' if colors_match else '❌'}")

if sizes_match and colors_match:
    print(f"\n🎉 SUCCESS: Formatting preserved!")
else:
    print(f"\n⚠️  Some formatting may be lost")

print(f"\n📄 Output PDF: {produced[0]}")
