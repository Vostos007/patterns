#!/usr/bin/env python3
"""Test span-level formatting extraction."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kps.layout_preserver import extract_span_formatting, extract_block_with_formatting
import fitz

# Load CSR PDF
pdf_path = Path("runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf")

if not pdf_path.exists():
    print(f"❌ File not found: {pdf_path}")
    exit(1)

doc = fitz.open(pdf_path)
page = doc[0]
page_dict = page.get_text("dict", sort=True)
text_blocks = [b for b in page_dict["blocks"] if b.get("type") == 0]

print(f"Analyzing {len(text_blocks)} text blocks\n")

# Test on first 3 blocks
for i, block in enumerate(text_blocks[:3]):
    print(f"{'='*70}")
    print(f"Block {i}:")
    print(f"{'='*70}")
    
    formatted_lines = extract_block_with_formatting(block)
    
    print(f"Lines: {len(formatted_lines)}\n")
    
    for line_idx, line_data in enumerate(formatted_lines):
        print(f"  Line {line_idx}:")
        print(f"    BBox: {tuple(round(x, 1) for x in line_data['bbox'])}")
        print(f"    Spans: {len(line_data['spans'])}")
        
        for span_idx, span_fmt in enumerate(line_data['spans']):
            text = span_fmt['text']
            font = span_fmt['font']
            size = span_fmt['size']
            color = span_fmt['color']
            is_bold = span_fmt['is_bold']
            is_italic = span_fmt['is_italic']
            
            # Format color as hex
            color_hex = f"#{int(color[0]*255):02x}{int(color[1]*255):02x}{int(color[2]*255):02x}"
            
            # Style indicators
            style = []
            if is_bold:
                style.append("BOLD")
            if is_italic:
                style.append("ITALIC")
            style_str = f" [{', '.join(style)}]" if style else ""
            
            print(f"      Span {span_idx}: \"{text[:40]}{'...' if len(text) > 40 else ''}\"")
            print(f"        Font: {font}{style_str}")
            print(f"        Size: {size:.1f}pt")
            print(f"        Color: {color_hex}")
        
        print()
    
    print()

doc.close()

print("✅ Span extraction test completed!")
