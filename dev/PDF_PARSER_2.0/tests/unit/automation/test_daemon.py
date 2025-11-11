"""
Tests for DocumentDaemon.
"""

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kps.automation.daemon import DocumentDaemon
from kps.core import PipelineConfig


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        inbox = base / "inbox"
        output = base / "output"
        processed = base / "inbox/processed"
        data = base / "data"

        inbox.mkdir(parents=True)
        output.mkdir(parents=True)
        processed.mkdir(parents=True)
        data.mkdir(parents=True)

        yield {
            "inbox": inbox,
            "output": output,
            "processed": processed,
            "data": data,
            "base": base,
        }


@pytest.fixture
def mock_pipeline():
    """Mock UnifiedPipeline."""
    with patch("kps.automation.daemon.UnifiedPipeline") as MockPipeline:
        mock_instance = Mock()
        mock_instance.process.return_value = Mock(
            target_languages=["en", "fr"],
            segments_translated=10,
            cache_hit_rate=0.5,
            translation_cost=0.05,
            errors=[],
            warnings=[],
        )
        MockPipeline.return_value = mock_instance
        yield mock_instance


class TestDocumentDaemon:
    """Tests for DocumentDaemon class."""

    def test_initialization(self, temp_dirs):
        """Test daemon initialization."""
        daemon = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
            processed_dir=str(temp_dirs["processed"]),
            target_languages=["en"],
            check_interval=60,
        )

        assert daemon.inbox == temp_dirs["inbox"]
        assert daemon.output == temp_dirs["output"]
        assert daemon.target_languages == ["en"]
        assert daemon.check_interval == 60
        assert len(daemon.processed_hashes) == 0

    def test_get_file_hash(self, temp_dirs):
        """Test file hash calculation."""
        daemon = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
        )

        # Create test file
        test_file = temp_dirs["inbox"] / "test.txt"
        test_content = b"Hello, World!"
        test_file.write_bytes(test_content)

        # Calculate hash
        file_hash = daemon._get_file_hash(test_file)

        # Verify
        expected_hash = hashlib.sha256(test_content).hexdigest()
        assert file_hash == expected_hash

    def test_find_new_documents_empty(self, temp_dirs, mock_pipeline):
        """Test finding documents when inbox is empty."""
        daemon = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
        )

        new_docs = daemon._find_new_documents()
        assert len(new_docs) == 0

    def test_find_new_documents_with_files(self, temp_dirs, mock_pipeline):
        """Test finding new documents."""
        daemon = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
        )

        # Create test files
        pdf1 = temp_dirs["inbox"] / "doc1.pdf"
        pdf2 = temp_dirs["inbox"] / "doc2.pdf"
        pdf1.write_text("PDF content 1")
        pdf2.write_text("PDF content 2")

        new_docs = daemon._find_new_documents()
        assert len(new_docs) == 2
        assert pdf1 in new_docs
        assert pdf2 in new_docs

    def test_find_new_documents_ignores_processed(self, temp_dirs, mock_pipeline):
        """Test that processed documents are ignored."""
        daemon = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
        )

        # Create test file
        pdf = temp_dirs["inbox"] / "doc.pdf"
        pdf.write_text("PDF content")

        # First scan - should find it
        new_docs = daemon._find_new_documents()
        assert len(new_docs) == 1

        # Add to processed
        file_hash = daemon._get_file_hash(pdf)
        daemon.processed_hashes.add(file_hash)

        # Second scan - should be ignored
        new_docs = daemon._find_new_documents()
        assert len(new_docs) == 0

    def test_save_and_load_state(self, temp_dirs, mock_pipeline):
        """Test state persistence."""
        state_file = temp_dirs["data"] / "daemon_state.txt"

        # Create daemon and add some hashes
        daemon1 = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
        )
        daemon1.state_file = state_file

        daemon1.processed_hashes.add("hash1")
        daemon1.processed_hashes.add("hash2")
        daemon1._save_state()

        # Create new daemon and load state
        daemon2 = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
        )
        daemon2.state_file = state_file
        loaded_hashes = daemon2._load_state()

        assert "hash1" in loaded_hashes
        assert "hash2" in loaded_hashes
        assert len(loaded_hashes) == 2

    def test_process_document_success(self, temp_dirs, mock_pipeline):
        """Test successful document processing."""
        daemon = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
            processed_dir=str(temp_dirs["processed"]),
        )

        # Create test file
        pdf = temp_dirs["inbox"] / "test.pdf"
        pdf.write_text("PDF content")

        # Process
        daemon._process_document(pdf)

        # Verify
        assert not pdf.exists()  # moved from inbox
        assert (temp_dirs["processed"] / "test.pdf").exists()  # moved to processed
        assert len(daemon.processed_hashes) == 1
        mock_pipeline.process.assert_called_once()

    def test_process_document_failure(self, temp_dirs, mock_pipeline):
        """Test document processing with pipeline failure."""
        # Make pipeline raise an error
        mock_pipeline.process.side_effect = RuntimeError("Pipeline error")

        daemon = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
            processed_dir=str(temp_dirs["processed"]),
        )

        # Create test file
        pdf = temp_dirs["inbox"] / "test.pdf"
        pdf.write_text("PDF content")

        # Process should raise
        with pytest.raises(RuntimeError):
            daemon._process_document(pdf)

        # File should be moved to failed folder
        failed_path = temp_dirs["inbox"] / "failed" / "test.pdf"
        assert failed_path.exists()
        assert daemon.stats["total_errors"] == 1

    def test_run_once_no_documents(self, temp_dirs, mock_pipeline):
        """Test run_once with no new documents."""
        daemon = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
        )

        daemon.run_once()

        # Pipeline should not be called
        mock_pipeline.process.assert_not_called()

    def test_run_once_with_documents(self, temp_dirs, mock_pipeline):
        """Test run_once with new documents."""
        daemon = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
            processed_dir=str(temp_dirs["processed"]),
        )

        # Create test files
        pdf1 = temp_dirs["inbox"] / "doc1.pdf"
        pdf2 = temp_dirs["inbox"] / "doc2.pdf"
        pdf1.write_text("Content 1")
        pdf2.write_text("Content 2")

        # Run once
        daemon.run_once()

        # Both should be processed
        assert mock_pipeline.process.call_count == 2
        assert daemon.stats["total_processed"] == 2
        assert len(daemon.processed_hashes) == 2

    def test_run_once_continues_after_error(self, temp_dirs, mock_pipeline):
        """Test that run_once continues processing after one document fails."""
        # Make first call fail, second succeed
        mock_pipeline.process.side_effect = [
            RuntimeError("Error"),
            Mock(
                target_languages=["en"],
                segments_translated=5,
                cache_hit_rate=0.5,
                translation_cost=0.02,
                errors=[],
                warnings=[],
            ),
        ]

        daemon = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
            processed_dir=str(temp_dirs["processed"]),
        )

        # Create test files
        pdf1 = temp_dirs["inbox"] / "doc1.pdf"
        pdf2 = temp_dirs["inbox"] / "doc2.pdf"
        pdf1.write_text("Content 1")
        pdf2.write_text("Content 2")

        # Run once
        daemon.run_once()

        # Second file should still be processed
        assert mock_pipeline.process.call_count == 2
        assert daemon.stats["total_processed"] == 1
        assert daemon.stats["total_errors"] == 1

    def test_statistics_tracking(self, temp_dirs, mock_pipeline):
        """Test that statistics are tracked correctly."""
        daemon = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
            processed_dir=str(temp_dirs["processed"]),
        )

        # Create and process a document
        pdf = temp_dirs["inbox"] / "doc.pdf"
        pdf.write_text("Content")

        daemon.run_once()

        assert daemon.stats["total_processed"] == 1
        assert daemon.stats["total_errors"] == 0


class TestDocumentDaemonIntegration:
    """Integration tests for DocumentDaemon."""

    def test_full_workflow(self, temp_dirs, mock_pipeline):
        """Test complete workflow: find → process → move → state."""
        daemon = DocumentDaemon(
            inbox_dir=str(temp_dirs["inbox"]),
            output_dir=str(temp_dirs["output"]),
            processed_dir=str(temp_dirs["processed"]),
            target_languages=["en", "fr"],
        )

        # Create test document
        pdf = temp_dirs["inbox"] / "pattern.pdf"
        pdf.write_text("Knitting pattern content")
        original_hash = daemon._get_file_hash(pdf)

        # Run daemon once
        daemon.run_once()

        # Verify:
        # 1. File moved from inbox to processed
        assert not pdf.exists()
        assert (temp_dirs["processed"] / "pattern.pdf").exists()

        # 2. Hash recorded
        assert original_hash in daemon.processed_hashes

        # 3. Pipeline called with correct args
        mock_pipeline.process.assert_called_once()
        call_args = mock_pipeline.process.call_args
        assert call_args.kwargs["target_languages"] == ["en", "fr"]

        # 4. Stats updated
        assert daemon.stats["total_processed"] == 1

        # Run again - should not reprocess
        daemon.run_once()
        assert mock_pipeline.process.call_count == 1  # still 1, not 2
