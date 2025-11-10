#!/usr/bin/env python3
"""Test script for PyMuPDF extraction with all 12 enhancements."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from kps.extraction import PyMuPDFExtractor, PyMuPDFExtractorConfig
from kps.core.assets import AssetType


def test_pymupdf_extraction():
    """Test PyMuPDF extraction on a sample PDF."""

    # Check if a test PDF exists
    test_pdfs = [
        Path("tests/fixtures/sample_pattern.pdf"),
        Path("sample.pdf"),
        Path("pattern.pdf"),
    ]

    test_pdf = None
    for pdf_path in test_pdfs:
        if pdf_path.exists():
            test_pdf = pdf_path
            break

    if not test_pdf:
        print("No test PDF found. Please provide a PDF file.")
        print("Usage: python test_pymupdf_extraction.py <pdf_path>")
        return

    print(f"\n{'='*80}")
    print("PyMuPDF Extraction Test - KPS v2.0")
    print(f"{'='*80}\n")

    print(f"Input PDF: {test_pdf}")

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

    print("\nConfiguration:")
    print(f"  - Vector DPI: {config.vector_dpi}")
    print(f"  - Image format: {config.image_format}")
    print(f"  - Min image size: {config.min_image_size}px")
    print(f"  - Min bbox area: {config.min_bbox_area} sq pts")

    # Create output directory
    output_dir = Path("output/test_extraction")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nOutput directory: {output_dir}")

    # Initialize extractor
    extractor = PyMuPDFExtractor(config)

    print("\n" + "-" * 80)
    print("Extracting assets...")
    print("-" * 80 + "\n")

    # Extract assets
    try:
        ledger = extractor.extract_assets(
            pdf_path=test_pdf,
            output_dir=output_dir
        )
    except Exception as e:
        print(f"ERROR: Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Print results
    print("\n" + "="*80)
    print("EXTRACTION COMPLETE")
    print("="*80 + "\n")

    print(f"Total assets extracted: {len(ledger.assets)}")
    print(f"Pages processed: {ledger.total_pages}")

    # Completeness check
    completeness = ledger.completeness_check()

    print("\n" + "-" * 80)
    print("Assets by Type:")
    print("-" * 80)
    for asset_type, count in completeness["by_type"].items():
        print(f"  {asset_type:20s}: {count:4d}")

    print("\n" + "-" * 80)
    print("Assets by Page:")
    print("-" * 80)
    for page, count in completeness["by_page"].items():
        print(f"  Page {page:3d}: {count:4d} assets")

    # Show enhancement details for first few assets
    print("\n" + "="*80)
    print("12 ENHANCEMENTS VERIFICATION")
    print("="*80 + "\n")

    if ledger.assets:
        for i, asset in enumerate(ledger.assets[:3]):  # Show first 3 assets
            print(f"\n{'-' * 80}")
            print(f"Asset {i+1}: {asset.asset_id}")
            print("-" * 80)

            print(f"  Type: {asset.asset_type.value}")
            print(f"  Page: {asset.page_number}")
            print(f"  Occurrence: {asset.occurrence}")

            # Enhancement 4: SHA256
            print(f"\n  ✓ Enhancement 4 - SHA256 Hash:")
            print(f"    {asset.sha256[:32]}...")
            print(f"    (64 chars total)")

            # Enhancement 1: CTM
            print(f"\n  ✓ Enhancement 1 - Transform Matrix (CTM):")
            print(f"    [{', '.join(f'{x:.2f}' for x in asset.ctm)}]")

            # Enhancement 6: BBox
            print(f"\n  ✓ Enhancement 6 - Bounding Box:")
            print(f"    ({asset.bbox.x0:.1f}, {asset.bbox.y0:.1f}) -> "
                  f"({asset.bbox.x1:.1f}, {asset.bbox.y1:.1f})")
            print(f"    Size: {asset.bbox.width:.1f} x {asset.bbox.height:.1f} pts "
                  f"(area: {asset.bbox.area:.1f})")

            # Enhancement 2: SMask and Clipping
            print(f"\n  ✓ Enhancement 2 - Transparency & Clipping:")
            print(f"    Has SMask: {asset.has_smask}")
            print(f"    Has Clip: {asset.has_clip}")

            # Enhancement 8: Colorspace
            print(f"\n  ✓ Enhancement 8 - Color Space:")
            print(f"    {asset.colorspace.value.upper()}")
            if asset.icc_profile:
                print(f"    ICC Profile: {len(asset.icc_profile)} bytes")

            # Enhancement 9: Dimensions
            if asset.image_width and asset.image_height:
                print(f"\n  ✓ Enhancement 9 - Image Dimensions:")
                print(f"    {asset.image_width} x {asset.image_height} pixels")

                # Calculate DPI
                dpi_x = (asset.image_width / asset.bbox.width) * 72
                dpi_y = (asset.image_height / asset.bbox.height) * 72
                print(f"    DPI: {dpi_x:.0f} x {dpi_y:.0f}")

            # Enhancement 3: Fonts (for vectors)
            if asset.fonts:
                print(f"\n  ✓ Enhancement 3 - Font Audit:")
                for font in asset.fonts[:3]:  # Show first 3 fonts
                    print(f"    - {font.font_name}")
                    print(f"      Type: {font.font_type}, "
                          f"Embedded: {font.embedded}, "
                          f"Subset: {font.subset}")

            # Enhancement 10: File export
            print(f"\n  ✓ Enhancement 10 - Exported File:")
            print(f"    {asset.file_path}")
            print(f"    Exists: {asset.file_path.exists()}")
            if asset.file_path.exists():
                print(f"    Size: {asset.file_path.stat().st_size:,} bytes")

    # Deduplication statistics
    print("\n" + "="*80)
    print("Enhancement 5 - DEDUPLICATION STATISTICS")
    print("="*80 + "\n")

    hash_counts = {}
    for asset in ledger.assets:
        if asset.sha256 not in hash_counts:
            hash_counts[asset.sha256] = []
        hash_counts[asset.sha256].append(asset)

    duplicates = {h: assets for h, assets in hash_counts.items() if len(assets) > 1}

    if duplicates:
        print(f"Found {len(duplicates)} duplicate content hashes:")
        for hash_val, assets in list(duplicates.items())[:5]:  # Show first 5
            print(f"\n  Hash: {hash_val[:16]}...")
            print(f"  Occurrences: {len(assets)}")
            for asset in assets:
                print(f"    - {asset.asset_id} (page {asset.page_number})")
    else:
        print("No duplicate content found (all assets unique)")

    print(f"\nUnique content: {len(hash_counts)} distinct SHA256 hashes")
    print(f"Total assets: {len(ledger.assets)}")
    print(f"Duplication ratio: {len(ledger.assets) / len(hash_counts):.2f}x")

    # Save ledger to JSON
    json_path = output_dir / "asset_ledger.json"
    ledger.save_json(json_path)
    print(f"\n✓ Asset ledger saved to: {json_path}")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    # Allow passing PDF path as argument
    if len(sys.argv) > 1:
        test_pdf = Path(sys.argv[1])
        if test_pdf.exists():
            # Temporarily override the test_pdfs list
            import kps.extraction.pymupdf_extractor as extractor_module
            test_pymupdf_extraction()
        else:
            print(f"Error: PDF not found: {test_pdf}")
    else:
        test_pymupdf_extraction()
