"""
Pandoc renderer for DOCX/PDF export.

Provides:
- DOCX rendering with reference.docx styling
- PDF rendering via HTML/CSS (WeasyPrint)
- PDF rendering via LaTeX (optional, requires TeX)
- Style contract loader shared by CLI and tests
"""

import sys
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import yaml


def _need(tool: str, hint: str):
    """Check if a command-line tool is available."""
    if not shutil.which(tool):
        sys.exit(f"{tool} не найден. {hint}")


def render_docx(
    md_path: str,
    out_docx: str,
    reference_docx: str,
    extra_args: Optional[Iterable[str]] = None,
) -> None:
    """
    Render Markdown to DOCX using Pandoc with reference.docx styling.

    Args:
        md_path: Path to input Markdown file
        out_docx: Path to output DOCX file
        reference_docx: Path to reference.docx template with styles

    Raises:
        SystemExit: If pandoc is not found or files don't exist
    """
    _need("pandoc", "Установите Pandoc: https://pandoc.org/installing.html")
    md = Path(md_path)
    ref = Path(reference_docx)
    out = Path(out_docx)
    if not md.exists():
        sys.exit(f"Нет входного MD: {md}")
    if not ref.exists():
        sys.exit(f"Нет reference.docx: {ref}")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["pandoc", str(md)]
    default_args = ["--toc", "--toc-depth=3"]
    if extra_args:
        cmd.extend(extra_args)
    else:
        cmd.extend(default_args)
    cmd.extend(["--reference-doc=" + str(ref), "-o", str(out)])
    subprocess.check_call(cmd)


def render_pdf_via_html(
    html_path: str,
    css_path: str,
    out_pdf: str,
    extra_args: Optional[Iterable[str]] = None,
) -> None:
    """
    Render HTML to PDF using WeasyPrint with CSS Paged Media support.

    Args:
        html_path: Path to input HTML file
        css_path: Path to CSS file (pdf.css with @page rules)
        out_pdf: Path to output PDF file

    Raises:
        SystemExit: If weasyprint is not found or files don't exist
    """
    _need("weasyprint", "Установите WeasyPrint: pip install weasyprint")
    html = Path(html_path)
    css = Path(css_path)
    out = Path(out_pdf)
    if not html.exists():
        sys.exit(f"Нет входного HTML: {html}")
    if not css.exists():
        sys.exit(f"Нет css: {css}")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["weasyprint", str(html), str(out)]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(["-s", str(css)])
    subprocess.check_call(cmd)


def render_pdf_via_latex(md_path: str, out_pdf: str, engine: str = "tectonic") -> None:
    """
    Render Markdown to PDF using Pandoc with LaTeX backend.

    Args:
        md_path: Path to input Markdown file
        out_pdf: Path to output PDF file
        engine: LaTeX engine to use (tectonic, pdflatex, xelatex, lualatex)

    Raises:
        SystemExit: If pandoc or LaTeX engine is not found
    """
    _need("pandoc", "Установите Pandoc")
    md = Path(md_path)
    out = Path(out_pdf)
    if not md.exists():
        sys.exit(f"Нет входного MD: {md}")
    out.parent.mkdir(parents=True, exist_ok=True)
    if engine == "tectonic":
        _need(
            "tectonic",
            "Установите Tectonic: https://tectonic-typesetting.github.io/",
        )
    cmd = ["pandoc", str(md), "--pdf-engine=" + engine, "-o", str(out)]
    subprocess.check_call(cmd)


def load_style_contract(style_map_path: str) -> Dict[str, Any]:
    """Load YAML style map and attach its base directory."""

    path = Path(style_map_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data["_base_dir"] = str(path.parent.resolve())
    return data


def _resolve_asset(base_dir: str, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        return candidate
    return Path(base_dir) / candidate


def render_docx_with_contract(
    md_path: str,
    out_docx: str,
    contract: Dict[str, Any],
) -> None:
    docx_cfg = contract.get("docx", {})
    base_dir = contract.get("_base_dir", ".")
    reference_docx = _resolve_asset(base_dir, docx_cfg.get("reference_docx", "styles/reference.docx"))
    pandoc_args = docx_cfg.get("pandoc_args") or docx_cfg.get("args")
    render_docx(md_path, out_docx, str(reference_docx), pandoc_args)


def render_pdf_with_contract(
    html_path: str,
    out_pdf: str,
    contract: Dict[str, Any],
) -> None:
    pdf_cfg = contract.get("pdf", {})
    base_dir = contract.get("_base_dir", ".")
    css_path = _resolve_asset(base_dir, pdf_cfg.get("css", "styles/pdf.css"))
    weasy_args = pdf_cfg.get("weasyprint_args")
    render_pdf_via_html(html_path, str(css_path), out_pdf, weasy_args)


if __name__ == "__main__":
    # Пример:
    # python -m kps.export.pandoc_renderer md2docx out/sample.md out/final.docx configs/reference.docx
    # python -m kps.export.pandoc_renderer html2pdf out/sample.html out/report.pdf configs/pdf.css
    # python -m kps.export.pandoc_renderer md2pdf out/sample.md out/report.pdf --engine tectonic
    import argparse

    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)

    p_docx = sub.add_parser("md2docx")
    p_docx.add_argument("md")
    p_docx.add_argument("out_docx")
    p_docx.add_argument("reference_docx")

    p_pdf_html = sub.add_parser("html2pdf")
    p_pdf_html.add_argument("html")
    p_pdf_html.add_argument("out_pdf")
    p_pdf_html.add_argument("css")

    p_pdf_tex = sub.add_parser("md2pdf")
    p_pdf_tex.add_argument("md")
    p_pdf_tex.add_argument("out_pdf")
    p_pdf_tex.add_argument("--engine", default="tectonic")

    args = ap.parse_args()
    if args.mode == "md2docx":
        render_docx(args.md, args.out_docx, args.reference_docx)
    elif args.mode == "html2pdf":
        render_pdf_via_html(args.html, args.out_pdf, args.css)
    else:
        render_pdf_via_latex(args.md, args.out_pdf, engine=args.engine)
