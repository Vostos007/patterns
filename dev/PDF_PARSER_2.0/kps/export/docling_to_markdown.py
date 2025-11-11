"""
Docling to Markdown/HTML converter.

Reads documents via Docling (PDF/DOCX/images) and exports to Markdown,
then converts Markdown to HTML5 via Pandoc.
"""

import sys
from pathlib import Path


def doc_to_markdown(input_path: str, md_out: str) -> None:
    """
    Читает файл любого поддерживаемого Docling формата (PDF/DOCX/изображения),
    сохраняет нормализованный Markdown по структурным элементам.

    Args:
        input_path: Path to input document (PDF, DOCX, image, etc.)
        md_out: Path to output Markdown file

    Raises:
        SystemExit: If Docling is not installed or file not found
    """
    try:
        import docling  # type: ignore
        from docling.document_converter import DocumentConverter
    except Exception as e:
        sys.exit("Docling не установлен. Установите: pip install docling\n" + str(e))

    inp = Path(input_path)
    if not inp.exists():
        sys.exit(f"Файл не найден: {inp}")

    conv = DocumentConverter()
    result = conv.convert(str(inp))
    md = result.document.export_to_markdown()

    Path(md_out).parent.mkdir(parents=True, exist_ok=True)
    Path(md_out).write_text(md, encoding="utf-8")


def markdown_to_html(md_path: str, html_out: str) -> None:
    """
    Преобразует Markdown в standalone HTML5 через Pandoc.

    Args:
        md_path: Path to input Markdown file
        html_out: Path to output HTML file

    Raises:
        SystemExit: If pandoc is not found
    """
    import shutil
    import subprocess

    if not shutil.which("pandoc"):
        sys.exit(
            "pandoc не найден. Установите его: https://pandoc.org/installing.html"
        )

    cmd = ["pandoc", md_path, "-t", "html5", "-s", "-o", html_out]
    subprocess.check_call(cmd)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "Использование: python -m kps.export.docling_to_markdown INPUT_FILE OUT_MD OUT_HTML"
        )
        sys.exit(2)
    src, md, html = sys.argv[1], sys.argv[2], sys.argv[3]
    doc_to_markdown(src, md)
    markdown_to_html(md, html)
    print("OK:", md, html)
