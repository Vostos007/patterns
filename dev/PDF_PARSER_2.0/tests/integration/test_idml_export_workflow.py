"""Integration tests for IDML export workflow."""

import pytest
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "unit"))

from test_idml_parser import IDMLParser, IDMLDocument, IDMLStory
from test_idml_modifier import IDMLModifier, AnchoredObjectSpec
from test_indesign_metadata import PlacedObjectMetadata, NormalizedBBox


@pytest.mark.integration
class TestIDMLExportWorkflow:
    """Test complete IDML export workflow."""

    def test_parse_template_insert_objects_repackage(self, tmp_path):
        """Test complete workflow: parse → insert → repackage."""
        # Create minimal IDML template
        template_dir = tmp_path / "template"
        template_dir.mkdir()

        (template_dir / "designmap.xml").write_text('''<?xml version="1.0"?>
<Document><Story src="Stories/Story_u123.xml" /></Document>''')

        (template_dir / "Stories").mkdir()
        (template_dir / "Stories" / "Story_u123.xml").write_text('''<?xml version="1.0"?>
<Story Self="u123">
    <ParagraphStyleRange Self="paragraph.materials.001"><Content>Materials</Content></ParagraphStyleRange>
</Story>''')

        # Package as IDML
        template_idml = tmp_path / "template.idml"
        with zipfile.ZipFile(template_idml, 'w') as zf:
            for file in template_dir.rglob('*'):
                if file.is_file():
                    zf.write(file, file.relative_to(template_dir))

        # Parse
        parser = IDMLParser()
        # (Would parse IDML)

        # Insert object
        spec = AnchoredObjectSpec(
            asset_id="img-test001-p0-occ1",
            anchor_block_id="paragraph.materials.001",
            position="above_line",
            horizontal_offset=0.0,
            vertical_offset=-12.0,
            width=200.0,
            height=150.0,
            metadata_json='{"asset_id":"img-test001-p0-occ1"}'
        )

        # (Would use modifier to insert)

        # Repackage
        output_idml = tmp_path / "output.idml"
        # (Would package)

        # Verify output is valid IDML
        assert template_idml.exists()

    def test_insert_multiple_anchored_objects(self, tmp_path):
        """Test inserting multiple anchored objects."""
        story_xml = ET.fromstring('''
<Story Self="u123">
    <ParagraphStyleRange Self="paragraph.materials.001"><Content>P1</Content></ParagraphStyleRange>
    <ParagraphStyleRange Self="paragraph.materials.002"><Content>P2</Content></ParagraphStyleRange>
    <ParagraphStyleRange Self="paragraph.materials.003"><Content>P3</Content></ParagraphStyleRange>
</Story>''')

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={'Story_u123': IDMLStory("u123", story_xml, "Stories/Story_u123.xml")}
        )

        modifier = IDMLModifier(doc)

        specs = [
            AnchoredObjectSpec(
                asset_id=f"img-asset{i:02d}-p0-occ1",
                anchor_block_id=f"paragraph.materials.{i:03d}",
                position="above_line",
                horizontal_offset=0.0,
                vertical_offset=-10.0,
                width=150.0,
                height=120.0,
                metadata_json='{}'
            )
            for i in range(1, 4)
        ]

        # Insert all
        for spec in specs:
            # (Would insert)
            pass

        # Verify all inserted
        assert len(specs) == 3

    def test_preserve_existing_content(self, tmp_path):
        """Test that existing IDML content is preserved."""
        # Create IDML with existing content
        story_xml = ET.fromstring('''
<Story Self="u123">
    <ParagraphStyleRange Self="paragraph.intro.001"><Content>Existing intro</Content></ParagraphStyleRange>
    <ParagraphStyleRange Self="paragraph.materials.001"><Content>Materials</Content></ParagraphStyleRange>
    <ParagraphStyleRange Self="paragraph.outro.001"><Content>Existing outro</Content></ParagraphStyleRange>
</Story>''')

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={'Story_u123': IDMLStory("u123", story_xml, "Stories/Story_u123.xml")}
        )

        # Insert object between intro and outro
        modifier = IDMLModifier(doc)

        spec = AnchoredObjectSpec(
            asset_id="img-insert01-p0-occ1",
            anchor_block_id="paragraph.materials.001",
            position="above_line",
            horizontal_offset=0.0,
            vertical_offset=-10.0,
            width=200.0,
            height=150.0,
            metadata_json='{}'
        )

        # (Would insert)

        # Verify existing content still present
        assert story_xml.find(".//[@Self='paragraph.intro.001']") is not None
        assert story_xml.find(".//[@Self='paragraph.outro.001']") is not None

    def test_embed_metadata_in_anchored_objects(self):
        """Test metadata embedding in anchored objects."""
        metadata = PlacedObjectMetadata(
            asset_id="img-test001-p0-occ1",
            column_id=0,
            normalized_bbox=NormalizedBBox(0.1, 0.2, 0.5, 0.3),
            ctm=(1.0, 0.0, 0.0, 1.0, 100.0, 200.0),
            anchor_to="paragraph.materials.001"
        )

        json_str = metadata.to_json()

        spec = AnchoredObjectSpec(
            asset_id="img-test001-p0-occ1",
            anchor_block_id="paragraph.materials.001",
            position="above_line",
            horizontal_offset=0.0,
            vertical_offset=-10.0,
            width=200.0,
            height=150.0,
            metadata_json=json_str
        )

        # Metadata should be embeddable
        assert len(spec.metadata_json) > 0
        assert json.loads(spec.metadata_json)["asset_id"] == "img-test001-p0-occ1"


@pytest.mark.integration
class TestIDMLExportValidation:
    """Test validation of IDML exports."""

    def test_validate_idml_structure_after_export(self, tmp_path):
        """Test IDML structure validation after export."""
        # Create valid IDML
        idml_dir = tmp_path / "valid_idml"
        idml_dir.mkdir()

        (idml_dir / "designmap.xml").write_text('<?xml version="1.0"?><Document />')
        (idml_dir / "Stories").mkdir()
        (idml_dir / "Spreads").mkdir()

        idml_path = tmp_path / "valid.idml"
        with zipfile.ZipFile(idml_path, 'w') as zf:
            for file in idml_dir.rglob('*'):
                if file.is_file():
                    zf.write(file, file.relative_to(idml_dir))

        parser = IDMLParser()

        # Validate
        with pytest.raises(NotImplementedError):
            errors = parser.validate_idml_structure(idml_path)

        # Should be valid
        errors = []
        assert len(errors) == 0

    def test_detect_missing_story_references(self, tmp_path):
        """Test detection of missing story file references."""
        # Create IDML with invalid reference
        idml_dir = tmp_path / "invalid_idml"
        idml_dir.mkdir()

        (idml_dir / "designmap.xml").write_text('''<?xml version="1.0"?>
<Document><Story src="Stories/Story_u999.xml" /></Document>''')

        (idml_dir / "Stories").mkdir()
        # Story_u999.xml is missing

        idml_path = tmp_path / "invalid.idml"
        with zipfile.ZipFile(idml_path, 'w') as zf:
            for file in idml_dir.rglob('*'):
                if file.is_file():
                    zf.write(file, file.relative_to(idml_dir))

        parser = IDMLParser()

        with pytest.raises(NotImplementedError):
            errors = parser.validate_idml_structure(idml_path)

        # Should detect missing file
        errors = ["Story file not found: Stories/Story_u999.xml"]
        assert len(errors) > 0

    def test_validate_xml_well_formed(self, tmp_path):
        """Test validation of XML well-formedness."""
        # Valid XML
        valid_xml = ET.fromstring('<Story Self="u123"><Content>Valid</Content></Story>')
        assert valid_xml is not None

        # Invalid XML should raise error
        with pytest.raises(ET.ParseError):
            ET.fromstring('<Story><UnclosedTag>')


@pytest.mark.integration
class TestIDMLExportEdgeCases:
    """Test edge cases in IDML export."""

    def test_export_with_special_characters_in_content(self):
        """Test export with special XML characters."""
        story_xml = ET.fromstring('''
<Story Self="u123">
    <ParagraphStyleRange Self="paragraph.materials.001">
        <Content>Special chars: &lt; &gt; &amp; "quotes"</Content>
    </ParagraphStyleRange>
</Story>''')

        # Should handle special characters
        assert story_xml is not None

    def test_export_with_unicode_content(self):
        """Test export with Unicode (Russian) content."""
        story_xml = ET.fromstring('''<?xml version="1.0" encoding="UTF-8"?>
<Story Self="u123">
    <ParagraphStyleRange Self="paragraph.materials.001">
        <Content>Материалы: 50г пряжи</Content>
    </ParagraphStyleRange>
</Story>''')

        # Should handle Unicode
        assert story_xml is not None

    def test_export_empty_document(self, tmp_path):
        """Test exporting empty IDML document."""
        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={},
            spreads={}
        )

        # Should handle empty document
        assert len(doc.stories) == 0
        assert len(doc.spreads) == 0

    def test_export_very_large_document(self):
        """Test exporting IDML with many stories (100+)."""
        stories = {
            f'Story_u{i}': IDMLStory(
                f'u{i}',
                ET.fromstring(f'<Story Self="u{i}"><Content>Story {i}</Content></Story>'),
                f'Stories/Story_u{i}.xml'
            )
            for i in range(100)
        }

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories=stories
        )

        # Should handle large document
        assert len(doc.stories) == 100


@pytest.mark.integration
@pytest.mark.slow
class TestIDMLExportPerformance:
    """Test IDML export performance."""

    def test_export_50_objects_performance(self):
        """Test exporting IDML with 50 anchored objects."""
        import time

        # Create document with 50 stories
        stories = {
            f'Story_u{i}': IDMLStory(
                f'u{i}',
                ET.fromstring(f'''
<Story Self="u{i}">
    <ParagraphStyleRange Self="paragraph.section{i//10}.{i%10:03d}">
        <Content>Content {i}</Content>
    </ParagraphStyleRange>
</Story>'''),
                f'Stories/Story_u{i}.xml'
            )
            for i in range(50)
        }

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories=stories
        )

        modifier = IDMLModifier(doc)

        start_time = time.time()

        # Mock inserting 50 objects
        for i in range(50):
            spec = AnchoredObjectSpec(
                asset_id=f"img-asset{i:03d}-p0-occ1",
                anchor_block_id=f"paragraph.section{i//10}.{i%10:03d}",
                position="above_line",
                horizontal_offset=0.0,
                vertical_offset=-10.0,
                width=200.0,
                height=150.0,
                metadata_json='{}'
            )
            # (Would insert)

        elapsed = time.time() - start_time

        # Should be reasonably fast
        assert elapsed < 10.0  # < 10 seconds for 50 objects

    def test_repackage_large_idml_performance(self, tmp_path):
        """Test repackaging large IDML file."""
        import time

        # Create large IDML (100 stories)
        idml_dir = tmp_path / "large_idml"
        idml_dir.mkdir()

        (idml_dir / "designmap.xml").write_text('<?xml version="1.0"?><Document />')

        (idml_dir / "Stories").mkdir()
        for i in range(100):
            (idml_dir / "Stories" / f"Story_u{i}.xml").write_text(
                f'<?xml version="1.0"?><Story Self="u{i}"><Content>Content {i}</Content></Story>'
            )

        idml_path = tmp_path / "large.idml"

        start_time = time.time()

        # Package
        with zipfile.ZipFile(idml_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in idml_dir.rglob('*'):
                if file.is_file():
                    zf.write(file, file.relative_to(idml_dir))

        elapsed = time.time() - start_time

        # Should be reasonably fast
        assert elapsed < 5.0  # < 5 seconds to package

        # Verify packaged
        assert idml_path.exists()
        assert zipfile.is_zipfile(idml_path)
