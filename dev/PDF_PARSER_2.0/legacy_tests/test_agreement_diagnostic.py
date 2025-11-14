#!/usr/bin/env python3
"""Diagnostic analysis of Russian agreement translation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz

# Paths
input_pdf = Path("runtime/input/Соглашение_о_расторжении_ИП_Смирнов_docx.pdf")
output_pdf = Path("runtime/output/docx/v002/layout/Соглашение_о_расторжении_ИП_Смирнов_docx_en.pdf")

if not input_pdf.exists():
    print(f"❌ Original not found: {input_pdf}")
    exit(1)

if not output_pdf.exists():
    print(f"❌ Output not found: {output_pdf}")
    exit(1)

print("=" * 80)
print("🔍 RUSSIAN AGREEMENT TRANSLATION - DIAGNOSTIC ANALYSIS")
print("=" * 80)

# Load PDFs
orig_doc = fitz.open(input_pdf)
out_doc = fitz.open(output_pdf)

print(f"\n📄 Document Info:")
print(f"  Original: {orig_doc.page_count} pages")
print(f"  Output:   {out_doc.page_count} pages")

# Analyze each page
for page_num in range(orig_doc.page_count):
    print(f"\n{'='*80}")
    print(f"📄 PAGE {page_num + 1}")
    print("=" * 80)

    orig_page = orig_doc[page_num]
    out_page = out_doc[page_num] if page_num < out_doc.page_count else None

    if not out_page:
        print(f"❌ Output page {page_num + 1} is missing!")
        continue

    # Extract text blocks
    orig_dict = orig_page.get_text("dict", sort=True)
    orig_blocks = [b for b in orig_dict["blocks"] if b.get("type") == 0]

    out_dict = out_page.get_text("dict", sort=True)
    out_blocks = [b for b in out_dict["blocks"] if b.get("type") == 0]

    print(f"\n📊 Block Analysis:")
    print(f"  Original blocks: {len(orig_blocks)}")
    print(f"  Output blocks:   {len(out_blocks)}")
    print(f"  Difference:      {len(out_blocks) - len(orig_blocks):+d}")

    # Extract all text for comparison
    orig_text = orig_page.get_text("text")
    out_text = out_page.get_text("text")

    orig_lines = [line.strip() for line in orig_text.split('\n') if line.strip()]
    out_lines = [line.strip() for line in out_text.split('\n') if line.strip()]

    print(f"\n📝 Text Line Comparison:")
    print(f"  Original lines: {len(orig_lines)}")
    print(f"  Output lines:   {len(out_lines)}")
    print(f"  Difference:     {len(out_lines) - len(orig_lines):+d}")

    # Show first few lines from each
    print(f"\n  Original text (first 5 lines):")
    for i, line in enumerate(orig_lines[:5], 1):
        print(f"    {i}. {line[:60]}{'...' if len(line) > 60 else ''}")

    print(f"\n  Translated text (first 5 lines):")
    for i, line in enumerate(out_lines[:5], 1):
        print(f"    {i}. {line[:60]}{'...' if len(line) > 60 else ''}")

    # Check for missing content
    missing_indicators = []

    # Look for form field keywords in original that might be missing
    form_keywords = ["Смирнов", "ИП", "расторжении", "Соглашение", "подпись", "дата"]

    for keyword in form_keywords:
        orig_count = orig_text.count(keyword)
        out_count = out_text.count(keyword) + out_text.count(keyword.lower())

        if orig_count > 0 and out_count == 0:
            missing_indicators.append(f"'{keyword}' appears {orig_count}x in original but 0x in output")

    if missing_indicators:
        print(f"\n⚠️  Potential Missing Content:")
        for indicator in missing_indicators:
            print(f"    • {indicator}")

    # Font size analysis
    print(f"\n📏 Font Size Analysis:")

    def extract_sizes(blocks):
        sizes = []
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = span.get("size", 0)
                    text = span.get("text", "").strip()
                    if size > 0 and text:
                        sizes.append((size, text[:30]))
        return sizes

    orig_sizes = extract_sizes(orig_blocks)
    out_sizes = extract_sizes(out_blocks)

    if orig_sizes:
        orig_avg = sum(s[0] for s in orig_sizes) / len(orig_sizes)
        orig_min = min(s[0] for s in orig_sizes)
        orig_max = max(s[0] for s in orig_sizes)
        print(f"  Original: avg={orig_avg:.1f}pt, min={orig_min:.1f}pt, max={orig_max:.1f}pt")

    if out_sizes:
        out_avg = sum(s[0] for s in out_sizes) / len(out_sizes)
        out_min = min(s[0] for s in out_sizes)
        out_max = max(s[0] for s in out_sizes)
        print(f"  Output:   avg={out_avg:.1f}pt, min={out_min:.1f}pt, max={out_max:.1f}pt")

        # Count how many spans are at minimum (7pt)
        at_minimum = sum(1 for s in out_sizes if s[0] <= 7.1)
        print(f"  Spans at 7pt minimum: {at_minimum}/{len(out_sizes)} ({100*at_minimum/len(out_sizes):.1f}%)")

        # Show examples of minimum-sized text
        if at_minimum > 0:
            print(f"\n  Examples of 7pt text:")
            count = 0
            for size, text in out_sizes:
                if size <= 7.1 and count < 3:
                    print(f"    • \"{text}...\" ({size:.1f}pt)")
                    count += 1

    # Graphics analysis
    orig_graphics = orig_page.get_drawings()
    out_graphics = out_page.get_drawings()

    print(f"\n🎨 Graphics Elements:")
    print(f"  Original: {len(orig_graphics)} elements")
    print(f"  Output:   {len(out_graphics)} elements")

    # Check for text overlaps
    overlaps = 0
    for i, block_a in enumerate(out_blocks):
        rect_a = fitz.Rect(block_a.get("bbox"))
        for block_b in out_blocks[i+1:]:
            rect_b = fitz.Rect(block_b.get("bbox"))
            if rect_a.intersects(rect_b):
                intersection = rect_a & rect_b
                if intersection.width > 5 and intersection.height > 5:
                    overlaps += 1

    print(f"\n⚠️  Text Overlaps: {overlaps}")

print(f"\n{'='*80}")
print("📋 SUMMARY")
print("=" * 80)

orig_doc.close()
out_doc.close()

print(f"\n✅ Analysis complete. Review output above for specific issues.")
