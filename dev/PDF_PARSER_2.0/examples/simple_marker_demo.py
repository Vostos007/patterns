#!/usr/bin/env python3
"""
Simple demonstration of marker injection logic (without full dependencies).

Shows the core marker injection strategies for different block types.
"""


def format_marker(asset_id: str) -> str:
    """Format an asset marker with newline."""
    return f"[[{asset_id}]]\n"


def demo_paragraph():
    """Show marker injection at start of paragraph."""
    print("=" * 80)
    print("DEMO 1: PARAGRAPH BLOCK - Inject at START")
    print("=" * 80)

    content_before = "You will need 200g of DK weight yarn. The sample shown uses merino blend."

    marker = format_marker("img-yarn-sample-p0-occ1")
    content_after = marker + content_before

    print("\nOriginal content:")
    print(f'  "{content_before}"')
    print("\nAfter marker injection:")
    print(f'  "{content_after}"')
    print("\nStrategy: Marker placed at position 0 (start of paragraph)")
    print()


def demo_heading():
    """Show marker injection after heading."""
    print("=" * 80)
    print("DEMO 2: HEADING BLOCK - Inject AFTER heading text")
    print("=" * 80)

    content_before = "Essential Knitting Techniques"

    marker = format_marker("vec-technique-diagram-p1-occ1")
    content_after = content_before + "\n" + marker

    print("\nOriginal content:")
    print(f'  "{content_before}"')
    print("\nAfter marker injection:")
    print(f'  "{content_after}"')
    print("\nStrategy: Marker placed after heading with newline separator")
    print()


def demo_multiple_assets():
    """Show multiple assets ordered by y-coordinate."""
    print("=" * 80)
    print("DEMO 3: MULTIPLE ASSETS - Ordered by y-coordinate (top to bottom)")
    print("=" * 80)

    content_before = "Follow the construction diagram. Begin with back panel, then front panels."

    # Assets ordered by y-coordinate (lower y0 = higher on page = first)
    # Asset 1: y0=80 (higher on page)
    # Asset 2: y0=150 (lower on page)
    marker1 = format_marker("img-back-panel-p2-occ1")
    marker2 = format_marker("img-front-panel-p2-occ1")

    content_after = marker1 + marker2 + content_before

    print("\nOriginal content:")
    print(f'  "{content_before}"')
    print("\nAsset positions:")
    print("  - img-back-panel: bbox y0=80 (higher on page)")
    print("  - img-front-panel: bbox y0=150 (lower on page)")
    print("\nAfter marker injection:")
    print(f'  "{content_after}"')
    print("\nStrategy: Assets sorted by y0 coordinate (ascending = top to bottom)")
    print()


def demo_table():
    """Show marker injection at start of table."""
    print("=" * 80)
    print("DEMO 4: TABLE BLOCK - Inject at START")
    print("=" * 80)

    content_before = """Size | Chest (cm) | Length (cm)
S    | 90         | 60
M    | 100        | 65
L    | 110        | 70"""

    marker = format_marker("tbl-snap-sizing-p3-occ1")
    content_after = marker + content_before

    print("\nOriginal content:")
    print(content_before)
    print("\nAfter marker injection:")
    print(content_after)
    print("Strategy: Marker placed at position 0 (before table data)")
    print()


def demo_caption_detection():
    """Show caption block handling."""
    print("=" * 80)
    print("DEMO 5: CAPTION BLOCK - Asset before caption text")
    print("=" * 80)

    content_before = "Figure 1: Back panel construction schematic"

    marker = format_marker("vec-schematic-p4-occ1")
    content_after = marker + content_before

    print("\nOriginal content:")
    print(f'  "{content_before}"')
    print("\nAfter marker injection:")
    print(f'  "{content_after}"')
    print("\nStrategy: Marker placed before caption text (asset first, then caption)")
    print()


def demo_validation():
    """Show validation examples."""
    print("=" * 80)
    print("DEMO 6: VALIDATION FEATURES")
    print("=" * 80)

    print("\nThe inject_markers() function performs comprehensive validation:")
    print()
    print("1. COMPLETENESS CHECK")
    print("   - Every anchored asset MUST have exactly one marker in document")
    print("   - If an asset has anchor_to='p.materials.001', that block must contain [[asset_id]]")
    print()
    print("2. UNIQUENESS CHECK")
    print("   - No duplicate markers across different blocks")
    print("   - Each [[asset_id]] appears exactly once")
    print()
    print("3. FORMAT VALIDATION")
    print("   - All markers match pattern: [[asset_id]]")
    print("   - asset_id format: type-hash-pN-occN")
    print("   - Examples: [[img-abc123-p0-occ1]], [[vec-xyz789-p1-occ2]]")
    print()
    print("4. ORPHAN DETECTION")
    print("   - No markers without corresponding anchored assets")
    print("   - All markers must reference a valid asset in the ledger")
    print()
    print("If any validation fails, MarkerInjectionError is raised with details.")
    print()


def demo_edge_cases():
    """Show edge case handling."""
    print("=" * 80)
    print("DEMO 7: EDGE CASES")
    print("=" * 80)

    print("\n1. EXISTING MARKERS (Deduplication)")
    print("   Original: [[img-abc-p0-occ1]]\\nSome text")
    print("   Asset: img-abc-p0-occ1 anchored to this block")
    print("   Result: No change (marker already exists, skip injection)")

    print("\n2. EMPTY CONTENT BLOCKS")
    print("   Original: '' (empty string)")
    print("   Asset: img-xyz-p1-occ1 anchored to this block")
    print("   Result: [[img-xyz-p1-occ1]]")

    print("\n3. FIGURE BLOCKS (No text content)")
    print("   Original: '' or None")
    print("   Asset: img-diagram-p2-occ1 anchored to this block")
    print("   Result: [[img-diagram-p2-occ1]] (marker replaces content)")

    print("\n4. MULTIPLE RUNS (Idempotency)")
    print("   First run: Injects markers")
    print("   Second run: Detects existing markers, skips re-injection")
    print("   Result: Same output on both runs")
    print()


def demo_example_output():
    """Show complete example with real content."""
    print("=" * 80)
    print("DEMO 8: COMPLETE EXAMPLE")
    print("=" * 80)

    print("\nBefore marker injection:")
    print("-" * 40)
    print("""
MATERIALS

You will need the following materials:
- 200g DK weight yarn
- 4mm needles
- Stitch markers

CONSTRUCTION

Begin by casting on 80 stitches. Work in stockinette
stitch for 20cm. Follow the schematic for details.
""")

    print("\nAfter marker injection:")
    print("-" * 40)
    print("""
MATERIALS

[[img-yarn-close-up-p0-occ1]]
[[img-needles-and-markers-p0-occ2]]
You will need the following materials:
- 200g DK weight yarn
- 4mm needles
- Stitch markers

CONSTRUCTION

[[vec-construction-schematic-p1-occ1]]
Begin by casting on 80 stitches. Work in stockinette
stitch for 20cm. Follow the schematic for details.
""")

    print("\nMarkers placed:")
    print("  - p.materials.001: 2 assets (ordered by y-coordinate)")
    print("  - p.construction.001: 1 asset")
    print()


def main():
    """Run all demonstrations."""
    print("\n")
    print("=" * 80)
    print(" KPS v2.0 - MARKER INJECTION DEMONSTRATION")
    print(" [[asset_id]] Marker Injection Strategies")
    print("=" * 80)
    print()

    demo_paragraph()
    demo_heading()
    demo_multiple_assets()
    demo_table()
    demo_caption_detection()
    demo_validation()
    demo_edge_cases()
    demo_example_output()

    print("=" * 80)
    print(" DEMONSTRATION COMPLETE")
    print("=" * 80)
    print()
    print("Key Takeaways:")
    print("  1. Markers are placed strategically based on block type")
    print("  2. Multiple assets are ordered by y-coordinate (top to bottom)")
    print("  3. Comprehensive validation ensures data integrity")
    print("  4. Deduplication prevents marker re-injection")
    print("  5. Each marker format: [[asset_id]]\\n (on its own line)")
    print()


if __name__ == "__main__":
    main()
