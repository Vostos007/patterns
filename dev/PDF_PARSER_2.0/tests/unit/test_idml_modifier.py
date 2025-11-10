"""Unit tests for IDML Modifier (anchored objects insertion)."""

import pytest
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List


# Mock classes (will be implemented by Agent 3)
@dataclass
class AnchoredObjectSpec:
    """Specification for an anchored object to insert."""
    asset_id: str
    anchor_block_id: str
    position: str  # "inline", "above_line", "custom"
    horizontal_offset: float  # pt
    vertical_offset: float  # pt
    width: float  # pt
    height: float  # pt
    metadata_json: str  # Embedded metadata


@dataclass
class PlacedImageSpec:
    """Specification for a placed image (non-anchored)."""
    asset_id: str
    page_number: int
    x: float
    y: float
    width: float
    height: float
    image_path: Path
    metadata_json: str


class IDMLModifier:
    """Modifies IDML structure to add anchored objects."""

    def __init__(self, doc: 'IDMLDocument'):
        self.doc = doc

    def insert_anchored_object(self, story_id: str, anchor_block_id: str,
                               spec: AnchoredObjectSpec) -> bool:
        """Insert anchored object into story."""
        raise NotImplementedError("To be implemented by Agent 3")

    def insert_placed_image(self, spread_id: str, spec: PlacedImageSpec) -> bool:
        """Insert placed image (non-anchored) on spread."""
        raise NotImplementedError("To be implemented by Agent 3")

    def add_object_label(self, element: ET.Element, label: str) -> None:
        """Add label attribute to XML element."""
        raise NotImplementedError("To be implemented by Agent 3")

    def embed_metadata_in_object(self, element: ET.Element, metadata_json: str) -> None:
        """Embed JSON metadata in object's XML."""
        raise NotImplementedError("To be implemented by Agent 3")

    def validate_modifications(self) -> list[str]:
        """Validate all modifications are valid."""
        raise NotImplementedError("To be implemented by Agent 3")


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def sample_story_xml():
    """Create sample story XML."""
    return ET.fromstring('''
<Story Self="u123">
    <ParagraphStyleRange Self="paragraph.materials.001">
        <CharacterStyleRange>
            <Content>First paragraph.</Content>
        </CharacterStyleRange>
    </ParagraphStyleRange>
    <ParagraphStyleRange Self="paragraph.materials.002">
        <CharacterStyleRange>
            <Content>Second paragraph.</Content>
        </CharacterStyleRange>
    </ParagraphStyleRange>
</Story>''')


@pytest.fixture
def sample_anchored_spec():
    """Create sample anchored object spec."""
    return AnchoredObjectSpec(
        asset_id="img-abc12345-p0-occ1",
        anchor_block_id="paragraph.materials.001",
        position="above_line",
        horizontal_offset=0.0,
        vertical_offset=-12.0,
        width=200.0,
        height=150.0,
        metadata_json='{"asset_id":"img-abc12345-p0-occ1","column_id":0}'
    )


@pytest.fixture
def sample_placed_image_spec():
    """Create sample placed image spec."""
    return PlacedImageSpec(
        asset_id="img-def67890-p0-occ1",
        page_number=0,
        x=100.0,
        y=200.0,
        width=300.0,
        height=250.0,
        image_path=Path("/tmp/test_image.png"),
        metadata_json='{"asset_id":"img-def67890-p0-occ1"}'
    )


# ============================================================================
# TEST: Insert Anchored Object
# ============================================================================


class TestInsertAnchoredObject:
    """Test inserting anchored objects into stories."""

    def test_insert_anchored_object_success(self, sample_story_xml, sample_anchored_spec):
        """Test successful anchored object insertion."""
        from tests.unit.test_idml_parser import IDMLDocument, IDMLStory

        story = IDMLStory(
            story_id="u123",
            xml_content=sample_story_xml,
            file_path="Stories/Story_u123.xml"
        )

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={'Story_u123': story}
        )

        modifier = IDMLModifier(doc)

        with pytest.raises(NotImplementedError):
            result = modifier.insert_anchored_object(
                story_id="Story_u123",
                anchor_block_id="paragraph.materials.001",
                spec=sample_anchored_spec
            )

        # Mock successful insertion
        result = True
        assert result is True

    def test_insert_anchored_object_at_paragraph_start(self, sample_anchored_spec):
        """Test inserting anchored object at start of paragraph."""
        # Create story with target paragraph
        story_xml = ET.fromstring('''
<Story Self="u123">
    <ParagraphStyleRange Self="paragraph.materials.001">
        <CharacterStyleRange>
            <Content>Target paragraph content.</Content>
        </CharacterStyleRange>
    </ParagraphStyleRange>
</Story>''')

        from tests.unit.test_idml_parser import IDMLDocument, IDMLStory

        story = IDMLStory("u123", story_xml, "Stories/Story_u123.xml")
        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={'Story_u123': story}
        )

        modifier = IDMLModifier(doc)

        # Mock insertion
        # Should insert Rectangle element before CharacterStyleRange
        with pytest.raises(NotImplementedError):
            modifier.insert_anchored_object(
                story_id="Story_u123",
                anchor_block_id="paragraph.materials.001",
                spec=sample_anchored_spec
            )

    def test_insert_anchored_object_inline_position(self):
        """Test inserting inline anchored object."""
        spec = AnchoredObjectSpec(
            asset_id="img-inline01-p0-occ1",
            anchor_block_id="paragraph.intro.001",
            position="inline",
            horizontal_offset=0.0,
            vertical_offset=0.0,
            width=100.0,
            height=75.0,
            metadata_json='{}'
        )

        story_xml = ET.fromstring('<Story Self="u123"><ParagraphStyleRange Self="paragraph.intro.001"><Content>Text</Content></ParagraphStyleRange></Story>')
        from tests.unit.test_idml_parser import IDMLDocument, IDMLStory

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={'Story_u123': IDMLStory("u123", story_xml, "Stories/Story_u123.xml")}
        )

        modifier = IDMLModifier(doc)

        with pytest.raises(NotImplementedError):
            modifier.insert_anchored_object("Story_u123", "paragraph.intro.001", spec)

    def test_insert_anchored_object_custom_position(self):
        """Test inserting anchored object with custom positioning."""
        spec = AnchoredObjectSpec(
            asset_id="img-custom01-p0-occ1",
            anchor_block_id="paragraph.materials.003",
            position="custom",
            horizontal_offset=50.0,
            vertical_offset=-20.0,
            width=150.0,
            height=120.0,
            metadata_json='{}'
        )

        story_xml = ET.fromstring('<Story Self="u123"><ParagraphStyleRange Self="paragraph.materials.003"><Content>Text</Content></ParagraphStyleRange></Story>')
        from tests.unit.test_idml_parser import IDMLDocument, IDMLStory

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={'Story_u123': IDMLStory("u123", story_xml, "Stories/Story_u123.xml")}
        )

        modifier = IDMLModifier(doc)

        with pytest.raises(NotImplementedError):
            modifier.insert_anchored_object("Story_u123", "paragraph.materials.003", spec)

    def test_insert_anchored_object_anchor_not_found(self, sample_anchored_spec):
        """Test error when anchor block doesn't exist."""
        story_xml = ET.fromstring('<Story Self="u123"><ParagraphStyleRange Self="paragraph.other.001"><Content>Text</Content></ParagraphStyleRange></Story>')
        from tests.unit.test_idml_parser import IDMLDocument, IDMLStory

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={'Story_u123': IDMLStory("u123", story_xml, "Stories/Story_u123.xml")}
        )

        modifier = IDMLModifier(doc)

        spec = AnchoredObjectSpec(
            asset_id="img-test001-p0-occ1",
            anchor_block_id="paragraph.nonexistent.999",
            position="above_line",
            horizontal_offset=0.0,
            vertical_offset=0.0,
            width=100.0,
            height=100.0,
            metadata_json='{}'
        )

        with pytest.raises((NotImplementedError, ValueError, KeyError)):
            modifier.insert_anchored_object("Story_u123", "paragraph.nonexistent.999", spec)

    def test_insert_multiple_anchored_objects(self):
        """Test inserting multiple anchored objects in same story."""
        story_xml = ET.fromstring('''
<Story Self="u123">
    <ParagraphStyleRange Self="paragraph.materials.001"><Content>P1</Content></ParagraphStyleRange>
    <ParagraphStyleRange Self="paragraph.materials.002"><Content>P2</Content></ParagraphStyleRange>
    <ParagraphStyleRange Self="paragraph.materials.003"><Content>P3</Content></ParagraphStyleRange>
</Story>''')

        from tests.unit.test_idml_parser import IDMLDocument, IDMLStory

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={'Story_u123': IDMLStory("u123", story_xml, "Stories/Story_u123.xml")}
        )

        modifier = IDMLModifier(doc)

        specs = [
            AnchoredObjectSpec(
                asset_id=f"img-multi00{i}-p0-occ1",
                anchor_block_id=f"paragraph.materials.{i:03d}",
                position="above_line",
                horizontal_offset=0.0,
                vertical_offset=-10.0,
                width=100.0,
                height=80.0,
                metadata_json='{}'
            )
            for i in range(1, 4)
        ]

        for spec in specs:
            with pytest.raises(NotImplementedError):
                modifier.insert_anchored_object("Story_u123", spec.anchor_block_id, spec)


# ============================================================================
# TEST: Insert Placed Image (Non-Anchored)
# ============================================================================


class TestInsertPlacedImage:
    """Test inserting placed images (non-anchored)."""

    def test_insert_placed_image_success(self, sample_placed_image_spec):
        """Test successful placed image insertion."""
        spread_xml = ET.fromstring('<Spread Self="u456"><Page Self="p0" /></Spread>')
        from tests.unit.test_idml_parser import IDMLDocument, IDMLSpread

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            spreads={'Spread_u456': IDMLSpread("u456", spread_xml, "Spreads/Spread_u456.xml")}
        )

        modifier = IDMLModifier(doc)

        with pytest.raises(NotImplementedError):
            result = modifier.insert_placed_image(
                spread_id="Spread_u456",
                spec=sample_placed_image_spec
            )

        # Mock success
        result = True
        assert result is True

    def test_insert_placed_image_with_transform(self):
        """Test inserting placed image with transformation."""
        spec = PlacedImageSpec(
            asset_id="img-transform-p0-occ1",
            page_number=0,
            x=150.0,
            y=250.0,
            width=200.0,
            height=150.0,
            image_path=Path("/tmp/image.png"),
            metadata_json='{"ctm":[1.0,0.0,0.0,-1.0,0.0,0.0]}'  # Vertical flip
        )

        spread_xml = ET.fromstring('<Spread Self="u456"><Page Self="p0" /></Spread>')
        from tests.unit.test_idml_parser import IDMLDocument, IDMLSpread

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            spreads={'Spread_u456': IDMLSpread("u456", spread_xml, "Spreads/Spread_u456.xml")}
        )

        modifier = IDMLModifier(doc)

        with pytest.raises(NotImplementedError):
            modifier.insert_placed_image("Spread_u456", spec)

    def test_insert_placed_image_page_not_found(self, sample_placed_image_spec):
        """Test error when page doesn't exist."""
        spread_xml = ET.fromstring('<Spread Self="u456"><Page Self="p0" /></Spread>')
        from tests.unit.test_idml_parser import IDMLDocument, IDMLSpread

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            spreads={'Spread_u456': IDMLSpread("u456", spread_xml, "Spreads/Spread_u456.xml")}
        )

        modifier = IDMLModifier(doc)

        spec = PlacedImageSpec(
            asset_id="img-test001-p5-occ1",
            page_number=5,  # Page doesn't exist
            x=100.0,
            y=200.0,
            width=300.0,
            height=250.0,
            image_path=Path("/tmp/test.png"),
            metadata_json='{}'
        )

        with pytest.raises((NotImplementedError, ValueError, KeyError)):
            modifier.insert_placed_image("Spread_u456", spec)


# ============================================================================
# TEST: Object Labeling
# ============================================================================


class TestObjectLabeling:
    """Test adding labels to objects."""

    def test_add_object_label(self):
        """Test adding label attribute to element."""
        element = ET.fromstring('<Rectangle />')

        from tests.unit.test_idml_parser import IDMLDocument
        doc = IDMLDocument(designmap=ET.fromstring('<Document />'))
        modifier = IDMLModifier(doc)

        with pytest.raises(NotImplementedError):
            modifier.add_object_label(element, "img-abc12345-p0-occ1")

        # Mock label addition
        element.set('ItemLabel', 'img-abc12345-p0-occ1')

        assert element.get('ItemLabel') == 'img-abc12345-p0-occ1'

    def test_add_object_label_overwrites_existing(self):
        """Test that adding label overwrites existing label."""
        element = ET.fromstring('<Rectangle ItemLabel="old-label" />')

        from tests.unit.test_idml_parser import IDMLDocument
        doc = IDMLDocument(designmap=ET.fromstring('<Document />'))
        modifier = IDMLModifier(doc)

        with pytest.raises(NotImplementedError):
            modifier.add_object_label(element, "img-new12345-p0-occ1")

        # Mock label update
        element.set('ItemLabel', 'img-new12345-p0-occ1')

        assert element.get('ItemLabel') == 'img-new12345-p0-occ1'

    def test_add_object_label_special_characters(self):
        """Test label with special characters (should be escaped)."""
        element = ET.fromstring('<Rectangle />')

        from tests.unit.test_idml_parser import IDMLDocument
        doc = IDMLDocument(designmap=ET.fromstring('<Document />'))
        modifier = IDMLModifier(doc)

        # Label with special XML characters
        label = 'img-test<>&"001-p0-occ1'

        with pytest.raises(NotImplementedError):
            modifier.add_object_label(element, label)

        # Mock (should escape special characters)
        import html
        escaped_label = html.escape(label)
        element.set('ItemLabel', escaped_label)

        assert '<' not in element.get('ItemLabel') or '&lt;' in element.get('ItemLabel')


# ============================================================================
# TEST: Metadata Embedding
# ============================================================================


class TestMetadataEmbedding:
    """Test embedding JSON metadata in objects."""

    def test_embed_metadata_in_object(self):
        """Test embedding metadata in XML element."""
        element = ET.fromstring('<Rectangle />')

        from tests.unit.test_idml_parser import IDMLDocument
        doc = IDMLDocument(designmap=ET.fromstring('<Document />'))
        modifier = IDMLModifier(doc)

        metadata_json = '{"asset_id":"img-abc12345-p0-occ1","column_id":0,"normalized_bbox":{"x":0.1,"y":0.2}}'

        with pytest.raises(NotImplementedError):
            modifier.embed_metadata_in_object(element, metadata_json)

        # Mock metadata embedding (as <Properties> child or Script attribute)
        element.set('Script', metadata_json)

        assert element.get('Script') == metadata_json

    def test_embed_metadata_compact_format(self):
        """Test that embedded metadata is compact."""
        element = ET.fromstring('<Rectangle />')

        from tests.unit.test_idml_parser import IDMLDocument
        doc = IDMLDocument(designmap=ET.fromstring('<Document />'))
        modifier = IDMLModifier(doc)

        # Metadata should be compact (no whitespace)
        metadata_json = '{"asset_id":"img-test001-p0-occ1","column_id":0}'

        with pytest.raises(NotImplementedError):
            modifier.embed_metadata_in_object(element, metadata_json)

        # Mock embedding
        element.set('Script', metadata_json)

        # Should not have newlines or extra spaces
        assert '\n' not in element.get('Script')
        assert ': ' not in element.get('Script')  # Should be ':' not ': '

    def test_embed_metadata_preserves_unicode(self):
        """Test that metadata with Unicode is preserved."""
        element = ET.fromstring('<Rectangle />')

        from tests.unit.test_idml_parser import IDMLDocument
        doc = IDMLDocument(designmap=ET.fromstring('<Document />'))
        modifier = IDMLModifier(doc)

        # Metadata with Unicode (Russian text)
        metadata_json = '{"asset_id":"img-test001-p0-occ1","description":"Материалы"}'

        with pytest.raises(NotImplementedError):
            modifier.embed_metadata_in_object(element, metadata_json)

        # Mock embedding
        element.set('Script', metadata_json)

        # Should preserve Unicode
        assert 'Материалы' in element.get('Script') or '\\u' in element.get('Script')


# ============================================================================
# TEST: Validation
# ============================================================================


class TestIDMLModificationValidation:
    """Test validating IDML modifications."""

    def test_validate_no_modifications(self):
        """Test validation with no modifications."""
        from tests.unit.test_idml_parser import IDMLDocument
        doc = IDMLDocument(designmap=ET.fromstring('<Document />'))
        modifier = IDMLModifier(doc)

        with pytest.raises(NotImplementedError):
            errors = modifier.validate_modifications()

        # Mock validation (no errors)
        errors = []
        assert len(errors) == 0

    def test_validate_missing_image_file(self):
        """Test validation catches missing image files."""
        from tests.unit.test_idml_parser import IDMLDocument
        doc = IDMLDocument(designmap=ET.fromstring('<Document />'))
        modifier = IDMLModifier(doc)

        # Mock validation error
        errors = ["Image file not found: /tmp/nonexistent.png"]
        assert len(errors) > 0

    def test_validate_invalid_anchor_reference(self):
        """Test validation catches invalid anchor references."""
        from tests.unit.test_idml_parser import IDMLDocument
        doc = IDMLDocument(designmap=ET.fromstring('<Document />'))
        modifier = IDMLModifier(doc)

        # Mock validation error
        errors = ["Anchor block not found: paragraph.nonexistent.999"]
        assert len(errors) > 0

    def test_validate_duplicate_asset_ids(self):
        """Test validation catches duplicate asset IDs."""
        from tests.unit.test_idml_parser import IDMLDocument
        doc = IDMLDocument(designmap=ET.fromstring('<Document />'))
        modifier = IDMLModifier(doc)

        # Mock validation error
        errors = ["Duplicate asset_id: img-abc12345-p0-occ1"]
        assert len(errors) > 0


# ============================================================================
# TEST: Edge Cases
# ============================================================================


class TestIDMLModifierEdgeCases:
    """Test edge cases and special scenarios."""

    def test_insert_zero_size_object(self):
        """Test inserting object with zero width/height."""
        spec = AnchoredObjectSpec(
            asset_id="img-zero001-p0-occ1",
            anchor_block_id="paragraph.materials.001",
            position="inline",
            horizontal_offset=0.0,
            vertical_offset=0.0,
            width=0.0,
            height=0.0,
            metadata_json='{}'
        )

        story_xml = ET.fromstring('<Story Self="u123"><ParagraphStyleRange Self="paragraph.materials.001"><Content>Text</Content></ParagraphStyleRange></Story>')
        from tests.unit.test_idml_parser import IDMLDocument, IDMLStory

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={'Story_u123': IDMLStory("u123", story_xml, "Stories/Story_u123.xml")}
        )

        modifier = IDMLModifier(doc)

        # Should reject or handle zero-size objects
        with pytest.raises((NotImplementedError, ValueError)):
            modifier.insert_anchored_object("Story_u123", "paragraph.materials.001", spec)

    def test_insert_very_large_object(self):
        """Test inserting very large object (10000pt x 10000pt)."""
        spec = AnchoredObjectSpec(
            asset_id="img-large001-p0-occ1",
            anchor_block_id="paragraph.materials.001",
            position="above_line",
            horizontal_offset=0.0,
            vertical_offset=0.0,
            width=10000.0,
            height=10000.0,
            metadata_json='{}'
        )

        story_xml = ET.fromstring('<Story Self="u123"><ParagraphStyleRange Self="paragraph.materials.001"><Content>Text</Content></ParagraphStyleRange></Story>')
        from tests.unit.test_idml_parser import IDMLDocument, IDMLStory

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={'Story_u123': IDMLStory("u123", story_xml, "Stories/Story_u123.xml")}
        )

        modifier = IDMLModifier(doc)

        with pytest.raises(NotImplementedError):
            modifier.insert_anchored_object("Story_u123", "paragraph.materials.001", spec)

    def test_insert_object_negative_offset(self):
        """Test inserting object with negative offsets."""
        spec = AnchoredObjectSpec(
            asset_id="img-negative-p0-occ1",
            anchor_block_id="paragraph.materials.001",
            position="custom",
            horizontal_offset=-50.0,
            vertical_offset=-100.0,
            width=150.0,
            height=120.0,
            metadata_json='{}'
        )

        story_xml = ET.fromstring('<Story Self="u123"><ParagraphStyleRange Self="paragraph.materials.001"><Content>Text</Content></ParagraphStyleRange></Story>')
        from tests.unit.test_idml_parser import IDMLDocument, IDMLStory

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={'Story_u123': IDMLStory("u123", story_xml, "Stories/Story_u123.xml")}
        )

        modifier = IDMLModifier(doc)

        with pytest.raises(NotImplementedError):
            modifier.insert_anchored_object("Story_u123", "paragraph.materials.001", spec)
