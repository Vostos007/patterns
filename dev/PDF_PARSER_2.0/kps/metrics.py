"""
Prometheus metrics for KPS system.

Provides real-time monitoring of:
- Document processing (count, latency, errors)
- Translation metrics (segments, cache hits, cost)
- Pipeline stages (extraction, segmentation, translation, export)
"""

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    start_http_server,
)

# Document processing metrics
DOCUMENTS_PROCESSED = Counter(
    "kps_documents_processed_total",
    "Total number of documents processed successfully",
    ["source_lang", "target_lang"],
)

DOCUMENTS_FAILED = Counter(
    "kps_documents_failed_total",
    "Total number of documents that failed processing",
    ["stage", "error_type"],
)

DOCUMENT_PROCESSING_TIME = Histogram(
    "kps_document_processing_seconds",
    "Time to process a single document end-to-end",
    ["source_lang"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)

# Translation metrics
SEGMENTS_TRANSLATED = Counter(
    "kps_segments_translated_total",
    "Total number of segments translated",
    ["source_lang", "target_lang", "from_cache"],
)

TRANSLATION_COST = Counter(
    "kps_translation_cost_dollars_total",
    "Total translation cost in dollars",
    ["model", "target_lang"],
)

TRANSLATION_CACHE_HIT_RATE = Gauge(
    "kps_translation_cache_hit_rate",
    "Current cache hit rate (0.0-1.0)",
    ["source_lang", "target_lang"],
)

# Glossary metrics
GLOSSARY_TERMS_APPLIED = Counter(
    "kps_glossary_terms_applied_total",
    "Number of glossary terms successfully applied",
    ["source_lang", "target_lang"],
)

TERM_VIOLATIONS = Counter(
    "kps_term_violations_total",
    "Number of glossary term violations detected",
    ["violation_type", "target_lang"],
)

# Pipeline stage metrics
EXTRACTION_DURATION = Histogram(
    "kps_extraction_duration_seconds",
    "Time spent in extraction stage",
    ["extractor"],
    buckets=[0.5, 1, 2, 5, 10, 30],
)

SEGMENTATION_DURATION = Histogram(
    "kps_segmentation_duration_seconds",
    "Time spent in segmentation stage",
    buckets=[0.1, 0.5, 1, 2, 5],
)

TRANSLATION_DURATION = Histogram(
    "kps_translation_duration_seconds",
    "Time spent in translation stage",
    ["target_lang"],
    buckets=[1, 5, 10, 30, 60, 120],
)

EXPORT_DURATION = Histogram(
    "kps_export_duration_seconds",
    "Time spent in export stage",
    ["format"],
    buckets=[0.5, 1, 2, 5, 10, 30],
)

EXPORTS_TOTAL = Counter(
    "kps_exports_total",
    "Total number of exports by format",
    ["format"],  # docx, pdf, html, md
)

# Knowledge Base metrics
KB_SEARCHES = Counter(
    "kps_kb_searches_total",
    "Total number of knowledge base searches",
    ["category", "language"],
)

KB_ENTRIES = Gauge(
    "kps_kb_entries_total",
    "Total number of entries in knowledge base",
    ["category", "language"],
)

# Daemon metrics
DAEMON_INBOX_FILES = Gauge(
    "kps_daemon_inbox_files",
    "Number of files currently in inbox",
)

DAEMON_PROCESSING_ACTIVE = Gauge(
    "kps_daemon_processing_active",
    "Number of documents currently being processed",
)

DAEMON_UPTIME_SECONDS = Gauge(
    "kps_daemon_uptime_seconds",
    "Daemon uptime in seconds",
)

# System info
SYSTEM_INFO = Info(
    "kps_system",
    "KPS system information",
)


def expose_metrics(port: int = 9108):
    """
    Start Prometheus metrics HTTP server.

    Args:
        port: Port to expose metrics on (default: 9108)

    Example:
        >>> from kps.metrics import expose_metrics
        >>> expose_metrics(port=9108)
        >>> # Metrics available at http://localhost:9108/metrics
    """
    start_http_server(port)
    SYSTEM_INFO.info({
        "version": "2.0.0",
        "component": "kps",
        "description": "Knitting Pattern System"
    })


def record_document_processed(source_lang: str, target_lang: str, duration: float):
    """Record successful document processing."""
    DOCUMENTS_PROCESSED.labels(source_lang=source_lang, target_lang=target_lang).inc()
    DOCUMENT_PROCESSING_TIME.labels(source_lang=source_lang).observe(duration)


def record_document_failed(stage: str, error_type: str):
    """Record document processing failure."""
    DOCUMENTS_FAILED.labels(stage=stage, error_type=error_type).inc()


def record_segments_translated(
    source_lang: str,
    target_lang: str,
    count: int,
    from_cache: bool
):
    """Record translated segments."""
    cache_label = "true" if from_cache else "false"
    SEGMENTS_TRANSLATED.labels(
        source_lang=source_lang,
        target_lang=target_lang,
        from_cache=cache_label
    ).inc(count)


def record_translation_cost(model: str, target_lang: str, cost: float):
    """Record translation cost."""
    TRANSLATION_COST.labels(model=model, target_lang=target_lang).inc(cost)


def set_cache_hit_rate(source_lang: str, target_lang: str, rate: float):
    """Set current cache hit rate."""
    TRANSLATION_CACHE_HIT_RATE.labels(
        source_lang=source_lang,
        target_lang=target_lang
    ).set(rate)


def record_glossary_term_applied(source_lang: str, target_lang: str):
    """Record glossary term application."""
    GLOSSARY_TERMS_APPLIED.labels(
        source_lang=source_lang,
        target_lang=target_lang
    ).inc()


def record_term_violation(violation_type: str, target_lang: str, count: int = 1):
    """Record term violation."""
    TERM_VIOLATIONS.labels(
        violation_type=violation_type,
        target_lang=target_lang
    ).inc(count)


def record_extraction_duration(extractor: str, duration: float):
    """Record extraction stage duration."""
    EXTRACTION_DURATION.labels(extractor=extractor).observe(duration)


def record_segmentation_duration(duration: float):
    """Record segmentation stage duration."""
    SEGMENTATION_DURATION.observe(duration)


def record_translation_duration(target_lang: str, duration: float):
    """Record translation stage duration."""
    TRANSLATION_DURATION.labels(target_lang=target_lang).observe(duration)


def record_export_duration(format: str, duration: float):
    """Record export stage duration."""
    EXPORT_DURATION.labels(format=format).observe(duration)


def record_export(format: str):
    """Record successful export by format."""
    EXPORTS_TOTAL.labels(format=format).inc()


def record_kb_search(category: str, language: str):
    """Record knowledge base search."""
    KB_SEARCHES.labels(category=category, language=language).inc()


def set_kb_entries(category: str, language: str, count: int):
    """Set knowledge base entry count."""
    KB_ENTRIES.labels(category=category, language=language).set(count)


def set_daemon_inbox_files(count: int):
    """Set number of files in inbox."""
    DAEMON_INBOX_FILES.set(count)


def set_daemon_processing_active(count: int):
    """Set number of documents currently being processed."""
    DAEMON_PROCESSING_ACTIVE.set(count)


def set_daemon_uptime(seconds: float):
    """Set daemon uptime."""
    DAEMON_UPTIME_SECONDS.set(seconds)


__all__ = [
    # Setup
    "expose_metrics",
    # Document metrics
    "record_document_processed",
    "record_document_failed",
    # Translation metrics
    "record_segments_translated",
    "record_translation_cost",
    "set_cache_hit_rate",
    # Glossary metrics
    "record_glossary_term_applied",
    "record_term_violation",
    # Pipeline stage metrics
    "record_extraction_duration",
    "record_segmentation_duration",
    "record_translation_duration",
    "record_export_duration",
    # Knowledge Base metrics
    "record_kb_search",
    "set_kb_entries",
    # Daemon metrics
    "set_daemon_inbox_files",
    "set_daemon_processing_active",
    "set_daemon_uptime",
]
