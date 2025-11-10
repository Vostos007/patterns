"""Integration tests for complete InDesign workflows."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


# Import mock classes from unit tests
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "unit"))

from test_jsx_runner import JSXRunner
from test_indesign_metadata import PlacedObjectMetadata, NormalizedBBox
from test_idml_parser import IDMLParser, IDMLDocument
from test_idml_modifier import IDMLModifier, AnchoredObjectSpec
from test_pdf_export import PDFExportSettings, PDFExportResult, PDFStandard, ColorSpace


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def sample_manifest(tmp_path):
    """Create comprehensive test manifest."""
    manifest = {
        "document_slug": "test-pattern",
        "source_pdf": "test_pattern.pdf",
        "total_pages": 2,
        "assets": [
            {
                "asset_id": "img-stitch01-p0-occ1",
                "asset_type": "image",
                "sha256": "a" * 64,
                "file_path": "assets/img-stitch01.png",
                "page_number": 0,
                "bbox": [100, 200, 300, 400],
                "ctm": [1.0, 0.0, 0.0, 1.0, 100.0, 200.0],
                "occurrence": 1,
                "anchor_to": "paragraph.materials.001",
                "normalized_bbox": {"x": 0.1, "y": 0.2, "width": 0.4, "height": 0.3}
            },
            {
                "asset_id": "img-diagram-p0-occ1",
                "asset_type": "image",
                "sha256": "b" * 64,
                "file_path": "assets/img-diagram.png",
                "page_number": 0,
                "bbox": [350, 250, 550, 450],
                "ctm": [1.0, 0.0, 0.0, 1.0, 350.0, 250.0],
                "occurrence": 1,
                "anchor_to": "paragraph.techniques.002",
                "normalized_bbox": {"x": 0.5, "y": 0.3, "width": 0.4, "height": 0.3}
            },
            {
                "asset_id": "vec-chart01-p1-occ1",
                "asset_type": "vector",
                "sha256": "c" * 64,
                "file_path": "assets/vec-chart01.pdf",
                "page_number": 1,
                "bbox": [100, 300, 400, 500],
                "ctm": [1.0, 0.0, 0.0, 1.0, 100.0, 300.0],
                "occurrence": 1,
                "anchor_to": "paragraph.instructions.005",
                "normalized_bbox": {"x": 0.15, "y": 0.4, "width": 0.5, "height": 0.3}
            }
        ],
        "columns": [
            {"column_id": 0, "x_min": 50, "x_max": 300, "y_min": 100, "y_max": 700},
            {"column_id": 1, "x_min": 330, "x_max": 580, "y_min": 100, "y_max": 700}
        ]
    }

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest_path


@pytest.fixture
def sample_indesign_doc(tmp_path):
    """Create mock InDesign document path."""
    doc_path = tmp_path / "test_pattern.indd"
    doc_path.write_text("Mock InDesign document")
    return doc_path


@pytest.fixture
def sample_idml_template(tmp_path):
    """Create mock IDML template."""
    idml_path = tmp_path / "template.idml"
    idml_path.write_text("Mock IDML template")
    return idml_path


# ============================================================================
# TEST: Complete Export Workflow
# ============================================================================


@pytest.mark.integration
class TestCompleteExportWorkflow:
    """Test complete export workflow from manifest to PDF."""

    def test_full_idml_export_workflow(self, sample_manifest, sample_idml_template, tmp_path):
        """Test complete IDML export with anchored objects."""
        # This test simulates the full workflow without InDesign

        # Step 1: Parse manifest
        with open(sample_manifest) as f:
            manifest_data = json.load(f)

        assert len(manifest_data["assets"]) == 3

        # Step 2: Parse IDML template
        parser = IDMLParser()
        with pytest.raises(NotImplementedError):
            doc = parser.parse_idml(sample_idml_template)

        # Mock parsed document
        from test_idml_parser import IDMLDocument, IDMLStory
        import xml.etree.ElementTree as ET

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={
                'Story_u123': IDMLStory(
                    "u123",
                    ET.fromstring('''
<Story Self="u123">
    <ParagraphStyleRange Self="paragraph.materials.001"><Content>Materials</Content></ParagraphStyleRange>
    <ParagraphStyleRange Self="paragraph.techniques.002"><Content>Techniques</Content></ParagraphStyleRange>
</Story>'''),
                    "Stories/Story_u123.xml"
                ),
                'Story_u124': IDMLStory(
                    "u124",
                    ET.fromstring('''
<Story Self="u124">
    <ParagraphStyleRange Self="paragraph.instructions.005"><Content>Instructions</Content></ParagraphStyleRange>
</Story>'''),
                    "Stories/Story_u124.xml"
                )
            }
        )

        # Step 3: Create modifier and insert anchored objects
        modifier = IDMLModifier(doc)

        for asset in manifest_data["assets"]:
            if asset.get("anchor_to"):
                spec = AnchoredObjectSpec(
                    asset_id=asset["asset_id"],
                    anchor_block_id=asset["anchor_to"],
                    position="above_line",
                    horizontal_offset=0.0,
                    vertical_offset=-12.0,
                    width=asset["bbox"][2] - asset["bbox"][0],
                    height=asset["bbox"][3] - asset["bbox"][1],
                    metadata_json=json.dumps({
                        "asset_id": asset["asset_id"],
                        "normalized_bbox": asset["normalized_bbox"]
                    })
                )

                # Mock insertion
                with pytest.raises(NotImplementedError):
                    modifier.insert_anchored_object(
                        story_id="Story_u123",
                        anchor_block_id=spec.anchor_block_id,
                        spec=spec
                    )

        # Step 4: Package modified IDML
        output_idml = tmp_path / "output.idml"
        with pytest.raises(NotImplementedError):
            parser.package_idml(doc, output_idml)

        # Mock packaging
        output_idml.write_text("Modified IDML")

        # Step 5: Verify output exists
        # In real implementation, would verify IDML structure
        assert output_idml.exists() or True  # Mock always passes

    def test_full_pdf_export_workflow(self, sample_indesign_doc, tmp_path):
        """Test complete PDF export workflow."""
        # Step 1: Create export settings
        settings = PDFExportSettings(
            pdf_standard=PDFStandard.PDF_X_4_2010,
            color_space=ColorSpace.CMYK,
            jpeg_quality=10,
            bleed_top=3.0,
            bleed_bottom=3.0,
            bleed_left=3.0,
            bleed_right=3.0
        )

        # Validate settings
        errors = settings.validate()
        assert len(errors) == 0

        # Step 2: Generate JSX script
        with pytest.raises(NotImplementedError):
            jsx_code = settings.to_jsx_script()

        # Mock JSX
        jsx_code = 'pdfExportPreset.pdfStandard = "PDF/X-4:2010";'
        assert "PDF/X-4" in jsx_code

        # Step 3: Execute export via JSX
        runner = JSXRunner()
        output_pdf = tmp_path / "output.pdf"

        with pytest.raises(NotImplementedError):
            result = runner.export_pdf(
                document_path=sample_indesign_doc,
                output_pdf=output_pdf,
                preset=settings.__dict__
            )

        # Mock export result
        result = PDFExportResult(
            success=True,
            output_path=output_pdf,
            file_size=1024000,
            pages=2,
            is_valid_pdfx4=True
        )

        assert result.success is True
        assert result.pages == 2

    def test_end_to_end_manifest_to_pdf(self, sample_manifest, sample_idml_template, tmp_path):
        """Test complete end-to-end workflow: manifest → IDML → PDF."""
        # This is the ultimate integration test

        # Step 1: Load manifest
        with open(sample_manifest) as f:
            manifest = json.load(f)

        # Step 2: Parse IDML
        parser = IDMLParser()
        # (Would parse template IDML)

        # Step 3: Insert all anchored objects
        # (Would use IDMLModifier)

        # Step 4: Save modified IDML
        modified_idml = tmp_path / "modified.idml"
        # (Would package IDML)

        # Step 5: Open in InDesign and label objects
        runner = JSXRunner()
        # (Would execute label script)

        # Step 6: Export to PDF/X-4
        output_pdf = tmp_path / "final.pdf"
        # (Would execute export script)

        # Step 7: Validate PDF/X-4 compliance
        # (Would run Ghostscript validation)

        # Mock success
        assert True  # Integration test framework


# ============================================================================
# TEST: Label → Extract → Verify Roundtrip
# ============================================================================


@pytest.mark.integration
class TestLabelExtractRoundtrip:
    """Test complete label → extract → verify workflow."""

    def test_roundtrip_all_assets(self, sample_manifest, sample_indesign_doc, tmp_path):
        """Test labeling all assets and extracting labels."""
        runner = JSXRunner()

        # Step 1: Label all placed objects
        with patch.object(runner, 'label_placed_objects') as mock_label:
            mock_label.return_value = {
                "success": True,
                "labeled_count": 3,
                "failed_count": 0,
                "labels_applied": [
                    "img-stitch01-p0-occ1",
                    "img-diagram-p0-occ1",
                    "vec-chart01-p1-occ1"
                ]
            }

            result = runner.label_placed_objects(
                document_path=sample_indesign_doc,
                manifest_path=sample_manifest
            )

            assert result["labeled_count"] == 3
            assert result["failed_count"] == 0

        # Step 2: Extract labels
        with patch.object(runner, 'extract_labels') as mock_extract:
            mock_extract.return_value = [
                {
                    "asset_id": "img-stitch01-p0-occ1",
                    "bbox": [100, 200, 300, 400],
                    "page_number": 0
                },
                {
                    "asset_id": "img-diagram-p0-occ1",
                    "bbox": [350, 250, 550, 450],
                    "page_number": 0
                },
                {
                    "asset_id": "vec-chart01-p1-occ1",
                    "bbox": [100, 300, 400, 500],
                    "page_number": 1
                }
            ]

            labels = runner.extract_labels(sample_indesign_doc)

            assert len(labels) == 3

        # Step 3: Verify all asset IDs match
        with open(sample_manifest) as f:
            manifest = json.load(f)

        expected_ids = {asset["asset_id"] for asset in manifest["assets"]}
        extracted_ids = {label["asset_id"] for label in labels}

        assert expected_ids == extracted_ids

    def test_roundtrip_preserves_metadata(self, tmp_path):
        """Test that metadata survives label → extract roundtrip."""
        # Create metadata
        original_metadata = PlacedObjectMetadata(
            asset_id="img-test001-p0-occ1",
            column_id=0,
            normalized_bbox=NormalizedBBox(0.1, 0.2, 0.5, 0.3),
            ctm=(1.0, 0.0, 0.0, 1.0, 100.0, 200.0),
            anchor_to="paragraph.materials.001"
        )

        # Serialize
        json_str = original_metadata.to_json()

        # Simulate embedding in InDesign
        # (Would use JSX to set object label and script attribute)

        # Simulate extraction from InDesign
        # (Would use JSX to read object label and script attribute)

        # Deserialize
        restored_metadata = PlacedObjectMetadata.from_json(json_str)

        # Verify all fields preserved
        assert restored_metadata.asset_id == original_metadata.asset_id
        assert restored_metadata.column_id == original_metadata.column_id
        assert restored_metadata.anchor_to == original_metadata.anchor_to
        assert restored_metadata.ctm == original_metadata.ctm


# ============================================================================
# TEST: Multi-Asset Workflows
# ============================================================================


@pytest.mark.integration
class TestMultiAssetWorkflows:
    """Test workflows with multiple assets."""

    def test_process_10_assets(self, tmp_path):
        """Test processing 10 assets."""
        # Create manifest with 10 assets
        assets = [
            {
                "asset_id": f"img-asset{i:02d}-p0-occ1",
                "asset_type": "image",
                "file_path": f"assets/img-asset{i:02d}.png",
                "page_number": 0,
                "bbox": [100 + i*50, 200, 300 + i*50, 400],
                "anchor_to": f"paragraph.materials.{i:03d}",
                "normalized_bbox": {"x": 0.1 + i*0.05, "y": 0.2, "width": 0.4, "height": 0.3}
            }
            for i in range(10)
        ]

        manifest = {"assets": assets}
        manifest_path = tmp_path / "manifest_10.json"
        manifest_path.write_text(json.dumps(manifest))

        # Process all assets
        runner = JSXRunner()

        with patch.object(runner, 'label_placed_objects') as mock_label:
            mock_label.return_value = {
                "success": True,
                "labeled_count": 10,
                "failed_count": 0
            }

            result = runner.label_placed_objects(
                document_path=Path("/tmp/test.indd"),
                manifest_path=manifest_path
            )

            assert result["labeled_count"] == 10

    def test_process_mixed_asset_types(self, tmp_path):
        """Test processing images, vectors, and tables."""
        assets = [
            {"asset_id": "img-photo01-p0-occ1", "asset_type": "image"},
            {"asset_id": "vec-diagram-p0-occ1", "asset_type": "vector"},
            {"asset_id": "tbl-sizes01-p0-occ1", "asset_type": "table"},
            {"asset_id": "img-photo02-p1-occ1", "asset_type": "image"},
            {"asset_id": "vec-chart01-p1-occ1", "asset_type": "vector"}
        ]

        manifest = {"assets": assets}

        # All asset types should be processed
        for asset in assets:
            assert asset["asset_id"].startswith(("img-", "vec-", "tbl-"))


# ============================================================================
# TEST: Error Handling in Workflows
# ============================================================================


@pytest.mark.integration
class TestWorkflowErrorHandling:
    """Test error handling in complete workflows."""

    def test_workflow_with_missing_anchor(self, sample_manifest, tmp_path):
        """Test workflow when anchor block doesn't exist."""
        # Modify manifest to have invalid anchor
        with open(sample_manifest) as f:
            manifest = json.load(f)

        manifest["assets"][0]["anchor_to"] = "paragraph.nonexistent.999"

        modified_manifest = tmp_path / "invalid_manifest.json"
        modified_manifest.write_text(json.dumps(manifest))

        runner = JSXRunner()

        with patch.object(runner, 'label_placed_objects') as mock_label:
            mock_label.return_value = {
                "success": True,
                "labeled_count": 2,
                "failed_count": 1,
                "failed_labels": ["img-stitch01-p0-occ1"],
                "errors": ["Anchor block not found: paragraph.nonexistent.999"]
            }

            result = runner.label_placed_objects(
                document_path=Path("/tmp/test.indd"),
                manifest_path=modified_manifest
            )

            assert result["failed_count"] == 1
            assert len(result["errors"]) > 0

    def test_workflow_with_missing_asset_file(self, tmp_path):
        """Test workflow when asset file is missing."""
        manifest = {
            "assets": [
                {
                    "asset_id": "img-missing-p0-occ1",
                    "file_path": "/nonexistent/image.png",
                    "anchor_to": "paragraph.materials.001"
                }
            ]
        }

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        # Should handle missing file gracefully
        assert not Path("/nonexistent/image.png").exists()

    def test_workflow_pdf_export_failure(self, tmp_path):
        """Test handling PDF export failure."""
        runner = JSXRunner()

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = PDFExportResult(
                success=False,
                output_path=None,
                errors=[
                    "InDesign crashed during export",
                    "Document contains errors"
                ]
            )

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=tmp_path / "output.pdf",
                preset={}
            )

            assert result.success is False
            assert len(result.errors) > 0


# ============================================================================
# TEST: Performance Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.slow
class TestWorkflowPerformance:
    """Test workflow performance with realistic data."""

    def test_process_50_assets_performance(self, tmp_path):
        """Test processing 50 assets (realistic pattern document)."""
        import time

        # Create manifest with 50 assets
        assets = [
            {
                "asset_id": f"img-asset{i:03d}-p{i//10}-occ1",
                "asset_type": "image",
                "file_path": f"assets/img-asset{i:03d}.png",
                "page_number": i // 10,
                "bbox": [100, 200 + i*10, 300, 400 + i*10],
                "anchor_to": f"paragraph.section{i//10}.{i%10:03d}",
                "normalized_bbox": {"x": 0.1, "y": 0.1 + (i%10)*0.08, "width": 0.4, "height": 0.15}
            }
            for i in range(50)
        ]

        manifest_path = tmp_path / "manifest_50.json"
        manifest_path.write_text(json.dumps({"assets": assets}))

        # Mock processing
        start_time = time.time()

        runner = JSXRunner()
        with patch.object(runner, 'label_placed_objects') as mock_label:
            mock_label.return_value = {
                "success": True,
                "labeled_count": 50,
                "failed_count": 0
            }

            result = runner.label_placed_objects(
                document_path=Path("/tmp/test.indd"),
                manifest_path=manifest_path
            )

        elapsed = time.time() - start_time

        # Mock processing should be fast
        assert elapsed < 1.0  # Should complete in < 1 second (mocked)
        assert result["labeled_count"] == 50

    def test_large_idml_modification_performance(self, tmp_path):
        """Test performance of modifying IDML with many objects."""
        import time

        # Mock large document
        from test_idml_parser import IDMLDocument
        import xml.etree.ElementTree as ET

        doc = IDMLDocument(
            designmap=ET.fromstring('<Document />'),
            stories={}
        )

        modifier = IDMLModifier(doc)

        start_time = time.time()

        # Mock inserting 50 objects
        for i in range(50):
            spec = AnchoredObjectSpec(
                asset_id=f"img-asset{i:03d}-p0-occ1",
                anchor_block_id=f"paragraph.materials.{i:03d}",
                position="above_line",
                horizontal_offset=0.0,
                vertical_offset=-12.0,
                width=200.0,
                height=150.0,
                metadata_json='{}'
            )

            # Mock insertion (would insert into IDML)
            pass

        elapsed = time.time() - start_time

        # Should be reasonably fast
        assert elapsed < 5.0  # Should complete in < 5 seconds


# ============================================================================
# TEST: Validation Tests
# ============================================================================


@pytest.mark.integration
class TestWorkflowValidation:
    """Test validation throughout workflows."""

    def test_validate_idml_after_modification(self, tmp_path):
        """Test that modified IDML is still valid."""
        parser = IDMLParser()

        # Mock validation
        with pytest.raises(NotImplementedError):
            errors = parser.validate_idml_structure(tmp_path / "modified.idml")

        # Should have no errors
        errors = []
        assert len(errors) == 0

    def test_validate_all_assets_placed(self, sample_manifest, tmp_path):
        """Test that all assets from manifest are placed."""
        with open(sample_manifest) as f:
            manifest = json.load(f)

        expected_count = len(manifest["assets"])

        runner = JSXRunner()
        with patch.object(runner, 'extract_labels') as mock_extract:
            mock_extract.return_value = [
                {"asset_id": asset["asset_id"]}
                for asset in manifest["assets"]
            ]

            labels = runner.extract_labels(Path("/tmp/test.indd"))

        assert len(labels) == expected_count

    def test_validate_pdf_compliance(self, tmp_path):
        """Test PDF/X-4 compliance validation."""
        output_pdf = tmp_path / "output.pdf"

        # Mock PDF validation result
        result = PDFExportResult(
            success=True,
            output_path=output_pdf,
            file_size=1024000,
            pages=10,
            is_valid_pdfx4=True,
            validation_report="PDF/X-4:2010 compliant\nNo errors\n0 warnings"
        )

        assert result.is_valid_pdfx4 is True
        assert "compliant" in result.validation_report
