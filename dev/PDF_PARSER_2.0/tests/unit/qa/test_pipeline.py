"""Unit tests for the fail-closed QA pipeline."""

from types import SimpleNamespace
from pathlib import Path

from kps.core import Asset, AssetLedger, AssetType, BBox
from kps.qa.pipeline import QAPipeline
from kps.qa.completeness_checker import CompletenessReport


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


class StubCompletenessChecker:
    def __init__(self, passed: bool = True):
        self.called = False
        self.report = CompletenessReport(
            passed=passed,
            coverage_percentage=100.0 if passed else 50.0,
            total_assets=2,
            placed_assets=2 if passed else 1,
            missing_assets=[] if passed else ["img-001"],
        )

    def check_completeness(self, *_, **__):
        self.called = True
        return self.report


class StubGeometryValidator:
    def __init__(self, passed: bool = True):
        self.called = False
        self.passed = passed

    def validate_geometry(self, *_, **__):
        self.called = True
        return SimpleNamespace(
            passed=self.passed,
            warnings=[],
            recommendations=[],
        )


class StubVisualDiffer:
    def __init__(self, passed: bool = True):
        self.called = False
        self.passed = passed

    def compare_documents(self, *_, **__):
        self.called = True
        page_report = SimpleNamespace(
            passed=self.passed,
            warnings=["visual warning"] if not self.passed else [],
            recommendations=["visual recommendation"] if not self.passed else [],
            page_index=0,
        )
        return self.passed, [page_report]


class StubDPIValidator:
    def __init__(self, passed: bool = True):
        self.called = False
        self.passed = passed

    def validate_dpi(self, *_, **__):
        self.called = True
        return SimpleNamespace(
            passed=self.passed,
            warnings=[],
            errors=[] if self.passed else ["dpi error"],
            recommendations=[],
        )


class StubFontAuditor:
    def __init__(self, passed: bool = True):
        self.called = False
        self.passed = passed

    def audit_fonts(self, *_):
        self.called = True
        return SimpleNamespace(
            passed=self.passed,
            warnings=[],
            errors=[] if self.passed else ["font error"],
            recommendations=[],
        )


class StubColorAuditor:
    def __init__(self, passed: bool = True):
        self.called = False
        self.passed = passed

    def audit_colors(self, *_ , **__):
        self.called = True
        return SimpleNamespace(
            passed=self.passed,
            warnings=[],
            errors=[] if self.passed else ["color error"],
            recommendations=[],
        )


def _ledger(tmp_path: Path) -> AssetLedger:
    assets = [_make_asset(1), _make_asset(2)]
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF")
    return AssetLedger(assets=assets, source_pdf=source_pdf, total_pages=1)


def _setup_files(tmp_path: Path):
    output_pdf = tmp_path / "output.pdf"
    output_pdf.write_bytes(b"%PDF-output")
    reference_pdf = tmp_path / "reference.pdf"
    reference_pdf.write_bytes(b"%PDF-reference")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    return reference_pdf, output_pdf, output_dir


def test_pipeline_success(tmp_path: Path):
    ledger = _ledger(tmp_path)
    reference_pdf, output_pdf, output_dir = _setup_files(tmp_path)
    placed_labels = [{"asset_id": ledger.assets[0].asset_id}, {"asset_id": ledger.assets[1].asset_id}]

    pipeline = QAPipeline(
        completeness_checker=StubCompletenessChecker(passed=True),
        geometry_validator=StubGeometryValidator(passed=True),
        visual_differ=StubVisualDiffer(passed=True),
        dpi_validator=StubDPIValidator(passed=True),
        font_auditor=StubFontAuditor(passed=True),
        color_auditor=StubColorAuditor(passed=True),
    )

    result = pipeline.run(
        source_pdf=ledger.source_pdf,
        reference_pdf=reference_pdf,
        output_pdf=output_pdf,
        output_dir=output_dir,
        ledger=ledger,
        placed_labels=placed_labels,
        page_dimensions=[(100.0, 120.0)],
        translation_result=None,
    )

    assert result.passed
    assert result.failed_check is None
    assert set(result.qa_reports.keys()) == {"completeness", "geometry", "visual_diff", "dpi", "font", "color"}
    assert (output_dir / "audit.json").exists()


def test_pipeline_stops_on_geometry_failure(tmp_path: Path):
    ledger = _ledger(tmp_path)
    reference_pdf, output_pdf, output_dir = _setup_files(tmp_path)
    placed_labels = [{"asset_id": ledger.assets[0].asset_id}]

    completeness = StubCompletenessChecker(passed=True)
    geometry = StubGeometryValidator(passed=False)
    visual = StubVisualDiffer(passed=True)
    dpi = StubDPIValidator(passed=True)
    font = StubFontAuditor(passed=True)
    color = StubColorAuditor(passed=True)

    pipeline = QAPipeline(
        completeness_checker=completeness,
        geometry_validator=geometry,
        visual_differ=visual,
        dpi_validator=dpi,
        font_auditor=font,
        color_auditor=color,
    )

    result = pipeline.run(
        source_pdf=ledger.source_pdf,
        reference_pdf=reference_pdf,
        output_pdf=output_pdf,
        output_dir=output_dir,
        ledger=ledger,
        placed_labels=placed_labels,
        page_dimensions=[(100.0, 120.0)],
    )

    assert not result.passed
    assert result.failed_check == "geometry"
    assert "geometry" in result.qa_reports
    assert not visual.called
    assert not dpi.called
    assert not font.called
    assert not color.called


def test_pipeline_handles_completeness_failure(tmp_path: Path):
    ledger = _ledger(tmp_path)
    _, output_pdf, output_dir = _setup_files(tmp_path)
    placed_labels = []

    completeness = StubCompletenessChecker(passed=False)
    pipeline = QAPipeline(completeness_checker=completeness)

    result = pipeline.run(
        source_pdf=ledger.source_pdf,
        reference_pdf=None,
        output_pdf=output_pdf,
        output_dir=output_dir,
        ledger=ledger,
        placed_labels=placed_labels,
    )

    assert not result.passed
    assert result.failed_check == "completeness"
    assert set(result.qa_reports.keys()) == {"completeness"}
