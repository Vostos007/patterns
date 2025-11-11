"""
KPS Command Line Interface.

Provides commands for document processing, translation, and automation.
"""

import logging
from pathlib import Path
from typing import List, Optional

import typer

app = typer.Typer(
    name="kps",
    help="Knitting Pattern System - Document processing and translation",
    add_completion=False,
)


@app.command()
def translate(
    input_file: str = typer.Argument(..., help="Input document (PDF, DOCX)"),
    languages: str = typer.Option("en,fr", "--lang", "-l", help="Target languages (comma-separated)"),
    output_dir: str = typer.Option("output", "--output", "-o", help="Output directory"),
    format: str = typer.Option("idml", "--format", "-f", help="Export format (idml, pdf, docx, markdown)"),
    glossary: Optional[str] = typer.Option(None, "--glossary", "-g", help="Glossary file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
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

    typer.echo(f"Processing: {input_file}")
    typer.echo(f"Languages: {languages}")
    typer.echo(f"Output: {output_dir}")

    # Parse languages
    target_langs = [lang.strip() for lang in languages.split(",")]

    # Create config
    config = PipelineConfig(
        extraction_method=ExtractionMethod.AUTO,
        memory_type=MemoryType.SEMANTIC,
        glossary_path=glossary or "glossary.yaml",
        export_format=format,
    )

    # Create pipeline
    pipeline = UnifiedPipeline(config)

    # Process
    try:
        result = pipeline.process(
            input_file=Path(input_file),
            target_languages=target_langs,
            output_dir=Path(output_dir),
        )

        # Print results
        typer.echo("\n" + "=" * 60)
        typer.secho("✓ Translation complete!", fg=typer.colors.GREEN, bold=True)
        typer.echo("=" * 60)
        typer.echo(f"Segments translated: {result.segments_translated}")
        typer.echo(f"Cache hit rate: {result.cache_hit_rate:.0%}")
        typer.echo(f"Translation cost: ${result.translation_cost:.4f}")
        typer.echo(f"Processing time: {result.processing_time:.1f}s")

        if result.output_files:
            typer.echo("\nOutput files:")
            for lang, filepath in result.output_files.items():
                typer.echo(f"  {lang}: {filepath}")

        if result.errors:
            typer.echo("\nErrors:")
            for error in result.errors:
                typer.secho(f"  ✗ {error}", fg=typer.colors.RED)

        if result.warnings:
            typer.echo("\nWarnings:")
            for warning in result.warnings:
                typer.secho(f"  ⚠ {warning}", fg=typer.colors.YELLOW)

    except Exception as e:
        typer.secho(f"✗ Error: {e}", fg=typer.colors.RED, err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(code=1)


@app.command()
def daemon(
    inbox: str = typer.Option("inbox", "--inbox", "-i", help="Inbox directory to monitor"),
    output: str = typer.Option("output", "--output", "-o", help="Output directory"),
    languages: str = typer.Option("en,fr", "--lang", "-l", help="Target languages (comma-separated)"),
    interval: int = typer.Option(300, "--interval", help="Check interval (seconds)"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    once: bool = typer.Option(False, "--once", help="Run once and exit"),
):
    """
    Start automatic document processing daemon.

    Monitors the inbox directory and automatically processes new documents.

    Example:
        kps daemon --inbox ./inbox --lang en,fr --interval 300
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
def version():
    """Show version information."""
    typer.echo("KPS (Knitting Pattern System) v2.0.0")
    typer.echo("Python-based document processing and translation system")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
