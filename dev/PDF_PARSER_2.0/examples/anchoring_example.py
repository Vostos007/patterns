#!/usr/bin/env python3
"""
Example demonstrating the asset-to-block anchoring algorithm for KPS v2.0.

This example shows:
1. Creating a simple document with text blocks
2. Creating assets (images) on the same page
3. Running the anchoring algorithm
4. Computing normalized coordinates
5. Validating the results
"""

from pathlib import Path

from kps.core.assets import Asset, AssetLedger, AssetType
from kps.core.document import (
    KPSDocument,
    DocumentMetadata,
    Section,
    SectionType,
    ContentBlock,
    BlockType,
)
from kps.core.bbox import BBox
from kps.anchoring import (
    anchor_assets_to_blocks,
    compute_normalized_bbox,
    find_nearest_block,
)


def create_sample_document() -> KPSDocument:
    """Create a sample KPS document with text blocks."""

    # Create text blocks on page 0
    blocks = [
        ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="Materials: 200g of yarn, 4mm needles",
            bbox=BBox(50, 100, 250, 150),
            page_number=0,
            reading_order=0,
        ),
        ContentBlock(
            block_id="p.materials.002",
            block_type=BlockType.PARAGRAPH,
            content="Gauge: 20 sts x 28 rows = 10cm in stockinette",
            bbox=BBox(50, 250, 250, 300),
            page_number=0,
            reading_order=1,
        ),
        ContentBlock(
            block_id="p.materials.003",
            block_type=BlockType.PARAGRAPH,
            content="Pattern instructions begin here...",
            bbox=BBox(50, 400, 250, 450),
            page_number=0,
            reading_order=2,
        ),
    ]

    document = KPSDocument(
        slug="sample-pattern",
        metadata=DocumentMetadata(
            title="Sample Knitting Pattern",
            author="Example Author",
            language="en",
        ),
        sections=[
            Section(
                section_type=SectionType.MATERIALS,
                title="Materials & Gauge",
                blocks=blocks,
            )
        ],
    )

    return document


def create_sample_assets() -> AssetLedger:
    """Create sample assets (images) on the same page."""

    # Create two assets:
    # 1. Image between first and second text blocks
    # 2. Image between second and third text blocks

    assets = [
        Asset(
            asset_id="img-yarn-001",
            asset_type=AssetType.IMAGE,
            sha256="a" * 64,
            page_number=0,
            bbox=BBox(75, 160, 225, 240),  # Between blocks 1 and 2
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/yarn_photo.png"),
            occurrence=1,
            anchor_to="",  # Will be set by anchoring
            image_width=300,
            image_height=200,
        ),
        Asset(
            asset_id="img-gauge-001",
            asset_type=AssetType.IMAGE,
            sha256="b" * 64,
            page_number=0,
            bbox=BBox(75, 310, 225, 390),  # Between blocks 2 and 3
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/gauge_swatch.png"),
            occurrence=1,
            anchor_to="",  # Will be set by anchoring
            image_width=300,
            image_height=200,
        ),
    ]

    ledger = AssetLedger(
        assets=assets,
        source_pdf=Path("/tmp/sample_pattern.pdf"),
        total_pages=1,
    )

    return ledger


def main():
    """Run the anchoring example."""

    print("=== KPS v2.0 Anchoring Algorithm Example ===\n")

    # Step 1: Create sample document
    print("Step 1: Creating sample document with 3 text blocks...")
    document = create_sample_document()
    print(f"  Created document '{document.slug}' with {len(document.sections[0].blocks)} blocks")
    for block in document.sections[0].blocks:
        print(f"    - {block.block_id}: y={block.bbox.y0}-{block.bbox.y1}")
    print()

    # Step 2: Create sample assets
    print("Step 2: Creating sample assets (2 images)...")
    ledger = create_sample_assets()
    print(f"  Created {len(ledger.assets)} assets:")
    for asset in ledger.assets:
        print(f"    - {asset.asset_id}: y={asset.bbox.y0}-{asset.bbox.y1}")
    print()

    # Step 3: Run anchoring algorithm
    print("Step 3: Running anchoring algorithm...")
    anchored_ledger, report = anchor_assets_to_blocks(ledger, document)

    print(f"  Anchoring complete!")
    print(f"  Success rate: {report.success_rate:.1%}")
    print(f"  Anchored assets: {report.anchored_assets}/{report.total_assets}")
    print()

    # Step 4: Display results
    print("Step 4: Anchoring results:")
    for asset in anchored_ledger.assets:
        print(f"  - {asset.asset_id}")
        print(f"      Anchored to: {asset.anchor_to}")

        # Show which block was selected
        block = document.find_block(asset.anchor_to)
        if block:
            print(f"      Block text: {block.content[:50]}...")
    print()

    # Step 5: Compute normalized coordinates
    print("Step 5: Computing normalized coordinates...")
    print("  (Column-relative 0-1 coordinates for geometry preservation)")

    # Detect columns for the page
    from kps.anchoring.columns import detect_columns
    page_blocks = document.get_blocks_on_page(0)
    columns = detect_columns(page_blocks)

    print(f"  Detected {len(columns)} column(s) on page 0")

    if columns:
        column = columns[0]
        print(f"    Column bounds: x={column.x_min}-{column.x_max}, y={column.y_min}-{column.y_max}")
        print()

        for asset in anchored_ledger.assets:
            normalized = compute_normalized_bbox(asset, column)
            print(f"  - {asset.asset_id}:")
            print(f"      Absolute: x={asset.bbox.x0:.1f}, y={asset.bbox.y0:.1f}, "
                  f"w={asset.bbox.width:.1f}, h={asset.bbox.height:.1f}")
            print(f"      Normalized: x={normalized.x:.3f}, y={normalized.y:.3f}, "
                  f"w={normalized.w:.3f}, h={normalized.h:.3f}")
    print()

    # Step 6: Validation summary
    print("Step 6: Validation summary:")
    if report.is_valid():
        print("   All assets successfully anchored")
        print("   Geometry preservation validated")
        print(f"   Pass rate: {report.geometry_pass_rate:.1%}")
    else:
        print("   Validation failed")
        if report.unanchored_assets:
            print(f"    Unanchored: {report.unanchored_assets}")
        if report.warnings:
            print(f"    Warnings: {len(report.warnings)}")
    print()

    print("=== Example Complete ===")


if __name__ == "__main__":
    main()
