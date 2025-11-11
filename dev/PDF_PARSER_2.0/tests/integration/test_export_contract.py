"""Tests for style-contract-aware export helpers."""

from pathlib import Path

import kps.export.pandoc_renderer as renderer
from kps.export import (
    load_style_contract,
    render_docx_with_contract,
    render_pdf_with_contract,
)


def test_render_docx_uses_reference_from_contract(monkeypatch, tmp_path):
    contract = load_style_contract("styles/style_map.yml")
    md = tmp_path / "doc.md"
    md.write_text("# Heading\n\nBody", encoding="utf-8")

    calls = []
    monkeypatch.setattr(renderer, "_need", lambda *args, **kwargs: None)
    monkeypatch.setattr(renderer.subprocess, "check_call", lambda cmd: calls.append(cmd))

    out_docx = tmp_path / "out.docx"
    render_docx_with_contract(str(md), str(out_docx), contract)

    assert calls, "Pandoc should be invoked"
    cmd = calls[0]
    assert cmd[0] == "pandoc"
    reference_flag = next((arg for arg in cmd if arg.startswith("--reference-doc=")), None)
    reference_rel = contract["docx"]["reference_docx"]
    expected = str((Path(contract["_base_dir"]) / reference_rel).resolve())
    assert reference_flag == f"--reference-doc={expected}"


def test_render_pdf_uses_css_from_contract(monkeypatch, tmp_path):
    contract = load_style_contract("styles/style_map.yml")
    html = tmp_path / "doc.html"
    html.write_text("<h1>Heading</h1>", encoding="utf-8")

    calls = []
    monkeypatch.setattr(renderer, "_need", lambda *args, **kwargs: None)
    monkeypatch.setattr(renderer.subprocess, "check_call", lambda cmd: calls.append(cmd))

    out_pdf = tmp_path / "out.pdf"
    render_pdf_with_contract(str(html), str(out_pdf), contract)

    assert calls, "WeasyPrint should be invoked"
    cmd = calls[0]
    assert cmd[0] == "weasyprint"
    css_idx = cmd.index("-s") + 1
    css_rel = contract["pdf"]["css"]
    expected_css = str((Path(contract["_base_dir"]) / css_rel).resolve())
    assert cmd[css_idx] == expected_css
