"""Tests for the audit trail generator."""

import json
from pathlib import Path

from kps.core import Asset, AssetLedger, AssetType, BBox
from kps.qa.audit_trail import AuditTrailGenerator
from kps.qa.completeness_checker import CompletenessReport
from kps.qa.visual_diff import VisualDiffMetrics, VisualDiffReport


def _make_asset(idx: int) -> Asset:
    asset_id = f"img-{idx:03d}-p0-occ1"
    sha256 = (asset_id.encode("utf-8").hex() * 4)[:64]
    bbox = BBox(0, 0, 100, 120)
    return Asset(
        asset_id=asset_id,
        asset_type=AssetType.IMAGE,
        sha256=sha256,
        page_number=0,
        bbox=bbox,
        ctm=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        file_path=Path("assets") / f"{asset_id}.png",
        occurrence=1,
        anchor_to="p.test.001",
        image_width=600,
        image_height=720,
    )


def _dummy_report(name: str):
    class DummyReport:
        def __init__(self, name: str):
            self.passed = False
            self.errors = [f"{name} error"]
            self.warnings = [f"{name} warning"]
            self.recommendations = [f"{name} recommendation"]

        def to_dict(self):
            return {
                "passed": self.passed,
                "errors": self.errors,
                "warnings": self.warnings,
            }

    return DummyReport(name)


def test_generate_audit_payload(tmp_path: Path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 test")

    output_pdf = tmp_path / "output.pdf"
    output_pdf.write_bytes(b"%PDF-1.4 output")

    output_dir = tmp_path / "artifacts"
    output_dir.mkdir()
    (output_dir / "preview.png").write_bytes(b"png")

    assets = [_make_asset(1), _make_asset(2)]
    ledger = AssetLedger(assets=assets, source_pdf=source_pdf, total_pages=1)

    placed_labels = [{"asset_id": assets[0].asset_id}]

    class FakeTranslationResult:
        detected_source_language = "ru"
        total_cost = 1.23
        total_input_tokens = 1000
        total_output_tokens = 800

        def __init__(self):
            self.translations = {
                "en": type("Translation", (), {"segments": ["foo", "bar"]})()
            }

    translation_result = FakeTranslationResult()

    completeness = CompletenessReport(
        passed=True,
        coverage_percentage=50.0,
        total_assets=2,
        placed_assets=1,
        missing_assets=[assets[1].asset_id],
    )

    visual_report = VisualDiffReport(
        passed=False,
        metrics=VisualDiffMetrics(
            diff_ratio=0.05,
            differing_pixels=10,
            total_mask_pixels=200,
            pixel_threshold=10,
            mean_difference=5.0,
            max_difference=12.0,
        ),
        warnings=["visual warning"],
        recommendations=["visual recommendation"],
        diff_image=None,
    )

    qa_reports = {
        "completeness": completeness,
        "visual_diff": visual_report,
        "dpi": _dummy_report("dpi"),
    }

    generator = AuditTrailGenerator(pipeline_version="2.1.0")
    audit = generator.generate(
        source_pdf=source_pdf,
        output_pdf=output_pdf,
        output_dir=output_dir,
        ledger=ledger,
        placed_labels=placed_labels,
        translation_result=translation_result,
        qa_reports=qa_reports,
        extra_metadata={"env": "test"},
    )

    assert audit["pipeline_version"] == "2.1.0"
    assert audit["source"]["path"] == str(source_pdf)
    assert audit["extraction"]["total_assets"] == 2
    assert "qa" in audit and "completeness" in audit["qa"]
    assert audit["translation"]["detected_source_language"] == "ru"
    assert audit["extra"]["env"] == "test"

    destination = tmp_path / "audit.json"
    generator.write_json(audit, destination)

    loaded = json.loads(destination.read_text())
    assert loaded["qa"]["visual_diff"]["passed"] is False
