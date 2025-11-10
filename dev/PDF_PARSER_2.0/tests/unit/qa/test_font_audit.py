"""Unit tests for the font auditor."""

from pathlib import Path

from kps.qa.font_audit import FontAuditor


def _font_record(
    name: str,
    *,
    font_type: str = "TrueType",
    embedded: bool = True,
    subset: bool = True,
    pages=None,
    encoding: str = "WinAnsi",
):
    return {
        "name": name,
        "font_type": font_type,
        "is_embedded": embedded,
        "is_subset": subset,
        "encoding": encoding,
        "pages": pages or [0],
        "xref": 10,
    }


def test_font_audit_passes_when_all_fonts_embedded_and_subset(tmp_path: Path):
    auditor = FontAuditor(require_subsetting=True)
    fonts = [
        _font_record("ABCDEE+Roboto-Regular"),
        _font_record("XYZABC+Roboto-Bold"),
    ]

    report = auditor.audit_fonts(tmp_path / "doc.pdf", pre_extracted=fonts)

    assert report.passed
    assert report.pdf_x_compliant
    assert report.referenced_fonts == 0
    assert "PDF/X compliant" in report.summary


def test_font_audit_detects_missing_fonts(tmp_path: Path):
    auditor = FontAuditor()
    fonts = [
        _font_record("ABCDEE+Roboto-Regular"),
        _font_record("Helvetica", embedded=False, subset=False),
    ]

    report = auditor.audit_fonts(tmp_path / "doc.pdf", pre_extracted=fonts)

    assert not report.passed
    assert report.referenced_fonts == 1
    assert report.missing_fonts
    assert any("not embedded" in err for err in report.errors)


def test_font_audit_warns_on_non_subset_when_required(tmp_path: Path):
    auditor = FontAuditor(require_subsetting=True)
    fonts = [
        _font_record("ABCDEE+Roboto-Regular"),
        _font_record("OpenSans", subset=False),
    ]

    report = auditor.audit_fonts(tmp_path / "doc.pdf", pre_extracted=fonts)

    assert report.passed
    assert not report.pdf_x_compliant
    assert any("subset" in warning for warning in report.warnings)
