#!/usr/bin/env python3
"""Find all table column headers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz

pdf_path = Path("runtime/input/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1.pdf")
doc = fitz.open(pdf_path)
page = doc[0]
page_dict = page.get_text("dict", sort=True)

print("=" * 80)
print("📊 ALL TABLE COLUMN HEADERS")
print("=" * 80)

# Keywords for table column headers
keywords = ["Available", "Withheld", "beginning", "ending"]

# Y-coordinate tolerance for "same row"
y_tolerance = 5.0
table_y = None

column_headers = []

for block_idx, block in enumerate(page_dict["blocks"]):
    if block.get("type") != 0:
        continue

    for line_idx, line in enumerate(block.get("lines", [])):
        line_text = "".join(span.get("text", "") for span in line.get("spans", []))

        # Check if this is a table header
        if any(kw in line_text for kw in keywords):
            bbox = line.get("bbox", [])
            y_coord = bbox[1] if len(bbox) > 1 else 0

            # Group by Y-coordinate (same row)
            if table_y is None:
                table_y = y_coord
            elif abs(y_coord - table_y) < y_tolerance:
                # Same row!
                pass
            else:
                # Different row, skip
                continue

            # Get first span's origin (X-coordinate)
            if line.get("spans"):
                first_span = line.get("spans")[0]
                origin = first_span.get("origin", (0, 0))
                x_coord = origin[0]

                column_headers.append({
                    "text": line_text.strip(),
                    "x": x_coord,
                    "y": y_coord,
                    "block_idx": block_idx,
                    "line_idx": line_idx
                })

# Sort by X-coordinate
column_headers.sort(key=lambda c: c["x"])

print(f"\nFound {len(column_headers)} column headers (sorted left to right):\n")

for i, col in enumerate(column_headers):
    print(f"Column {i+1}:")
    print(f"  Text: \"{col['text']}\"")
    print(f"  X:    {col['x']:.1f}px")
    print(f"  Y:    {col['y']:.1f}px")
    print(f"  Block: {col['block_idx']}, Line: {col['line_idx']}")
    print()

print("=" * 80)
print("💡 KEY FINDING:")
print("=" * 80)
print(f"Each column header is in a SEPARATE BLOCK (not separate spans)!")
print(f"This means they're translated INDEPENDENTLY.")
print(f"Our X-coordinate fix positions each translation at the right START position,")
print(f"but if the translation is too long, it overflows into the next column.")

doc.close()
