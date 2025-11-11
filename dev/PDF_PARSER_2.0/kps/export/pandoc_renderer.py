"""
Pandoc renderer for DOCX/PDF export.

Provides:
- DOCX rendering with reference.docx styling
- PDF rendering via HTML/CSS (WeasyPrint)
- PDF rendering via LaTeX (optional, requires TeX)
"""

import sys
import shutil
import subprocess
from pathlib import Path


def _need(tool: str, hint: str):
    """Check if a command-line tool is available."""
    if not shutil.which(tool):
        sys.exit(f"{tool} не найден. {hint}")


def render_docx(md_path: str, out_docx: str, reference_docx: str) -> None:
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
    cmd = [
        "pandoc",
        str(md),
        "--reference-doc=" + str(ref),
        "--toc",
        "--toc-depth=3",
        "-o",
        str(out),
    ]
    subprocess.check_call(cmd)


def render_pdf_via_html(html_path: str, css_path: str, out_pdf: str) -> None:
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
    cmd = ["weasyprint", str(html), str(out), "-s", str(css)]
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
