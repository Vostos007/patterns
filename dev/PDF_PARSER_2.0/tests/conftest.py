"""Pytest fixtures for KPS v2.0 tests (anchoring, extraction, translation)."""

import pytest
from pathlib import Path
from kps.core.bbox import BBox
from kps.core.document import (
    KPSDocument,
    DocumentMetadata,
    Section,
    SectionType,
    ContentBlock,
    BlockType,
)
from kps.core.assets import Asset, AssetLedger, AssetType, ColorSpace


# ============================================================================
# PDF TEST FILE FIXTURES (Day 3 - Extraction Tests)
# ============================================================================
# Note: These fixtures return Path objects to test PDF files.
# Actual test PDFs should be created in tests/fixtures/ directory.
# For CI/CD, minimal PDFs can be generated programmatically or committed.


@pytest.fixture
def simple_pdf_path(tmp_path) -> Path:
    """
    Path to simple single-page test PDF.

    Contains:
    - 1 page
    - Basic text blocks
    - 1-2 images
    - Simple layout
    """
    # TODO: Create actual test PDF or use existing sample
    pdf_path = Path(__file__).parent / "fixtures" / "simple.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def multi_page_pdf_path(tmp_path) -> Path:
    """
    Path to multi-page test PDF (3+ pages).

    Contains:
    - 3+ pages
    - Text spanning pages
    - Images on multiple pages
    """
    pdf_path = Path(__file__).parent / "fixtures" / "multi_page.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def russian_pattern_pdf_path(tmp_path) -> Path:
    """
    Path to Russian knitting pattern PDF.

    Contains:
    - Russian section headers (Материалы, Техники, etc.)
    - Cyrillic text
    - Russian knitting terminology
    """
    pdf_path = Path(__file__).parent / "fixtures" / "russian_pattern.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def sample_russian_pattern_pdf(russian_pattern_pdf_path) -> Path:
    """Alias for russian_pattern_pdf_path for integration tests."""
    return russian_pattern_pdf_path


@pytest.fixture
def hierarchical_pdf_path(tmp_path) -> Path:
    """
    Path to PDF with heading hierarchy (h1, h2, h3).

    Contains:
    - Multiple heading levels
    - Nested sections
    - Clear hierarchy
    """
    pdf_path = Path(__file__).parent / "fixtures" / "hierarchical.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def two_column_pdf_path(tmp_path) -> Path:
    """
    Path to PDF with 2-column layout.

    Contains:
    - 2 columns per page
    - Text in both columns
    - Images in columns
    """
    pdf_path = Path(__file__).parent / "fixtures" / "two_column.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def pdf_with_images_path(tmp_path) -> Path:
    """
    Path to PDF with multiple images.

    Contains:
    - 5+ images
    - Various formats (JPEG, PNG)
    - Different sizes
    """
    pdf_path = Path(__file__).parent / "fixtures" / "with_images.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def pdf_with_rotated_images_path(tmp_path) -> Path:
    """
    Path to PDF with rotated/transformed images.

    Contains:
    - Images with rotation
    - Non-identity CTM
    """
    pdf_path = Path(__file__).parent / "fixtures" / "rotated_images.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def pdf_with_transparency_path(tmp_path) -> Path:
    """
    Path to PDF with transparent images (SMask).

    Contains:
    - PNG images with transparency
    - Images with soft masks
    """
    pdf_path = Path(__file__).parent / "fixtures" / "transparency.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def pdf_with_duplicate_images_path(tmp_path) -> Path:
    """
    Path to PDF with duplicate images (same content, different positions).

    Contains:
    - Same image appearing 2+ times
    - Different pages or positions
    - Tests multi-occurrence tracking
    """
    pdf_path = Path(__file__).parent / "fixtures" / "duplicate_images.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def pdf_with_vector_graphics_path(tmp_path) -> Path:
    """
    Path to PDF with vector graphics (charts, diagrams).

    Contains:
    - Vector drawings
    - Charts/diagrams
    - No bitmap images
    """
    pdf_path = Path(__file__).parent / "fixtures" / "vector_graphics.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def pdf_with_text_graphics_path(tmp_path) -> Path:
    """
    Path to PDF with vector graphics containing text.

    Contains:
    - Vector graphics with embedded fonts
    - Text in diagrams
    - Font audit needed
    """
    pdf_path = Path(__file__).parent / "fixtures" / "text_graphics.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def pdf_with_icc_images_path(tmp_path) -> Path:
    """
    Path to PDF with ICC color profiles.

    Contains:
    - Images with ICC profiles
    - CMYK images
    """
    pdf_path = Path(__file__).parent / "fixtures" / "icc_images.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def pdf_with_mixed_content_path(tmp_path) -> Path:
    """
    Path to PDF with mixed content types.

    Contains:
    - Text
    - Images
    - Tables
    - Vectors
    """
    pdf_path = Path(__file__).parent / "fixtures" / "mixed_content.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def pdf_with_tables_path(tmp_path) -> Path:
    """
    Path to PDF with tables.

    Contains:
    - 2+ tables
    - Table structure
    """
    pdf_path = Path(__file__).parent / "fixtures" / "with_tables.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def russian_text_pdf_path(tmp_path) -> Path:
    """Path to PDF with Russian text (encoding test)."""
    pdf_path = Path(__file__).parent / "fixtures" / "russian_text.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def ten_page_pdf_path(tmp_path) -> Path:
    """
    Path to 10-page test PDF (performance tests).

    Contains:
    - 10 pages
    - Realistic content density
    - 20+ assets
    """
    pdf_path = Path(__file__).parent / "fixtures" / "ten_pages.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def large_pdf_with_many_assets_path(tmp_path) -> Path:
    """
    Path to large PDF with many assets (50+).

    For performance testing.
    """
    pdf_path = Path(__file__).parent / "fixtures" / "large_many_assets.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


# Error handling test PDFs


@pytest.fixture
def invalid_pdf_path(tmp_path) -> Path:
    """Path to invalid PDF file."""
    invalid_path = tmp_path / "invalid.pdf"
    invalid_path.write_bytes(b"Not a PDF")
    return invalid_path


@pytest.fixture
def empty_pdf_path(tmp_path) -> Path:
    """Path to empty PDF (no content)."""
    pdf_path = Path(__file__).parent / "fixtures" / "empty.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def corrupted_pdf_path(tmp_path) -> Path:
    """Path to corrupted PDF."""
    corrupted_path = tmp_path / "corrupted.pdf"
    # Create a minimal broken PDF
    corrupted_path.write_bytes(b"%PDF-1.4\nBroken content")
    return corrupted_path


@pytest.fixture
def pdf_with_corrupted_image_path(tmp_path) -> Path:
    """Path to PDF with corrupted image XObject."""
    pdf_path = Path(__file__).parent / "fixtures" / "corrupted_image.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def pdf_with_missing_resources_path(tmp_path) -> Path:
    """Path to PDF with missing resource references."""
    pdf_path = Path(__file__).parent / "fixtures" / "missing_resources.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


@pytest.fixture
def partially_corrupted_pdf_path(tmp_path) -> Path:
    """Path to partially corrupted PDF (some pages valid)."""
    pdf_path = Path(__file__).parent / "fixtures" / "partially_corrupted.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found: {pdf_path}")
    return pdf_path


# ============================================================================
# EXISTING FIXTURES (Day 2 - Anchoring)
# ============================================================================


@pytest.fixture
def sample_bbox() -> BBox:
    """Create a sample bounding box."""
    return BBox(x0=100, y0=200, x1=300, y1=400)


@pytest.fixture
def sample_column_bounds() -> BBox:
    """Create sample column bounds."""
    return BBox(x0=50, y0=100, x1=250, y1=700)


@pytest.fixture
def two_column_layout_blocks() -> list[ContentBlock]:
    """
    Create blocks for a two-column layout with 30pt gap.

    Left column: x=50-250 (width=200)
    Gap: 30pt
    Right column: x=280-480 (width=200)
    """
    blocks = [
        # Left column blocks
        ContentBlock(
            block_id="p.materials.001",
            block_type=BlockType.PARAGRAPH,
            content="Left column paragraph one",
            bbox=BBox(50, 100, 250, 150),
            page_number=0,
            reading_order=0,
        ),
        ContentBlock(
            block_id="p.materials.002",
            block_type=BlockType.PARAGRAPH,
            content="Left column paragraph two",
            bbox=BBox(50, 160, 250, 210),
            page_number=0,
            reading_order=1,
        ),
        ContentBlock(
            block_id="h2.techniques.001",
            block_type=BlockType.HEADING,
            content="Left column heading",
            bbox=BBox(50, 220, 250, 240),
            page_number=0,
            reading_order=2,
        ),
        # Right column blocks
        ContentBlock(
            block_id="p.instructions.001",
            block_type=BlockType.PARAGRAPH,
            content="Right column paragraph one",
            bbox=BBox(280, 100, 480, 150),
            page_number=0,
            reading_order=3,
        ),
        ContentBlock(
            block_id="p.instructions.002",
            block_type=BlockType.PARAGRAPH,
            content="Right column paragraph two",
            bbox=BBox(280, 160, 480, 210),
            page_number=0,
            reading_order=4,
        ),
        ContentBlock(
            block_id="tbl.sizes.001",
            block_type=BlockType.TABLE,
            content="Right column table",
            bbox=BBox(280, 220, 480, 320),
            page_number=0,
            reading_order=5,
        ),
    ]
    return blocks


@pytest.fixture
def three_column_layout_blocks() -> list[ContentBlock]:
    """
    Create blocks for a three-column layout.

    Left: x=50-200 (width=150)
    Middle: x=220-370 (width=150)
    Right: x=390-540 (width=150)
    Gap: 20pt between columns
    """
    blocks = [
        # Left column
        ContentBlock(
            block_id="p.col1.001",
            block_type=BlockType.PARAGRAPH,
            content="Column 1 text",
            bbox=BBox(50, 100, 200, 150),
            page_number=0,
            reading_order=0,
        ),
        # Middle column
        ContentBlock(
            block_id="p.col2.001",
            block_type=BlockType.PARAGRAPH,
            content="Column 2 text",
            bbox=BBox(220, 100, 370, 150),
            page_number=0,
            reading_order=1,
        ),
        # Right column
        ContentBlock(
            block_id="p.col3.001",
            block_type=BlockType.PARAGRAPH,
            content="Column 3 text",
            bbox=BBox(390, 100, 540, 150),
            page_number=0,
            reading_order=2,
        ),
    ]
    return blocks


@pytest.fixture
def single_column_layout_blocks() -> list[ContentBlock]:
    """Create blocks for a single-column layout."""
    blocks = [
        ContentBlock(
            block_id="p.intro.001",
            block_type=BlockType.PARAGRAPH,
            content="Single column paragraph 1",
            bbox=BBox(50, 100, 500, 150),
            page_number=0,
            reading_order=0,
        ),
        ContentBlock(
            block_id="p.intro.002",
            block_type=BlockType.PARAGRAPH,
            content="Single column paragraph 2",
            bbox=BBox(50, 160, 500, 210),
            page_number=0,
            reading_order=1,
        ),
        ContentBlock(
            block_id="h1.title.001",
            block_type=BlockType.HEADING,
            content="Single column heading",
            bbox=BBox(50, 220, 500, 250),
            page_number=0,
            reading_order=2,
        ),
    ]
    return blocks


@pytest.fixture
def sample_asset_left_column() -> Asset:
    """Create a sample asset in the left column."""
    return Asset(
        asset_id="img-abc123-p0-occ1",
        asset_type=AssetType.IMAGE,
        sha256="a" * 64,
        page_number=0,
        bbox=BBox(80, 250, 220, 350),  # In left column (x: 50-250)
        ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        file_path=Path("/tmp/img-abc123.png"),
        occurrence=1,
        anchor_to="",  # To be set by anchoring
        image_width=800,
        image_height=600,
    )


@pytest.fixture
def sample_asset_right_column() -> Asset:
    """Create a sample asset in the right column."""
    return Asset(
        asset_id="img-def456-p0-occ1",
        asset_type=AssetType.IMAGE,
        sha256="b" * 64,
        page_number=0,
        bbox=BBox(310, 330, 450, 430),  # In right column (x: 280-480)
        ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        file_path=Path("/tmp/img-def456.png"),
        occurrence=1,
        anchor_to="",
        image_width=800,
        image_height=600,
    )


@pytest.fixture
def sample_asset_between_blocks() -> Asset:
    """Create an asset positioned between two blocks."""
    return Asset(
        asset_id="img-ghi789-p0-occ1",
        asset_type=AssetType.IMAGE,
        sha256="c" * 64,
        page_number=0,
        bbox=BBox(80, 155, 220, 205),  # Between blocks at y=150 and y=210
        ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        file_path=Path("/tmp/img-ghi789.png"),
        occurrence=1,
        anchor_to="",
        image_width=600,
        image_height=400,
    )


@pytest.fixture
def sample_asset_column_boundary() -> Asset:
    """Create an asset at column boundary (edge case)."""
    return Asset(
        asset_id="img-jkl012-p0-occ1",
        asset_type=AssetType.IMAGE,
        sha256="d" * 64,
        page_number=0,
        bbox=BBox(240, 100, 290, 150),  # Spanning column gap (250-280)
        ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        file_path=Path("/tmp/img-jkl012.png"),
        occurrence=1,
        anchor_to="",
        image_width=400,
        image_height=400,
    )


@pytest.fixture
def sample_kps_document(two_column_layout_blocks: list[ContentBlock]) -> KPSDocument:
    """Create a sample KPS document with sections."""
    metadata = DocumentMetadata(
        title="Test Pattern",
        author="Test Author",
        version="2.0.0",
        language="ru",
    )

    # Split blocks into sections based on block_id prefixes
    materials_section = Section(
        section_type=SectionType.MATERIALS,
        title="Materials",
        blocks=[b for b in two_column_layout_blocks if "materials" in b.block_id],
    )

    techniques_section = Section(
        section_type=SectionType.TECHNIQUES,
        title="Techniques",
        blocks=[b for b in two_column_layout_blocks if "techniques" in b.block_id],
    )

    instructions_section = Section(
        section_type=SectionType.INSTRUCTIONS,
        title="Instructions",
        blocks=[b for b in two_column_layout_blocks if "instructions" in b.block_id or "sizes" in b.block_id],
    )

    return KPSDocument(
        slug="test-pattern",
        metadata=metadata,
        sections=[materials_section, techniques_section, instructions_section],
    )


@pytest.fixture
def sample_asset_ledger(
    sample_asset_left_column: Asset,
    sample_asset_right_column: Asset,
) -> AssetLedger:
    """Create a sample asset ledger."""
    return AssetLedger(
        assets=[sample_asset_left_column, sample_asset_right_column],
        source_pdf=Path("/tmp/test.pdf"),
        total_pages=1,
    )


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory."""
    output_dir = tmp_path / "kps_test_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


# Constants for anchoring algorithm
@pytest.fixture
def dbscan_params() -> dict:
    """DBSCAN parameters for column detection."""
    return {
        "epsilon": 30.0,  # Maximum gap between columns (pt)
        "min_points": 3,   # Minimum blocks per column
    }


# Marker pattern constants
ASSET_MARKER_PATTERN = r"\[\[([a-z]+-[a-f0-9]{8}-p\d+-occ\d+)\]\]"


@pytest.fixture
def marker_pattern() -> str:
    """Asset marker regex pattern."""
    return ASSET_MARKER_PATTERN


# ============================================================================
# INDESIGN FIXTURES (Day 4 - InDesign Integration Tests)
# ============================================================================


@pytest.fixture
def sample_idml_path() -> Path:
    """
    Path to sample IDML file.

    Contains:
    - 2 stories with test content
    - Paragraph blocks for anchoring
    - Valid IDML structure
    """
    idml_path = Path(__file__).parent / "fixtures" / "sample.idml"
    if not idml_path.exists():
        pytest.skip(f"Test IDML not found: {idml_path}")
    return idml_path


@pytest.fixture
def indesign_manifest_path() -> Path:
    """
    Path to InDesign manifest JSON.

    Contains:
    - 4 assets (images, vectors, tables)
    - Anchor references
    - Normalized coordinates
    - Column definitions
    """
    manifest_path = Path(__file__).parent / "fixtures" / "manifest_indesign.json"
    if not manifest_path.exists():
        pytest.skip(f"Test manifest not found: {manifest_path}")
    return manifest_path


@pytest.fixture
def sample_indesign_metadata():
    """Create sample PlacedObjectMetadata for testing."""
    from tests.unit.test_indesign_metadata import PlacedObjectMetadata, NormalizedBBox

    return PlacedObjectMetadata(
        asset_id="img-test001-p0-occ1",
        column_id=0,
        normalized_bbox=NormalizedBBox(x=0.1, y=0.2, width=0.5, height=0.3),
        ctm=(1.0, 0.0, 0.0, 1.0, 100.0, 200.0),
        anchor_to="paragraph.materials.001",
        asset_type="image",
        page_number=0,
        occurrence=1
    )


@pytest.fixture
def sample_column_definition():
    """Create sample Column definition."""
    from tests.unit.test_placement import Column

    return Column(
        column_id=0,
        x_min=50.0,
        x_max=300.0,
        y_min=100.0,
        y_max=700.0
    )


@pytest.fixture
def sample_pdf_export_settings():
    """Create sample PDF export settings."""
    from tests.unit.test_pdf_export import PDFExportSettings, PDFStandard, ColorSpace

    return PDFExportSettings(
        pdf_standard=PDFStandard.PDF_X_4_2010,
        color_space=ColorSpace.CMYK,
        jpeg_quality=10,
        bleed_top=3.0,
        bleed_bottom=3.0,
        bleed_left=3.0,
        bleed_right=3.0,
        embed_fonts=True,
        include_icc_profiles=True
    )


@pytest.fixture
def mock_jsx_runner():
    """Create mock JSX runner for tests without InDesign."""
    from unittest.mock import Mock
    from tests.unit.test_jsx_runner import JSXRunner

    runner = JSXRunner()

    # Mock methods
    runner.execute_script = Mock(return_value={"success": True})
    runner.label_placed_objects = Mock(return_value={
        "success": True,
        "labeled_count": 3,
        "failed_count": 0
    })
    runner.extract_labels = Mock(return_value=[])
    runner.export_pdf = Mock(return_value={
        "success": True,
        "output_path": "/tmp/output.pdf",
        "file_size": 1024000,
        "pages": 10
    })

    return runner


@pytest.fixture
def a4_page_dimensions():
    """A4 page dimensions in points."""
    return {
        "width": 595.28,   # 210mm
        "height": 841.89,  # 297mm
        "margin_top": 50.0,
        "margin_bottom": 50.0,
        "margin_left": 50.0,
        "margin_right": 50.0
    }


# InDesign test markers
def pytest_configure(config):
    """Add custom markers for InDesign tests."""
    config.addinivalue_line(
        "markers", "indesign: mark test as requiring InDesign (skip if not available)"
    )
    config.addinivalue_line(
        "markers", "jsx: mark test as requiring JSX execution"
    )
    config.addinivalue_line(
        "markers", "ghostscript: mark test as requiring Ghostscript for PDF validation"
    )
