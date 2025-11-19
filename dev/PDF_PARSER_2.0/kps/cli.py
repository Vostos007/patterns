"""
KPS Command Line Interface.

Provides commands for document processing, translation, and automation.
"""

import logging
from pathlib import Path
from typing import List, Optional

import typer

from kps.io.layout import IOLayout

SUPPORTED_LAYOUT_LANGS = {"ru", "en", "fr"}

app = typer.Typer(
    name="kps",
    help="Knitting Pattern System - Document processing and translation",
    add_completion=False,
)


@app.command()
def translate(
    input_file: str = typer.Argument(..., help="Input document (PDF, DOCX)"),
    languages: str = typer.Option("en,fr", "--lang", "-l", help="Target languages (comma-separated)"),
    root_dir: Optional[str] = typer.Option(
        None,
        "--root",
        "-r",
        help="Base directory containing input/inter/output structure",
        show_default=False,
    ),
    use_tmp: bool = typer.Option(False, "--tmp", help="Route outputs into an isolated tmp layout"),
    formats: str = typer.Option(
        "docx,pdf,json,markdown",
        "--format",
        "-f",
        help="Comma-separated export formats (docx,pdf,markdown,json,idml)",
    ),
    skip_translation_qa: bool = typer.Option(False, "--skip-translation-qa", help="Bypass translation QA gate"),
    glossary: Optional[str] = typer.Option(None, "--glossary", "-g", help="Glossary file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    layout_preserve: bool = typer.Option(
        False,
        "--layout-preserve",
        help="Overlay translations onto original PDF to preserve layout (ru/en/fr only)",
    ),
):
    """
    Translate a document to target languages.

    Example:
        kps translate document.pdf --lang en,fr --output ./output
    """
    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from kps.core import PipelineConfig, UnifiedPipeline, ExtractionMethod, MemoryType

    project_root = Path(__file__).resolve().parents[1]
    default_root = (project_root / "runtime").resolve()
    layout_root = Path(root_dir).expanduser().resolve() if root_dir else default_root

    typer.echo(f"Processing: {input_file}")
    typer.echo(f"Languages: {languages}")
    typer.echo(f"Root: {layout_root}{' (tmp run)' if use_tmp else ''}")

    # Parse languages
    target_langs = [lang.strip() for lang in languages.split(",") if lang.strip()]
    export_formats = [fmt.strip() for fmt in formats.split(",") if fmt.strip()]
    if not export_formats:
        export_formats = ["docx", "pdf", "json", "markdown"]

    # Create config
    config = PipelineConfig(
        extraction_method=ExtractionMethod.AUTO,
        memory_type=MemoryType.SEMANTIC,
        glossary_path=glossary or "glossary.yaml",
        export_formats=export_formats,
    )

    # Create pipeline and layout context
    pipeline = UnifiedPipeline(config)
    if skip_translation_qa:
        pipeline.translation_qa_gate = None
    layout = IOLayout(
        base_root=layout_root,
        use_tmp=use_tmp,
        publish_root=getattr(pipeline, "publish_root", None),
    )
    run_context = layout.prepare_run(Path(input_file))

    # Process
    try:
        result = pipeline.process(
            input_file=run_context.staged_input,
            target_languages=target_langs,
            output_dir=run_context.output_dir,
            run_context=run_context,
        )

        # Print results
        typer.echo("\n" + "=" * 60)
        typer.secho("✓ Translation complete!", fg=typer.colors.GREEN, bold=True)
        typer.echo("=" * 60)
        typer.echo(f"Segments translated: {result.segments_translated}")
        typer.echo(f"Cache hit rate: {result.cache_hit_rate:.0%}")
        typer.echo(f"Translation cost: ${result.translation_cost:.4f}")
        typer.echo(
            f"Input tokens: {result.total_input_tokens:,} | Output tokens: {result.total_output_tokens:,}"
        )
        typer.echo(f"Processing time: {result.processing_time:.1f}s")

        if result.output_files:
            typer.echo("\nOutput files:")
            for lang, files in result.output_files.items():
                for fmt, filepath in files.items():
                    typer.echo(f"  {lang} [{fmt}]: {filepath}")

        if result.errors:
            typer.echo("\nErrors:")
            for error in result.errors:
                typer.secho(f"  ✗ {error}", fg=typer.colors.RED)

        if result.warnings:
            typer.echo("\nWarnings:")
            for warning in result.warnings:
                typer.secho(f"  ⚠ {warning}", fg=typer.colors.YELLOW)

        if layout_preserve:
            _maybe_run_layout_preserver(run_context, target_langs)

    except Exception as e:
        typer.secho(f"✗ Error: {e}", fg=typer.colors.RED, err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(code=1)


def _maybe_run_layout_preserver(run_context, target_langs: list[str], preserve_formatting: bool = True) -> None:
    """Run layout preserver to create overlay-translated PDFs.
    
    Args:
        run_context: IO layout context
        target_langs: List of target language codes
        preserve_formatting: If True, preserve fonts, colors, bold/italic
    """
    from kps.layout_preserver import process_pdf

    requested = [lang for lang in target_langs if lang in SUPPORTED_LAYOUT_LANGS]
    if not requested:
        typer.secho(
            "⚠ Layout preserve skipped: supported languages are ru/en/fr.",
            fg=typer.colors.YELLOW,
        )
        return

    # Show clear header before starting
    typer.echo("\n" + "=" * 70)
    typer.secho("🎨 LAYOUT PRESERVATION MODE", fg=typer.colors.BLUE, bold=True)
    if preserve_formatting:
        typer.secho("   (with full formatting preservation)", fg=typer.colors.CYAN)
    typer.echo("=" * 70)
    typer.echo("Main pipeline PDFs:    " + str(Path(run_context.output_dir)))
    typer.secho("Layout-preserved PDFs: " + str(Path(run_context.output_dir) / "layout"), fg=typer.colors.GREEN, bold=True)
    typer.echo("\n💡 For best layout preservation, use PDFs from the layout/ subdirectory")
    typer.echo("=" * 70 + "\n")

    output_dir = Path(run_context.output_dir) / "layout"
    produced = process_pdf(
        Path(run_context.staged_input),
        output_dir,
        target_langs=requested,
        preserve_formatting=preserve_formatting
    )

    # Show results with clear distinction
    typer.echo("\n" + "=" * 70)
    typer.secho("✅ Layout-preserved PDFs created:", fg=typer.colors.GREEN, bold=True)
    typer.echo("=" * 70)
    for path in produced:
        typer.secho(f"  📄 {path}", fg=typer.colors.GREEN)
    
    if preserve_formatting:
        typer.echo("\n✨ Preserved:")
        typer.echo("   ✓ Font sizes (exact match)")
        typer.echo("   ✓ Text colors")
        typer.echo("   ✓ Table borders")
        typer.echo("   ✓ Bold/italic styles (if in original)")
    
    typer.echo("\n💡 Open these PDFs (not the main pipeline versions) for clean text rendering")
    typer.echo("=" * 70 + "\n")


@app.command()
def daemon(
    inbox: str = typer.Option("to_translate", "--inbox", "-i", help="Incoming directory to monitor"),
    output: str = typer.Option("translations", "--output", "-o", help="Output directory"),
    languages: str = typer.Option("en,fr", "--lang", "-l", help="Target languages (comma-separated)"),
    interval: int = typer.Option(300, "--interval", help="Check interval (seconds)"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    once: bool = typer.Option(False, "--once", help="Run once and exit"),
):
    """
    Start automatic document processing daemon.

    Monitors the incoming directory and automatically processes new documents.

    Example:
        kps daemon --inbox ./to_translate --lang en,fr --interval 300
        kps daemon --once  # Run once for testing
    """
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    from kps.automation import DocumentDaemon

    # Parse languages
    target_langs = [lang.strip() for lang in languages.split(",")]

    # Create daemon
    doc_daemon = DocumentDaemon(
        inbox_dir=inbox,
        output_dir=output,
        target_languages=target_langs,
        check_interval=interval,
    )

    if once:
        typer.echo("Running one iteration...")
        doc_daemon.run_once()
        typer.secho("✓ Done", fg=typer.colors.GREEN)
    else:
        typer.echo(f"Starting daemon (interval: {interval}s)")
        typer.echo(f"Monitoring: {inbox}")
        typer.echo("Press Ctrl+C to stop\n")
        doc_daemon.start()


@app.command()
def knowledge(
    action: str = typer.Argument(..., help="Action: add, search, list, stats"),
    path: Optional[str] = typer.Argument(None, help="File path (for 'add' action)"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Search query"),
    lang: str = typer.Option("en", "--lang", "-l", help="Language"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Category filter"),
    top_k: int = typer.Option(5, "--top", "-n", help="Number of results"),
):
    """
    Manage knowledge base.

    Actions:
        add     - Add document to knowledge base
        search  - Search knowledge base
        list    - List categories
        stats   - Show statistics

    Examples:
        kps knowledge add pattern.pdf --lang en
        kps knowledge search --query "cable stitch" --top 10
        kps knowledge stats
    """
    from kps.knowledge import KnowledgeBase

    kb = KnowledgeBase("data/knowledge.db")

    if action == "add":
        if not path:
            typer.secho("Error: path required for 'add' action", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Adding to knowledge base: {path}")
        kb.add_document(Path(path), language=lang)
        typer.secho("✓ Added successfully", fg=typer.colors.GREEN)

    elif action == "search":
        if not query:
            typer.secho("Error: --query required for 'search' action", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Searching: {query}")
        results = kb.search(query, language=lang, category=category, top_k=top_k)

        if not results:
            typer.echo("No results found")
        else:
            typer.echo(f"\nFound {len(results)} result(s):\n")
            for i, result in enumerate(results, 1):
                typer.echo(f"{i}. {result.content[:100]}...")
                typer.echo(f"   Score: {result.similarity:.3f}")
                typer.echo(f"   Category: {result.category}")
                typer.echo(f"   Source: {result.source}\n")

    elif action == "list":
        categories = kb.get_categories()
        typer.echo("Categories:")
        for cat, count in categories.items():
            typer.echo(f"  {cat}: {count} entries")

    elif action == "stats":
        stats = kb.get_statistics()
        typer.echo("Knowledge Base Statistics:")
        for key, value in stats.items():
            typer.echo(f"  {key}: {value}")

    else:
        typer.secho(f"Unknown action: {action}", fg=typer.colors.RED, err=True)
        typer.echo("Valid actions: add, search, list, stats")
        raise typer.Exit(code=1)


@app.command()
def export(
    input_file: str = typer.Argument(..., help="Input document (PDF, DOCX, etc.)"),
    md_out: str = typer.Option("build/doc.md", "--md", help="Markdown output path"),
    html_out: str = typer.Option("build/doc.html", "--html", help="HTML output path"),
    docx_out: str = typer.Option("output/final.docx", "--docx", help="DOCX output path"),
    pdf_out: str = typer.Option("output/final.pdf", "--pdf", help="PDF output path"),
    style_map: str = typer.Option("styles/style_map.yml", "--style-map", help="Path to style_map.yml"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """
    Export document to DOCX and PDF formats.

    Converts input document through Docling → Markdown → HTML → DOCX/PDF pipeline.

    Example:
        kps export document.pdf --docx output/doc.docx --pdf output/doc.pdf
    """
    import time
    from kps.export import (
        doc_to_markdown,
        markdown_to_html,
        load_style_contract,
        render_docx_with_contract,
        render_pdf_with_contract,
    )
    # from kps.metrics import record_export, record_export_duration

    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        contract = load_style_contract(style_map)
        typer.echo("Starting export pipeline...")

        # Step 1: Docling → Markdown
        if verbose:
            typer.echo(f"[1/4] Extracting to Markdown: {input_file} → {md_out}")
        start = time.time()
        doc_to_markdown(input_file, md_out)
        duration = time.time() - start
        # record_export_duration("md", duration)
        # record_export("md")
        if verbose:
            typer.echo(f"      ✓ Complete ({duration:.2f}s)")

        # Step 2: Markdown → HTML
        if verbose:
            typer.echo(f"[2/4] Converting to HTML: {md_out} → {html_out}")
        start = time.time()
        markdown_to_html(md_out, html_out)
        duration = time.time() - start
        # record_export_duration("html", duration)
        # record_export("html")
        if verbose:
            typer.echo(f"      ✓ Complete ({duration:.2f}s)")

        # Step 3: Markdown → DOCX
        if verbose:
            typer.echo(f"[3/4] Rendering DOCX: {md_out} → {docx_out}")
        start = time.time()
        render_docx_with_contract(md_out, docx_out, contract)
        duration = time.time() - start
        # record_export_duration("docx", duration)
        # record_export("docx")
        if verbose:
            typer.echo(f"      ✓ Complete ({duration:.2f}s)")

        # Step 4: HTML → PDF
        if verbose:
            typer.echo(f"[4/4] Rendering PDF: {html_out} → {pdf_out}")
        start = time.time()
        render_pdf_with_contract(html_out, pdf_out, contract)
        duration = time.time() - start
        # record_export_duration("pdf", duration)
        # record_export("pdf")
        if verbose:
            typer.echo(f"      ✓ Complete ({duration:.2f}s)")

        # Success
        typer.echo("\n" + "=" * 60)
        typer.secho("✓ Export complete!", fg=typer.colors.GREEN, bold=True)
        typer.echo("=" * 60)
        typer.echo(f"DOCX: {docx_out}")
        typer.echo(f"PDF:  {pdf_out}")
        typer.echo(f"HTML: {html_out}")
        typer.echo(f"MD:   {md_out}")

    except Exception as e:
        typer.secho(f"✗ Export failed: {e}", fg=typer.colors.RED, err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(code=1)


@app.command()
def glossary(
    action: str = typer.Argument(..., help="Action: import-tbx, export-tbx"),
    file: str = typer.Option(..., "--file", "-f", help="TBX file path"),
    db: str = typer.Option(..., "--db", help="Database URL (postgresql://...)"),
    src: str = typer.Option(..., "--src", help="Source language code"),
    tgt: str = typer.Option(..., "--tgt", help="Target language code"),
    domain: str = typer.Option("general", "--domain", "-d", help="Domain/category"),
):
    """
    Glossary operations (TBX import/export).

    Actions:
        import-tbx  - Import TBX file into glossary_terms
        export-tbx  - Export glossary_terms to TBX file

    Example:
        kps glossary import-tbx --file terms.tbx --db "postgresql://..." --src ru --tgt en
        kps glossary export-tbx --file export.tbx --db "postgresql://..." --src ru --tgt en --domain knitting
    """
    from kps.interop import import_tbx_to_db, export_glossary_to_tbx

    if action == "import-tbx":
        typer.echo(f"Importing TBX from: {file}")
        try:
            n = import_tbx_to_db(
                path_tbx=file,
                db_url=db,
                src_lang=src,
                tgt_lang=tgt,
                domain=domain,
            )
            typer.secho(f"✓ Imported {n} glossary term pairs ({src} → {tgt})", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"✗ Import failed: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    elif action == "export-tbx":
        typer.echo(f"Exporting TBX to: {file}")
        try:
            n = export_glossary_to_tbx(
                db_url=db,
                output_path=file,
                src_lang=src,
                tgt_lang=tgt,
                domain=domain if domain != "general" else None,
            )
            typer.secho(f"✓ Exported {n} glossary term pairs to TBX", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"✗ Export failed: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    else:
        typer.secho(f"Unknown action: {action}", fg=typer.colors.RED, err=True)
        typer.echo("Valid actions: import-tbx, export-tbx")
        raise typer.Exit(code=1)


@app.command()
def memory(
    action: str = typer.Argument(..., help="Action: import-tmx, export-tmx"),
    file: str = typer.Option(..., "--file", "-f", help="TMX file path"),
    db: str = typer.Option(..., "--db", help="Database URL (postgresql://...)"),
    src: str = typer.Option(..., "--src", help="Source language code"),
    tgt: str = typer.Option(..., "--tgt", help="Target language code"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit for export"),
):
    """
    Translation memory operations (TMX import/export).

    Actions:
        import-tmx  - Import TMX file into translations_training
        export-tmx  - Export translations_training to TMX file

    Example:
        kps memory import-tmx --file memory.tmx --db "postgresql://..." --src ru --tgt en
        kps memory export-tmx --file export.tmx --db "postgresql://..." --src ru --tgt en --limit 1000
    """
    from kps.interop import import_tmx_to_db, export_translations_to_tmx

    if action == "import-tmx":
        typer.echo(f"Importing TMX from: {file}")
        try:
            n = import_tmx_to_db(
                path_tmx=file,
                db_url=db,
                src_lang=src,
                tgt_lang=tgt,
            )
            typer.secho(f"✓ Imported {n} translation pairs ({src} → {tgt})", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"✗ Import failed: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    elif action == "export-tmx":
        typer.echo(f"Exporting TMX to: {file}")
        try:
            n = export_translations_to_tmx(
                db_url=db,
                output_path=file,
                src_lang=src,
                tgt_lang=tgt,
                limit=limit,
            )
            typer.secho(f"✓ Exported {n} translation pairs to TMX", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"✗ Export failed: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    else:
        typer.secho(f"Unknown action: {action}", fg=typer.colors.RED, err=True)
        typer.echo("Valid actions: import-tmx, export-tmx")
        raise typer.Exit(code=1)


@app.command()
def version():
    """Show version information."""
    typer.echo("KPS (Knitting Pattern System) v2.0.0")
    typer.echo("Python-based document processing and translation system")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
