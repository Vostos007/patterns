#!/usr/bin/env python3
"""Final check of table column alignment."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz

output_pdf = Path("runtime/output/csr-report-jan-1-2025-to-jul-30-2025-1---page1/v015/layout/CSR Report Jan 1 2025 to Jul 30 2025 (1) - page1_ru.pdf")

if not output_pdf.exists():
    print(f"❌ Output not found: {output_pdf}")
    exit(1)

doc = fitz.open(output_pdf)
page = doc[0]
page_dict = page.get_text("dict", sort=True)

print("=" * 80)
print("📊 FINAL TABLE COLUMN ALIGNMENT CHECK (v015)")
print("=" * 80)

# Find the table header row
table_headers = []
keywords = ["Доступн", "Удержан"]  # Russian keywords

for block_idx, block in enumerate(page_dict["blocks"]):
    if block.get("type") != 0:
        continue

    for line_idx, line in enumerate(block.get("lines", [])):
        line_text = "".join(span.get("text", "") for span in line.get("spans", []))

        # Check if this is a table header
        if any(kw in line_text for kw in keywords):
            bbox = line.get("bbox", [])
            y_coord = bbox[1] if len(bbox) > 1 else 0

            if line.get("spans"):
                first_span = line.get("spans")[0]
                origin = first_span.get("origin", (0, 0))
                x_coord = origin[0]

                table_headers.append({
                    "text": line_text.strip(),
                    "x": x_coord,
                    "y": y_coord,
                    "bbox": bbox,
                    "block_idx": block_idx,
                    "line_idx": line_idx
                })

# Sort by Y then X
table_headers.sort(key=lambda c: (c["y"], c["x"]))

# Group by Y-coordinate
from collections import defaultdict
rows = defaultdict(list)
for header in table_headers:
    y_key = round(header["y"] / 5) * 5  # Group within 5px
    rows[y_key].append(header)

print(f"\nFound {len(table_headers)} table header(s) in {len(rows)} row(s):\n")

for y_key in sorted(rows.keys()):
    row = rows[y_key]
    print(f"Row at Y≈{y_key:.1f}px:")

    # Sort columns by X
    row.sort(key=lambda c: c["x"])

    for i, col in enumerate(row):
        print(f"  Column {i+1}:")
        print(f"    Text: \"{col['text']}\"")
        print(f"    X:    {col['x']:.1f}px")
        print(f"    BBox: ({col['bbox'][0]:.1f}, {col['bbox'][1]:.1f}, {col['bbox'][2]:.1f}, {col['bbox'][3]:.1f})")

    print()

print("=" * 80)
print("✅ EXPECTED vs ACTUAL:")
print("=" * 80)

expected_columns = [
    {"name": "Доступное начало", "x_approx": 102},
    {"name": "Доступное окончание", "x_approx": 232},
    {"name": "Удержанное начало", "x_approx": 332},
    {"name": "Удержанное окончание", "x_approx": 478},
]

if len(rows) == 1:
    row = list(rows.values())[0]
    row.sort(key=lambda c: c["x"])

    if len(row) == 4:
        print("✅ Found 4 separate columns (as expected)!\n")

        tolerance = 30  # pixels
        all_aligned = True

        for i, (expected, actual) in enumerate(zip(expected_columns, row)):
            x_diff = abs(actual["x"] - expected["x_approx"])
            aligned = x_diff < tolerance

            status = "✅" if aligned else "❌"
            print(f"{status} Column {i+1}: \"{actual['text'][:20]}...\"")
            print(f"     Expected X≈{expected['x_approx']}px, Got X={actual['x']:.1f}px (Δ={x_diff:.1f}px)")

            if not aligned:
                all_aligned = False

        if all_aligned:
            print(f"\n🎉 SUCCESS: All 4 columns properly aligned!")
        else:
            print(f"\n⚠️  Some columns misaligned")
    else:
        print(f"❌ Expected 4 columns, found {len(row)}")
        print("   Columns may still be merged into single spans")
else:
    print(f"❌ Expected 1 row with 4 columns, found {len(rows)} rows")

doc.close()
