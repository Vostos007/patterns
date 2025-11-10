#!/usr/bin/env python3
"""
Demonstration of marker injection functionality.

Shows how [[asset_id]] markers are injected into different block types.
"""

from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kps.anchoring.markers import inject_markers, count_markers
from kps.core.assets import Asset, AssetLedger, AssetType
from kps.core.bbox import BBox
from kps.core.document import (
    BlockType,
    ContentBlock,
    DocumentMetadata,
    KPSDocument,
    Section,
    SectionType,
)


def print_separator():
    """Print visual separator."""
    print("\n" + "=" * 80 + "\n")


def demo_paragraph_injection():
    """Demonstrate marker injection at start of paragraph."""
    print("DEMO 1: Paragraph Block (marker at start)")
    print("-" * 80)

    block = ContentBlock(
        block_id="p.materials.001",
        block_type=BlockType.PARAGRAPH,
        content="You will need 200g of DK weight yarn in your favorite color. The sample shown uses a soft merino blend.",
        bbox=BBox(50, 100, 550, 150),
        page_number=0,
    )

    print(f"Original content:\n  {block.content}\n")

    # Create mock document
    metadata = DocumentMetadata(title="Test Pattern", language="ru")
    section = Section(
        section_type=SectionType.MATERIALS, title="Materials", blocks=[block]
    )
    document = KPSDocument(slug="test-pattern", metadata=metadata, sections=[section])

    # Create asset
    asset = Asset(
        asset_id="img-yarn-sample-p0-occ1",
        asset_type=AssetType.IMAGE,
        sha256="a" * 64,
        page_number=0,
        bbox=BBox(50, 50, 550, 90),
        ctm=(1, 0, 0, 1, 0, 0),
        file_path=Path("/tmp/yarn-sample.png"),
        occurrence=1,
        anchor_to="p.materials.001",
        image_width=500,
        image_height=100,
    )

    ledger = AssetLedger(
        assets=[asset], source_pdf=Path("/tmp/test.pdf"), total_pages=1
    )

    # Inject markers
    modified_doc = inject_markers(document, ledger)
    modified_block = modified_doc.sections[0].blocks[0]

    print(f"After injection:\n  {modified_block.content}\n")
    print(f"Result: Marker injected at START of paragraph")


def demo_heading_injection():
    """Demonstrate marker injection after heading text."""
    print("\nDEMO 2: Heading Block (marker after heading)")
    print("-" * 80)

    block = ContentBlock(
        block_id="h2.techniques.001",
        block_type=BlockType.HEADING,
        content="Essential Knitting Techniques",
    )

    print(f"Original content:\n  {block.content}\n")

    metadata = DocumentMetadata(title="Test Pattern", language="ru")
    section = Section(
        section_type=SectionType.TECHNIQUES, title="Techniques", blocks=[block]
    )
    document = KPSDocument(slug="test-pattern", metadata=metadata, sections=[section])

    asset = Asset(
        asset_id="vec-technique-diagram-p1-occ1",
        asset_type=AssetType.VECTOR_PDF,
        sha256="b" * 64,
        page_number=1,
        bbox=BBox(50, 50, 550, 90),
        ctm=(1, 0, 0, 1, 0, 0),
        file_path=Path("/tmp/technique-diagram.pdf"),
        occurrence=1,
        anchor_to="h2.techniques.001",
    )

    ledger = AssetLedger(
        assets=[asset], source_pdf=Path("/tmp/test.pdf"), total_pages=2
    )

    modified_doc = inject_markers(document, ledger)
    modified_block = modified_doc.sections[0].blocks[0]

    print(f"After injection:\n  {modified_block.content}\n")
    print(f"Result: Marker injected AFTER heading text")


def demo_multiple_assets():
    """Demonstrate multiple assets ordered by y-coordinate."""
    print("\nDEMO 3: Multiple Assets (ordered top-to-bottom)")
    print("-" * 80)

    block = ContentBlock(
        block_id="p.construction.001",
        block_type=BlockType.PARAGRAPH,
        content="Follow the construction diagram shown above. Begin with the back panel, then work the front panels.",
        bbox=BBox(50, 200, 550, 300),
        page_number=2,
    )

    print(f"Original content:\n  {block.content}\n")

    metadata = DocumentMetadata(title="Test Pattern", language="ru")
    section = Section(
        section_type=SectionType.CONSTRUCTION, title="Construction", blocks=[block]
    )
    document = KPSDocument(slug="test-pattern", metadata=metadata, sections=[section])

    # Asset 1: Lower on page (higher y0 value)
    asset1 = Asset(
        asset_id="img-front-panel-p2-occ1",
        asset_type=AssetType.IMAGE,
        sha256="c" * 64,
        page_number=2,
        bbox=BBox(50, 150, 550, 190),
        ctm=(1, 0, 0, 1, 0, 0),
        file_path=Path("/tmp/front-panel.png"),
        occurrence=1,
        anchor_to="p.construction.001",
        image_width=500,
        image_height=100,
    )

    # Asset 2: Higher on page (lower y0 value)
    asset2 = Asset(
        asset_id="img-back-panel-p2-occ1",
        asset_type=AssetType.IMAGE,
        sha256="d" * 64,
        page_number=2,
        bbox=BBox(50, 80, 550, 140),
        ctm=(1, 0, 0, 1, 0, 0),
        file_path=Path("/tmp/back-panel.png"),
        occurrence=1,
        anchor_to="p.construction.001",
        image_width=500,
        image_height=150,
    )

    ledger = AssetLedger(
        assets=[asset1, asset2], source_pdf=Path("/tmp/test.pdf"), total_pages=3
    )

    modified_doc = inject_markers(document, ledger)
    modified_block = modified_doc.sections[0].blocks[0]

    print(f"After injection:\n{modified_block.content}\n")
    print(f"Result: Assets ordered by y-coordinate (top to bottom)")
    print(f"  - First marker: img-back-panel (y0=80, higher on page)")
    print(f"  - Second marker: img-front-panel (y0=150, lower on page)")


def demo_table_injection():
    """Demonstrate marker injection at start of table."""
    print("\nDEMO 4: Table Block (marker at start)")
    print("-" * 80)

    block = ContentBlock(
        block_id="tbl.sizes.001",
        block_type=BlockType.TABLE,
        content="Size | Chest (cm) | Length (cm) | Sleeve (cm)\nS    | 90         | 60          | 45\nM    | 100        | 65          | 47\nL    | 110        | 70          | 50",
    )

    print(f"Original content:\n{block.content}\n")

    metadata = DocumentMetadata(title="Test Pattern", language="ru")
    section = Section(
        section_type=SectionType.SIZES, title="Sizes", blocks=[block]
    )
    document = KPSDocument(slug="test-pattern", metadata=metadata, sections=[section])

    asset = Asset(
        asset_id="tbl-snap-sizing-p3-occ1",
        asset_type=AssetType.TABLE_SNAP,
        sha256="e" * 64,
        page_number=3,
        bbox=BBox(50, 100, 550, 200),
        ctm=(1, 0, 0, 1, 0, 0),
        file_path=Path("/tmp/sizing-table.png"),
        occurrence=1,
        anchor_to="tbl.sizes.001",
    )

    ledger = AssetLedger(
        assets=[asset], source_pdf=Path("/tmp/test.pdf"), total_pages=4
    )

    modified_doc = inject_markers(document, ledger)
    modified_block = modified_doc.sections[0].blocks[0]

    print(f"After injection:\n{modified_block.content}\n")
    print(f"Result: Marker injected at START of table")


def demo_statistics():
    """Demonstrate marker counting and statistics."""
    print("\nDEMO 5: Marker Statistics")
    print("-" * 80)

    metadata = DocumentMetadata(title="Test Pattern", language="ru")

    # Create multiple blocks with markers
    block1 = ContentBlock(
        block_id="p.materials.001",
        block_type=BlockType.PARAGRAPH,
        content="Materials paragraph.",
        bbox=BBox(50, 100, 550, 150),
        page_number=0,
    )

    block2 = ContentBlock(
        block_id="p.materials.002",
        block_type=BlockType.PARAGRAPH,
        content="More materials.",
        bbox=BBox(50, 200, 550, 250),
        page_number=0,
    )

    block3 = ContentBlock(
        block_id="p.instructions.001",
        block_type=BlockType.PARAGRAPH,
        content="Instructions paragraph.",
        bbox=BBox(50, 100, 550, 150),
        page_number=1,
    )

    section1 = Section(
        section_type=SectionType.MATERIALS,
        title="Materials",
        blocks=[block1, block2],
    )

    section2 = Section(
        section_type=SectionType.INSTRUCTIONS,
        title="Instructions",
        blocks=[block3],
    )

    document = KPSDocument(
        slug="test-pattern", metadata=metadata, sections=[section1, section2]
    )

    # Create assets
    assets = [
        Asset(
            asset_id=f"img-asset{i}-p0-occ1",
            asset_type=AssetType.IMAGE,
            sha256=f"{i}" * 64,
            page_number=0,
            bbox=BBox(50, 50 + i * 50, 550, 90 + i * 50),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path(f"/tmp/asset{i}.png"),
            occurrence=1,
            anchor_to=f"p.materials.00{i+1}",
            image_width=500,
            image_height=100,
        )
        for i in range(2)
    ]

    assets.append(
        Asset(
            asset_id="vec-diagram-p1-occ1",
            asset_type=AssetType.VECTOR_PDF,
            sha256="f" * 64,
            page_number=1,
            bbox=BBox(50, 50, 550, 90),
            ctm=(1, 0, 0, 1, 0, 0),
            file_path=Path("/tmp/diagram.pdf"),
            occurrence=1,
            anchor_to="p.instructions.001",
        )
    )

    ledger = AssetLedger(
        assets=assets, source_pdf=Path("/tmp/test.pdf"), total_pages=2
    )

    # Inject markers
    modified_doc = inject_markers(document, ledger)

    # Get statistics
    stats = count_markers(modified_doc)

    print(f"Total markers in document: {stats['total_markers']}")
    print(f"\nMarkers by section:")
    for section_type, count in stats["markers_by_section"].items():
        print(f"  {section_type}: {count} markers")

    print(f"\nMarkers by block:")
    for block_id, marker_ids in stats["markers_by_block"].items():
        print(f"  {block_id}:")
        for marker_id in marker_ids:
            print(f"    - [[{marker_id}]]")


def demo_validation():
    """Demonstrate validation features."""
    print("\nDEMO 6: Validation Features")
    print("-" * 80)

    print("Validation ensures:")
    print("  1. Every anchored asset has exactly ONE marker in document")
    print("  2. No duplicate markers across blocks")
    print("  3. All markers match the pattern [[asset_id]]")
    print("  4. No orphan markers (markers without anchored assets)")
    print("\nThese validations run automatically in inject_markers().")
    print("If validation fails, MarkerInjectionError is raised.")


def main():
    """Run all demonstrations."""
    print_separator()
    print("MARKER INJECTION DEMONSTRATION")
    print("KPS v2.0 - Asset Marker Injection System")
    print_separator()

    demo_paragraph_injection()
    print_separator()

    demo_heading_injection()
    print_separator()

    demo_multiple_assets()
    print_separator()

    demo_table_injection()
    print_separator()

    demo_statistics()
    print_separator()

    demo_validation()
    print_separator()

    print("DEMONSTRATION COMPLETE")
    print_separator()


if __name__ == "__main__":
    main()
