#!/usr/bin/env python3
"""
Demo script for PyMuPDF extraction with all 12 enhancements.

This demonstrates the complete graphics extraction pipeline for KPS v2.0.

Usage:
    python examples/pymupdf_extraction_demo.py <path_to_pdf>

Example:
    python examples/pymupdf_extraction_demo.py pattern.pdf
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Direct import to avoid broken docling import
import importlib.util

spec = importlib.util.spec_from_file_location(
    "pymupdf_extractor",
    Path(__file__).parent.parent / "kps/extraction/pymupdf_extractor.py"
)
module = importlib.util.module_from_spec(spec)

# Load dependencies first
from kps.core.assets import Asset, AssetLedger, AssetType, ColorSpace, VectorFont
from kps.core.bbox import BBox

spec.loader.exec_module(module)
PyMuPDFExtractor = module.PyMuPDFExtractor
PyMuPDFExtractorConfig = module.PyMuPDFExtractorConfig


def main():
    """Run PyMuPDF extraction demo."""

    if len(sys.argv) < 2:
        print("Usage: python examples/pymupdf_extraction_demo.py <path_to_pdf>")
        print("\nExample:")
        print("  python examples/pymupdf_extraction_demo.py pattern.pdf")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])

    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(1)

    print("\n" + "="*80)
    print("PyMuPDF Graphics Extraction - KPS v2.0")
    print("="*80)
    print(f"\nInput: {pdf_path}")

    # Configure extractor
    config = PyMuPDFExtractorConfig(
        vector_dpi=300,
        image_format="png",
        extract_images=True,
        extract_vectors=True,
        extract_tables=True,
        min_image_size=10,
        min_bbox_area=100.0,
    )

    # Create output directory
    output_dir = Path("output") / pdf_path.stem / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output: {output_dir}")

    # Initialize extractor
    extractor = PyMuPDFExtractor(config)

    # Extract assets
    print("\nExtracting assets...")
    try:
        ledger = extractor.extract_assets(pdf_path, output_dir)
    except Exception as e:
        print(f"\nError during extraction: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Print summary
    print("\n" + "="*80)
    print("EXTRACTION COMPLETE")
    print("="*80)
    print(f"\nTotal assets: {len(ledger.assets)}")
    print(f"Pages: {ledger.total_pages}")

    completeness = ledger.completeness_check()

    print("\nBy type:")
    for asset_type, count in completeness["by_type"].items():
        if count > 0:
            print(f"  {asset_type:20s}: {count}")

    print("\nBy page:")
    for page, count in completeness["by_page"].items():
        if count > 0:
            print(f"  Page {page}: {count} assets")

    # Show first asset details
    if ledger.assets:
        print("\n" + "="*80)
        print("SAMPLE ASSET (first extracted)")
        print("="*80)

        asset = ledger.assets[0]
        print(f"\nAsset ID: {asset.asset_id}")
        print(f"Type: {asset.asset_type.value}")
        print(f"SHA256: {asset.sha256}")
        print(f"Page: {asset.page_number}")
        print(f"BBox: ({asset.bbox.x0:.1f}, {asset.bbox.y0:.1f}) -> ({asset.bbox.x1:.1f}, {asset.bbox.y1:.1f})")
        print(f"Size: {asset.bbox.width:.1f} x {asset.bbox.height:.1f} pts")
        print(f"CTM: {asset.ctm}")
        print(f"Occurrence: {asset.occurrence}")
        print(f"File: {asset.file_path}")

        if asset.image_width and asset.image_height:
            print(f"Dimensions: {asset.image_width} x {asset.image_height} px")
            dpi_x = (asset.image_width / asset.bbox.width) * 72
            dpi_y = (asset.image_height / asset.bbox.height) * 72
            print(f"DPI: {dpi_x:.0f} x {dpi_y:.0f}")

        print(f"Color space: {asset.colorspace.value}")
        print(f"Has SMask: {asset.has_smask}")
        print(f"Has Clip: {asset.has_clip}")

        if asset.fonts:
            print(f"Fonts: {len(asset.fonts)}")
            for font in asset.fonts[:3]:
                print(f"  - {font.font_name} ({font.font_type})")

    # Save ledger
    json_path = output_dir.parent / "asset_ledger.json"
    ledger.save_json(json_path)
    print(f"\n✓ Asset ledger saved: {json_path}")

    print("\n" + "="*80)
    print("Demo complete!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
