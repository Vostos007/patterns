#!/usr/bin/env python3
"""Debug layout preservation text overlay issues.

This script analyzes PDF text layers to identify:
- Overlapping text blocks (causes garbled/smeared text)
- Font usage and Cyrillic compatibility
- Text positioning issues
"""

import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("❌ PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)


def analyze_pdf_layers(pdf_path: Path) -> dict:
    """Analyze PDF text layers and positioning.

    Returns:
        dict with analysis results including overlaps, fonts, and issues
    """
    if not pdf_path.exists():
        print(f"❌ File not found: {pdf_path}")
        sys.exit(1)

    doc = fitz.open(pdf_path)
    page = doc[0]  # Analyze first page

    results = {
        "file": pdf_path.name,
        "page_size": (page.rect.width, page.rect.height),
        "text_blocks": [],
        "overlaps": [],
        "fonts": set(),
        "warnings": []
    }

    # Get text blocks with positioning
    blocks_dict = page.get_text("dict", sort=True)
    text_blocks = [b for b in blocks_dict["blocks"] if b.get("type") == 0]

    results["text_blocks"] = text_blocks

    # Check for overlapping text blocks
    for i, b1 in enumerate(text_blocks):
        bbox1 = fitz.Rect(b1["bbox"])
        for j, b2 in enumerate(text_blocks[i+1:], i+1):
            bbox2 = fitz.Rect(b2["bbox"])
            if bbox1.intersects(bbox2):
                overlap_area = (bbox1 & bbox2).get_area()
                results["overlaps"].append({
                    "block1": i,
                    "block2": j,
                    "area": overlap_area,
                    "bbox1": tuple(bbox1),
                    "bbox2": tuple(bbox2)
                })

    # Collect fonts used
    for block in text_blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                font = span.get("font", "unknown")
                results["fonts"].add(font)

    doc.close()
    return results


def print_analysis(results: dict):
    """Print formatted analysis results."""
    print(f"\n{'='*70}")
    print(f"📄 PDF Analysis: {results['file']}")
    print(f"{'='*70}")

    width, height = results["page_size"]
    print(f"\n📐 Page Size: {width:.1f} x {height:.1f} pt")
    print(f"📝 Text Blocks: {len(results['text_blocks'])}")

    # Print overlap analysis
    overlaps = results["overlaps"]
    if overlaps:
        print(f"\n⚠️  OVERLAPPING TEXT DETECTED: {len(overlaps)} overlaps")
        print("   This causes garbled/smeared text rendering!\n")

        for i, overlap in enumerate(overlaps[:5], 1):  # Show first 5
            print(f"   {i}. Block {overlap['block1']} ↔ Block {overlap['block2']}")
            print(f"      Overlap area: {overlap['area']:.1f} sq pt")
            if i < len(overlaps):
                print()

        if len(overlaps) > 5:
            print(f"   ... and {len(overlaps) - 5} more overlaps")

        results["warnings"].append(
            f"Found {len(overlaps)} overlapping text blocks - this is the root cause!"
        )
    else:
        print(f"\n✅ No overlapping text detected")
        print("   Text layers are clean and separated")

    # Print font analysis
    print(f"\n🔤 Fonts Used: {len(results['fonts'])}")
    fonts_sorted = sorted(results["fonts"])

    for font in fonts_sorted:
        font_lower = font.lower()

        # Check for Cyrillic compatibility
        cyrillic_ok = any(name in font_lower for name in [
            "noto", "dejavu", "arial unicode", "liberation",
            "times new roman", "georgia", "verdana"
        ])

        status = "✅" if cyrillic_ok else "⚠️"
        print(f"   {status} {font}")

        if not cyrillic_ok:
            if "helv" in font_lower or font_lower == "helvetica":
                results["warnings"].append(
                    f"Font '{font}' has poor Cyrillic support - may cause rendering issues"
                )

    # Print warnings summary
    if results["warnings"]:
        print(f"\n{'='*70}")
        print("⚠️  WARNINGS:")
        print(f"{'='*70}")
        for i, warning in enumerate(results["warnings"], 1):
            print(f"{i}. {warning}")

    print(f"\n{'='*70}\n")


def compare_pdfs(pdf1_path: Path, pdf2_path: Path):
    """Compare two PDFs (e.g., main vs layout-preserved)."""
    print("\n" + "="*70)
    print("🔍 COMPARING TWO PDFs")
    print("="*70)

    print(f"\n📄 PDF 1: {pdf1_path.name}")
    results1 = analyze_pdf_layers(pdf1_path)
    print(f"   Text blocks: {len(results1['text_blocks'])}")
    print(f"   Overlaps: {len(results1['overlaps'])}")
    print(f"   Fonts: {', '.join(sorted(results1['fonts']))}")

    print(f"\n📄 PDF 2: {pdf2_path.name}")
    results2 = analyze_pdf_layers(pdf2_path)
    print(f"   Text blocks: {len(results2['text_blocks'])}")
    print(f"   Overlaps: {len(results2['overlaps'])}")
    print(f"   Fonts: {', '.join(sorted(results2['fonts']))}")

    print(f"\n{'='*70}")
    print("💡 RECOMMENDATION:")
    print(f"{'='*70}")

    if len(results1["overlaps"]) < len(results2["overlaps"]):
        print(f"✅ Use PDF 1: {pdf1_path.name}")
        print(f"   (Fewer overlaps: {len(results1['overlaps'])} vs {len(results2['overlaps'])})")
    elif len(results2["overlaps"]) < len(results1["overlaps"]):
        print(f"✅ Use PDF 2: {pdf2_path.name}")
        print(f"   (Fewer overlaps: {len(results2['overlaps'])} vs {len(results1['overlaps'])})")
    else:
        print("Both PDFs have similar overlap counts")

    print(f"\n{'='*70}\n")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Analyze single PDF:")
        print("    python debug_layout_overlap.py <pdf_path>")
        print()
        print("  Compare two PDFs:")
        print("    python debug_layout_overlap.py <pdf1_path> <pdf2_path>")
        print()
        print("Example:")
        print("  python debug_layout_overlap.py runtime/output/.../layout/file_ru.pdf")
        sys.exit(1)

    pdf1_path = Path(sys.argv[1])

    if len(sys.argv) == 3:
        # Compare mode
        pdf2_path = Path(sys.argv[2])
        compare_pdfs(pdf1_path, pdf2_path)
    else:
        # Single analysis mode
        results = analyze_pdf_layers(pdf1_path)
        print_analysis(results)


if __name__ == "__main__":
    main()
