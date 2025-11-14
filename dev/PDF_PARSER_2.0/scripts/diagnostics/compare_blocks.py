#!/usr/bin/env python3
"""Compare text blocks between original and translated PDFs."""
import fitz
from pathlib import Path

original_pdf = Path("runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf")
translated_pdf = Path("runtime/output/csr-report-jan-1-2025-to-jul-30-2025-1---page1/v001/layout/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1_ru.pdf")

def get_block_info(pdf_path):
    """Extract block information."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    page_dict = page.get_text("dict", sort=True)
    blocks = [b for b in page_dict.get("blocks", []) if b.get("type") == 0]

    block_info = []
    for i, block in enumerate(blocks):
        bbox = block.get("bbox", [0, 0, 0, 0])
        text_lines = []
        for line in block.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                line_text += span.get("text", "")
            text_lines.append(line_text)

        full_text = " ".join(text_lines)
        block_info.append({
            "index": i,
            "bbox": bbox,
            "text": full_text[:100],  # First 100 chars
            "lines": len(block.get("lines", []))
        })

    doc.close()
    return block_info

print("=" * 70)
print("ORIGINAL PDF")
print("=" * 70)
orig_blocks = get_block_info(original_pdf)
print(f"Total blocks: {len(orig_blocks)}\n")
for b in orig_blocks:
    print(f"Block {b['index']}: bbox={tuple(round(x, 1) for x in b['bbox'])}")
    print(f"  Lines: {b['lines']}")
    print(f"  Text: {b['text'][:60]}...")
    print()

print("\n" + "=" * 70)
print("TRANSLATED PDF")
print("=" * 70)
trans_blocks = get_block_info(translated_pdf)
print(f"Total blocks: {len(trans_blocks)}\n")
for b in trans_blocks:
    print(f"Block {b['index']}: bbox={tuple(round(x, 1) for x in b['bbox'])}")
    print(f"  Lines: {b['lines']}")
    print(f"  Text: {b['text'][:60]}...")
    print()

print("\n" + "=" * 70)
print("ANALYSIS")
print("=" * 70)
print(f"Original: {len(orig_blocks)} blocks")
print(f"Translated: {len(trans_blocks)} blocks")
print(f"Extra blocks: {len(trans_blocks) - len(orig_blocks)}")

# Check for overlaps in translated PDF
print("\nChecking for bbox overlaps...")
overlaps = []
for i, b1 in enumerate(trans_blocks):
    bbox1 = fitz.Rect(b1["bbox"])
    for j, b2 in enumerate(trans_blocks[i+1:], i+1):
        bbox2 = fitz.Rect(b2["bbox"])
        if bbox1.intersects(bbox2):
            overlap_area = (bbox1 & bbox2).get_area()
            overlaps.append((i, j, overlap_area))
            print(f"  Block {i} overlaps Block {j} ({overlap_area:.1f} sq pt)")
