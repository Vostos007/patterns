#!/usr/bin/env python3
"""Detailed analysis of missing content in agreement translation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz

# Paths
input_pdf = Path("runtime/input/Соглашение_о_расторжении_ИП_Смирнов_docx.pdf")
output_pdf = Path("runtime/output/docx/v002/layout/Соглашение_о_расторжении_ИП_Смирнов_docx_en.pdf")

orig_doc = fitz.open(input_pdf)
out_doc = fitz.open(output_pdf)

orig_page = orig_doc[0]
out_page = out_doc[0]

print("=" * 80)
print("🔍 MISSING CONTENT ANALYSIS")
print("=" * 80)

# Extract all text with positions
orig_dict = orig_page.get_text("dict", sort=True)
out_dict = out_page.get_text("dict", sort=True)

print("\n📄 ORIGINAL DOCUMENT - All Text Blocks:\n")

for block_idx, block in enumerate(orig_dict["blocks"][:15]):  # First 15 blocks
    if block.get("type") != 0:
        continue

    bbox = block.get("bbox", [0, 0, 0, 0])
    print(f"Block {block_idx}: BBox=({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})")

    for line_idx, line in enumerate(block.get("lines", [])):
        line_text = "".join(span.get("text", "") for span in line.get("spans", []))
        line_bbox = line.get("bbox", [0, 0, 0, 0])

        # Highlight lines with missing keywords
        missing_markers = []
        if "Смирнов" in line_text:
            missing_markers.append("⚠️ CONTAINS 'Смирнов'")
        if "ИП" in line_text:
            missing_markers.append("⚠️ CONTAINS 'ИП'")
        if "Соглашение" in line_text:
            missing_markers.append("⚠️ CONTAINS 'Соглашение'")

        marker = " " + " ".join(missing_markers) if missing_markers else ""

        print(f"  Line {line_idx}: \"{line_text[:80]}\"{marker}")
        print(f"    BBox: ({line_bbox[0]:.1f}, {line_bbox[1]:.1f}, {line_bbox[2]:.1f}, {line_bbox[3]:.1f})")

        # Show individual spans if they have the keyword
        if missing_markers:
            for span_idx, span in enumerate(line.get("spans", [])):
                span_text = span.get("text", "")
                if span_text.strip():
                    span_bbox = span.get("bbox", [0, 0, 0, 0])
                    print(f"      Span {span_idx}: \"{span_text}\"")
                    print(f"        BBox: ({span_bbox[0]:.1f}, {span_bbox[1]:.1f}, {span_bbox[2]:.1f}, {span_bbox[3]:.1f})")
                    print(f"        Size: {span.get('size', 0):.1f}pt, Font: {span.get('font', 'unknown')}")

    print()

print("\n" + "=" * 80)
print("📄 TRANSLATED DOCUMENT - All Text Blocks:\n")

for block_idx, block in enumerate(out_dict["blocks"][:15]):
    if block.get("type") != 0:
        continue

    bbox = block.get("bbox", [0, 0, 0, 0])
    print(f"Block {block_idx}: BBox=({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})")

    for line_idx, line in enumerate(block.get("lines", [])):
        line_text = "".join(span.get("text", "") for span in line.get("spans", []))
        line_bbox = line.get("bbox", [0, 0, 0, 0])

        print(f"  Line {line_idx}: \"{line_text[:80]}\"")
        print(f"    BBox: ({line_bbox[0]:.1f}, {line_bbox[1]:.1f}, {line_bbox[2]:.1f}, {line_bbox[3]:.1f})")

    print()

# Check what was actually translated
print("\n" + "=" * 80)
print("🔍 TRANSLATION MAPPING CHECK")
print("=" * 80)

# Look for specific problem cases
print("\n1. Title 'СОГЛАШЕНИЕ О РАСТОРЖЕНИИ':")
print("   Should translate to: 'AGREEMENT OF TERMINATION'")
print(f"   Actually got: '{out_dict['blocks'][0]['lines'][0]['spans'][0]['text'] if out_dict['blocks'] else 'N/A'}'")

orig_doc.close()
out_doc.close()
