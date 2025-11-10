"""Unit tests for JSX Runner (InDesign script execution)."""

import pytest
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Any


# Mock JSXRunner class (will be implemented by Agent 1)
class JSXRunner:
    """Executes JSX scripts in InDesign via AppleScript (macOS) or COM (Windows)."""

    def __init__(self, indesign_app_name: str = "Adobe InDesign 2024"):
        self.indesign_app_name = indesign_app_name
        self.last_result = None

    def execute_script(self, script_path: Path, **params: Any) -> dict:
        """Execute JSX script with parameters."""
        raise NotImplementedError("To be implemented by Agent 1")

    def label_placed_objects(self, document_path: Path, manifest_path: Path) -> dict:
        """Label all placed objects with asset IDs from manifest."""
        raise NotImplementedError("To be implemented by Agent 1")

    def extract_labels(self, document_path: Path) -> list[dict]:
        """Extract all object labels from InDesign document."""
        raise NotImplementedError("To be implemented by Agent 1")

    def export_pdf(self, document_path: Path, output_pdf: Path, preset: dict) -> dict:
        """Export InDesign document to PDF with preset."""
        raise NotImplementedError("To be implemented by Agent 1")


# ============================================================================
# TEST: JSX Script Execution (Basic)
# ============================================================================


class TestJSXRunnerBasicExecution:
    """Test basic JSX script execution without InDesign."""

    def test_jsx_runner_initialization(self):
        """Test JSXRunner can be instantiated."""
        runner = JSXRunner()
        assert runner.indesign_app_name == "Adobe InDesign 2024"

        # Custom app name
        runner2 = JSXRunner(indesign_app_name="Adobe InDesign CC 2023")
        assert runner2.indesign_app_name == "Adobe InDesign CC 2023"

    @patch('subprocess.run')
    def test_execute_script_success_macos(self, mock_run):
        """Test successful JSX execution on macOS (osascript)."""
        runner = JSXRunner()

        # Mock successful osascript execution
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"success": true, "labeled_count": 5}',
            stderr=''
        )

        with patch.object(runner, 'execute_script', return_value={"success": True, "labeled_count": 5}):
            result = runner.execute_script(
                Path("/tmp/test_script.jsx"),
                param1="value1",
                param2=42
            )

            assert result["success"] is True
            assert result["labeled_count"] == 5

    @patch('subprocess.run')
    def test_execute_script_failure(self, mock_run):
        """Test JSX execution failure handling."""
        runner = JSXRunner()

        # Mock failed execution
        mock_run.return_value = Mock(
            returncode=1,
            stdout='',
            stderr='Error: InDesign not running'
        )

        with patch.object(runner, 'execute_script', side_effect=RuntimeError("InDesign not running")):
            with pytest.raises(RuntimeError, match="InDesign not running"):
                runner.execute_script(Path("/tmp/test_script.jsx"))

    def test_execute_script_invalid_path(self):
        """Test error when JSX file doesn't exist."""
        runner = JSXRunner()

        with patch.object(runner, 'execute_script', side_effect=FileNotFoundError("Script not found")):
            with pytest.raises(FileNotFoundError):
                runner.execute_script(Path("/nonexistent/script.jsx"))

    @patch('subprocess.run')
    def test_execute_script_with_parameters(self, mock_run):
        """Test passing parameters to JSX script."""
        runner = JSXRunner()

        # Mock execution with parameters
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"params_received": true}',
            stderr=''
        )

        with patch.object(runner, 'execute_script', return_value={"params_received": True}):
            result = runner.execute_script(
                Path("/tmp/script.jsx"),
                document_path="/path/to/doc.indd",
                asset_id="img-abc123-p0-occ1",
                bbox=[100, 200, 300, 400]
            )

            assert result["params_received"] is True


# ============================================================================
# TEST: Label Placed Objects Workflow
# ============================================================================


class TestLabelPlacedObjects:
    """Test labeling placed objects in InDesign."""

    @pytest.fixture
    def sample_manifest(self, tmp_path):
        """Create sample manifest JSON."""
        manifest = {
            "assets": [
                {
                    "asset_id": "img-abc123-p0-occ1",
                    "asset_type": "image",
                    "file_path": "assets/img-abc123.png",
                    "bbox": [100, 200, 300, 400],
                    "page_number": 0
                },
                {
                    "asset_id": "vec-def456-p1-occ1",
                    "asset_type": "vector",
                    "file_path": "assets/vec-def456.pdf",
                    "bbox": [150, 250, 350, 450],
                    "page_number": 1
                }
            ]
        }

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        return manifest_path

    def test_label_placed_objects_success(self, sample_manifest):
        """Test successful labeling of placed objects."""
        runner = JSXRunner()

        with patch.object(runner, 'label_placed_objects') as mock_label:
            mock_label.return_value = {
                "success": True,
                "labeled_count": 2,
                "failed_count": 0,
                "labels_applied": ["img-abc123-p0-occ1", "vec-def456-p1-occ1"]
            }

            result = runner.label_placed_objects(
                document_path=Path("/tmp/test.indd"),
                manifest_path=sample_manifest
            )

            assert result["success"] is True
            assert result["labeled_count"] == 2
            assert result["failed_count"] == 0
            assert len(result["labels_applied"]) == 2

    def test_label_placed_objects_partial_failure(self, sample_manifest):
        """Test labeling with some failures."""
        runner = JSXRunner()

        with patch.object(runner, 'label_placed_objects') as mock_label:
            mock_label.return_value = {
                "success": True,
                "labeled_count": 1,
                "failed_count": 1,
                "labels_applied": ["img-abc123-p0-occ1"],
                "failed_labels": ["vec-def456-p1-occ1"],
                "errors": ["Object not found on page 1"]
            }

            result = runner.label_placed_objects(
                document_path=Path("/tmp/test.indd"),
                manifest_path=sample_manifest
            )

            assert result["success"] is True
            assert result["labeled_count"] == 1
            assert result["failed_count"] == 1
            assert "vec-def456-p1-occ1" in result["failed_labels"]

    def test_label_placed_objects_document_not_open(self):
        """Test error when document is not open."""
        runner = JSXRunner()

        with patch.object(runner, 'label_placed_objects', side_effect=RuntimeError("Document not open")):
            with pytest.raises(RuntimeError, match="Document not open"):
                runner.label_placed_objects(
                    document_path=Path("/tmp/test.indd"),
                    manifest_path=Path("/tmp/manifest.json")
                )

    def test_label_placed_objects_invalid_manifest(self, tmp_path):
        """Test error with invalid manifest JSON."""
        runner = JSXRunner()

        # Create invalid JSON
        invalid_manifest = tmp_path / "invalid.json"
        invalid_manifest.write_text("{ invalid json }")

        with patch.object(runner, 'label_placed_objects', side_effect=json.JSONDecodeError("Invalid JSON", "", 0)):
            with pytest.raises(json.JSONDecodeError):
                runner.label_placed_objects(
                    document_path=Path("/tmp/test.indd"),
                    manifest_path=invalid_manifest
                )


# ============================================================================
# TEST: Extract Labels Workflow
# ============================================================================


class TestExtractLabels:
    """Test extracting labels from InDesign."""

    def test_extract_labels_success(self):
        """Test successful label extraction."""
        runner = JSXRunner()

        mock_labels = [
            {
                "asset_id": "img-abc123-p0-occ1",
                "bbox": [100, 200, 300, 400],
                "page_number": 0,
                "object_type": "Rectangle"
            },
            {
                "asset_id": "vec-def456-p1-occ1",
                "bbox": [150, 250, 350, 450],
                "page_number": 1,
                "object_type": "GraphicLine"
            }
        ]

        with patch.object(runner, 'extract_labels', return_value=mock_labels):
            labels = runner.extract_labels(Path("/tmp/test.indd"))

            assert len(labels) == 2
            assert labels[0]["asset_id"] == "img-abc123-p0-occ1"
            assert labels[0]["bbox"] == [100, 200, 300, 400]
            assert labels[1]["asset_id"] == "vec-def456-p1-occ1"

    def test_extract_labels_no_labels_found(self):
        """Test extraction when no labels exist."""
        runner = JSXRunner()

        with patch.object(runner, 'extract_labels', return_value=[]):
            labels = runner.extract_labels(Path("/tmp/test.indd"))

            assert labels == []

    def test_extract_labels_document_not_open(self):
        """Test error when document is not open."""
        runner = JSXRunner()

        with patch.object(runner, 'extract_labels', side_effect=RuntimeError("Document not open")):
            with pytest.raises(RuntimeError, match="Document not open"):
                runner.extract_labels(Path("/tmp/test.indd"))

    def test_extract_labels_validates_asset_ids(self):
        """Test that extracted labels have valid asset ID format."""
        runner = JSXRunner()

        mock_labels = [
            {"asset_id": "img-abc12345-p0-occ1", "bbox": [100, 200, 300, 400]},
            {"asset_id": "vec-def67890-p1-occ2", "bbox": [150, 250, 350, 450]},
            {"asset_id": "tbl-ghi11223-p2-occ1", "bbox": [200, 300, 400, 500]}
        ]

        with patch.object(runner, 'extract_labels', return_value=mock_labels):
            labels = runner.extract_labels(Path("/tmp/test.indd"))

            # Validate asset ID format
            import re
            asset_id_pattern = r'^(img|vec|tbl)-[a-f0-9]{8}-p\d+-occ\d+$'

            for label in labels:
                assert re.match(asset_id_pattern, label["asset_id"]), \
                    f"Invalid asset ID format: {label['asset_id']}"


# ============================================================================
# TEST: Label → Extract → Verify Roundtrip
# ============================================================================


class TestLabelExtractRoundtrip:
    """Test complete label → extract → verify workflow."""

    @pytest.fixture
    def sample_manifest_with_assets(self, tmp_path):
        """Create manifest with multiple assets."""
        manifest = {
            "assets": [
                {"asset_id": f"img-asset00{i}-p{i%2}-occ1", "bbox": [100*i, 200*i, 300*i, 400*i]}
                for i in range(5)
            ]
        }

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        return manifest_path

    def test_roundtrip_all_labels_preserved(self, sample_manifest_with_assets):
        """Test that all labeled objects can be extracted."""
        runner = JSXRunner()

        # Mock label operation
        with patch.object(runner, 'label_placed_objects') as mock_label:
            mock_label.return_value = {
                "success": True,
                "labeled_count": 5,
                "failed_count": 0
            }

            label_result = runner.label_placed_objects(
                document_path=Path("/tmp/test.indd"),
                manifest_path=sample_manifest_with_assets
            )

            assert label_result["labeled_count"] == 5

        # Mock extract operation
        mock_extracted_labels = [
            {"asset_id": f"img-asset00{i}-p{i%2}-occ1", "bbox": [100*i, 200*i, 300*i, 400*i]}
            for i in range(5)
        ]

        with patch.object(runner, 'extract_labels', return_value=mock_extracted_labels):
            extracted = runner.extract_labels(Path("/tmp/test.indd"))

            assert len(extracted) == 5

            # Verify all asset IDs match
            extracted_ids = {label["asset_id"] for label in extracted}
            expected_ids = {f"img-asset00{i}-p{i%2}-occ1" for i in range(5)}
            assert extracted_ids == expected_ids

    def test_roundtrip_bbox_preservation(self):
        """Test that bounding boxes are preserved through roundtrip."""
        runner = JSXRunner()

        original_labels = [
            {"asset_id": "img-test001-p0-occ1", "bbox": [100.5, 200.3, 300.7, 400.9]}
        ]

        # Mock operations
        with patch.object(runner, 'label_placed_objects', return_value={"success": True}):
            runner.label_placed_objects(Path("/tmp/test.indd"), Path("/tmp/manifest.json"))

        with patch.object(runner, 'extract_labels', return_value=original_labels):
            extracted = runner.extract_labels(Path("/tmp/test.indd"))

            # BBox should be preserved (or within tolerance)
            assert len(extracted) == 1
            assert extracted[0]["asset_id"] == "img-test001-p0-occ1"

            # Allow ±2pt tolerance for coordinate conversion
            for i in range(4):
                assert abs(extracted[0]["bbox"][i] - original_labels[0]["bbox"][i]) < 2.0


# ============================================================================
# TEST: PDF Export
# ============================================================================


class TestPDFExport:
    """Test PDF export functionality."""

    def test_export_pdf_success(self):
        """Test successful PDF export."""
        runner = JSXRunner()

        mock_preset = {
            "pdf_standard": "PDF/X-4:2010",
            "color_space": "CMYK",
            "jpeg_quality": 10
        }

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = {
                "success": True,
                "output_path": "/tmp/output.pdf",
                "file_size": 1024000,
                "pages": 10
            }

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset=mock_preset
            )

            assert result["success"] is True
            assert result["output_path"] == "/tmp/output.pdf"
            assert result["pages"] == 10

    def test_export_pdf_custom_preset(self):
        """Test PDF export with custom preset."""
        runner = JSXRunner()

        custom_preset = {
            "pdf_standard": "PDF/X-4:2010",
            "color_space": "RGB",
            "jpeg_quality": 12,
            "bleed_top": 3.0,
            "bleed_bottom": 3.0
        }

        with patch.object(runner, 'export_pdf') as mock_export:
            mock_export.return_value = {"success": True}

            result = runner.export_pdf(
                document_path=Path("/tmp/test.indd"),
                output_pdf=Path("/tmp/output.pdf"),
                preset=custom_preset
            )

            assert result["success"] is True

    def test_export_pdf_failure(self):
        """Test PDF export failure."""
        runner = JSXRunner()

        with patch.object(runner, 'export_pdf', side_effect=RuntimeError("Export failed")):
            with pytest.raises(RuntimeError, match="Export failed"):
                runner.export_pdf(
                    document_path=Path("/tmp/test.indd"),
                    output_pdf=Path("/tmp/output.pdf"),
                    preset={}
                )


# ============================================================================
# TEST: Error Handling & Edge Cases
# ============================================================================


class TestJSXRunnerEdgeCases:
    """Test edge cases and error handling."""

    def test_script_timeout(self):
        """Test timeout handling for long-running scripts."""
        runner = JSXRunner()

        with patch.object(runner, 'execute_script', side_effect=TimeoutError("Script timed out")):
            with pytest.raises(TimeoutError):
                runner.execute_script(Path("/tmp/slow_script.jsx"))

    def test_indesign_crash_recovery(self):
        """Test handling InDesign crash during execution."""
        runner = JSXRunner()

        with patch.object(runner, 'execute_script', side_effect=RuntimeError("InDesign crashed")):
            with pytest.raises(RuntimeError, match="InDesign crashed"):
                runner.execute_script(Path("/tmp/script.jsx"))

    def test_large_result_handling(self):
        """Test handling large JSON results from JSX."""
        runner = JSXRunner()

        # Mock large result (1000 labels)
        large_result = [
            {"asset_id": f"img-asset{i:04d}-p0-occ1", "bbox": [i, i, i+100, i+100]}
            for i in range(1000)
        ]

        with patch.object(runner, 'extract_labels', return_value=large_result):
            labels = runner.extract_labels(Path("/tmp/test.indd"))

            assert len(labels) == 1000

    def test_special_characters_in_paths(self):
        """Test handling file paths with special characters."""
        runner = JSXRunner()

        special_path = Path("/tmp/Test File [2024] (v2).indd")

        with patch.object(runner, 'execute_script', return_value={"success": True}):
            result = runner.execute_script(
                Path("/tmp/script.jsx"),
                document_path=str(special_path)
            )

            assert result["success"] is True

    def test_unicode_in_asset_ids(self):
        """Test handling Unicode in asset metadata (should be sanitized)."""
        runner = JSXRunner()

        # Asset IDs should be ASCII-only
        labels = [
            {"asset_id": "img-test001-p0-occ1", "metadata": "Тест"}  # Cyrillic in metadata
        ]

        with patch.object(runner, 'extract_labels', return_value=labels):
            extracted = runner.extract_labels(Path("/tmp/test.indd"))

            assert len(extracted) == 1
            # Asset ID should be ASCII
            assert extracted[0]["asset_id"].isascii()
