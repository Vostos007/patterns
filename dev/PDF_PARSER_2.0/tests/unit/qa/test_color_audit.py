"""Unit tests for the color auditor."""

from pathlib import Path

from kps.qa.color_audit import ColorAuditor


def test_color_audit_passes_with_matching_colorspaces(tmp_path: Path):
    auditor = ColorAuditor()
    records = [
        {
            "asset_id": "img-001",
            "page": 0,
            "source_colorspace": "cmyk",
            "target_colorspace": "cmyk",
            "has_icc": True,
        },
        {
            "asset_id": "img-002",
            "page": 1,
            "source_colorspace": "rgb",
            "target_colorspace": "rgb",
            "has_icc": False,
        },
    ]

    report = auditor.audit_colors(None, tmp_path / "doc.pdf", pre_extracted=records)

    assert report.passed
    assert not report.errors
    assert report.colorspace_counts["cmyk"] == 1
    assert report.colorspace_counts["rgb"] == 1


def test_color_audit_detects_conversion(tmp_path: Path):
    auditor = ColorAuditor()
    records = [
        {
            "asset_id": "img-003",
            "page": 2,
            "source_colorspace": "cmyk",
            "target_colorspace": "rgb",
            "has_icc": False,
        }
    ]

    report = auditor.audit_colors(None, tmp_path / "doc.pdf", pre_extracted=records)

    assert not report.passed
    assert report.errors
    assert report.conversions
    assert any("conversion" in error.lower() for error in report.errors)


def test_color_audit_warns_on_missing_icc(tmp_path: Path):
    auditor = ColorAuditor(require_icc_for_cmyk=True)
    records = [
        {
            "asset_id": "img-004",
            "page": 3,
            "source_colorspace": "cmyk",
            "target_colorspace": "cmyk",
            "has_icc": False,
        }
    ]

    report = auditor.audit_colors(None, tmp_path / "doc.pdf", pre_extracted=records)

    assert not report.passed
    assert report.missing_icc
    assert any("icc" in warning.lower() for warning in report.warnings)
