"""
Prometheus metrics for KPS translation pipeline (P6).

Provides:
- Counters for documents, segments, glossary violations, cache hits
- Histograms for latency tracking (extraction, translation, export)
- Gauges for current budget usage
- HTTP endpoint for Prometheus scraping

Usage:
    from kps.metrics import (
        documents_total,
        translation_cost_usd,
        glossary_violations_total,
        track_duration
    )

    # Counter
    documents_total.labels(source_lang="ru", target_lang="en").inc()

    # Histogram with context manager
    with track_duration("extraction"):
        extract_document()

    # Gauge
    daily_budget_pct.set(45.5)
"""

import logging
import time
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# Check if prometheus_client is available
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        start_http_server,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Stub classes for when prometheus_client is not installed
    class Counter:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, **kwargs):
            return self
        def inc(self, amount=1):
            pass

    class Histogram:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, **kwargs):
            return self
        def observe(self, amount):
            pass

    class Gauge:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass
        def set(self, value):
            pass
        def inc(self, amount=1):
            pass
        def dec(self, amount=1):
            pass


# =============================================================================
# COUNTERS (累積值 - things that only go up)
# =============================================================================

# Documents processed
documents_total = Counter(
    "kps_documents_total",
    "Total documents processed",
    ["source_lang", "target_lang", "status"]  # status: success, error
)

# Segments processed
segments_total = Counter(
    "kps_segments_total",
    "Total segments translated",
    ["source_lang", "target_lang"]
)

# Glossary violations
glossary_violations_total = Counter(
    "kps_glossary_violations_total",
    "Total glossary term violations detected",
    ["violation_type", "src_lang", "tgt_lang"]  # violation_type: term_missing, case_mismatch, etc.
)

# Term enforcements
term_enforcements_total = Counter(
    "kps_term_enforcements_total",
    "Total automatic term enforcements applied",
    ["src_lang", "tgt_lang"]
)

# Cache hits/misses
cache_hits_total = Counter(
    "kps_cache_hits_total",
    "Total translation cache hits",
    ["src_lang", "tgt_lang", "cache_type"]  # cache_type: semantic, exact
)

cache_misses_total = Counter(
    "kps_cache_misses_total",
    "Total translation cache misses",
    ["src_lang", "tgt_lang"]
)

# API calls
api_calls_total = Counter(
    "kps_api_calls_total",
    "Total OpenAI API calls",
    ["model", "status"]  # status: success, error, rate_limit
)

# Translation cost
translation_cost_usd = Counter(
    "kps_translation_cost_usd_total",
    "Total translation cost in USD",
    ["model"]
)

# Token usage
tokens_total = Counter(
    "kps_tokens_total",
    "Total tokens processed",
    ["model", "direction"]  # direction: input, output
)


# =============================================================================
# HISTOGRAMS (分布 - track distributions of values)
# =============================================================================

# Latency tracking
duration_seconds = Histogram(
    "kps_duration_seconds",
    "Operation duration in seconds",
    ["operation"],  # operation: extraction, segmentation, translation, validation, export
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

# Segment length distribution
segment_length_chars = Histogram(
    "kps_segment_length_chars",
    "Segment length in characters",
    ["lang"],
    buckets=[10, 50, 100, 200, 500, 1000, 2000, 5000]
)

# Batch size distribution
batch_size = Histogram(
    "kps_batch_size",
    "Number of segments per batch",
    buckets=[1, 5, 10, 20, 50, 100, 200]
)


# =============================================================================
# GAUGES (現在値 - track current values that can go up or down)
# =============================================================================

# Budget usage
daily_budget_usd = Gauge(
    "kps_daily_budget_usd",
    "Daily budget limit in USD"
)

daily_spent_usd = Gauge(
    "kps_daily_spent_usd",
    "Daily spending in USD"
)

daily_budget_pct = Gauge(
    "kps_daily_budget_pct",
    "Daily budget usage percentage"
)

# Active jobs
active_jobs = Gauge(
    "kps_active_jobs",
    "Number of currently active translation jobs"
)

# Cache size
cache_entries = Gauge(
    "kps_cache_entries",
    "Number of entries in translation cache",
    ["cache_type"]  # cache_type: semantic, exact
)

# Queue size
queue_size = Gauge(
    "kps_queue_size",
    "Number of documents in processing queue"
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

@contextmanager
def track_duration(operation: str):
    """
    Context manager to track operation duration.

    Args:
        operation: Operation name (e.g., "extraction", "translation")

    Example:
        >>> with track_duration("extraction"):
        ...     extract_document(pdf_path)
    """
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        duration_seconds.labels(operation=operation).observe(elapsed)


def record_document(source_lang: str, target_lang: str, status: str = "success"):
    """
    Record document processing.

    Args:
        source_lang: Source language code
        target_lang: Target language code
        status: Processing status ("success" or "error")
    """
    documents_total.labels(
        source_lang=source_lang,
        target_lang=target_lang,
        status=status
    ).inc()


def record_segments(count: int, source_lang: str, target_lang: str):
    """
    Record segment translation.

    Args:
        count: Number of segments
        source_lang: Source language
        target_lang: Target language
    """
    segments_total.labels(
        source_lang=source_lang,
        target_lang=target_lang
    ).inc(count)


def record_violation(violation_type: str, src_lang: str, tgt_lang: str):
    """
    Record glossary violation.

    Args:
        violation_type: Type of violation (e.g., "term_missing", "case_mismatch")
        src_lang: Source language
        tgt_lang: Target language
    """
    glossary_violations_total.labels(
        violation_type=violation_type,
        src_lang=src_lang,
        tgt_lang=tgt_lang
    ).inc()


def record_enforcement(src_lang: str, tgt_lang: str):
    """
    Record term enforcement.

    Args:
        src_lang: Source language
        tgt_lang: Target language
    """
    term_enforcements_total.labels(
        src_lang=src_lang,
        tgt_lang=tgt_lang
    ).inc()


def record_cache_hit(src_lang: str, tgt_lang: str, cache_type: str = "semantic"):
    """
    Record cache hit.

    Args:
        src_lang: Source language
        tgt_lang: Target language
        cache_type: Type of cache ("semantic" or "exact")
    """
    cache_hits_total.labels(
        src_lang=src_lang,
        tgt_lang=tgt_lang,
        cache_type=cache_type
    ).inc()


def record_cache_miss(src_lang: str, tgt_lang: str):
    """
    Record cache miss.

    Args:
        src_lang: Source language
        tgt_lang: Target language
    """
    cache_misses_total.labels(
        src_lang=src_lang,
        tgt_lang=tgt_lang
    ).inc()


def record_api_call(model: str, status: str = "success"):
    """
    Record API call.

    Args:
        model: Model name (e.g., "gpt-4o-mini")
        status: Call status ("success", "error", "rate_limit")
    """
    api_calls_total.labels(
        model=model,
        status=status
    ).inc()


def record_cost(model: str, cost_usd: float):
    """
    Record translation cost.

    Args:
        model: Model name
        cost_usd: Cost in USD
    """
    translation_cost_usd.labels(model=model).inc(cost_usd)


def record_tokens(model: str, tokens_in: int, tokens_out: int):
    """
    Record token usage.

    Args:
        model: Model name
        tokens_in: Input tokens
        tokens_out: Output tokens
    """
    tokens_total.labels(model=model, direction="input").inc(tokens_in)
    tokens_total.labels(model=model, direction="output").inc(tokens_out)


def update_budget(daily_limit: float, daily_spent: float):
    """
    Update budget metrics.

    Args:
        daily_limit: Daily budget limit in USD
        daily_spent: Daily spending in USD
    """
    daily_budget_usd.set(daily_limit)
    daily_spent_usd.set(daily_spent)

    if daily_limit > 0:
        pct = (daily_spent / daily_limit) * 100
        daily_budget_pct.set(pct)


def start_metrics_server(port: int = 9090):
    """
    Start Prometheus metrics HTTP server.

    Args:
        port: HTTP port (default: 9090)

    Example:
        >>> start_metrics_server(port=9090)
        Metrics server started on port 9090
    """
    if not PROMETHEUS_AVAILABLE:
        logger.warning(
            "prometheus_client not installed. "
            "Install with: pip install prometheus-client"
        )
        return

    try:
        start_http_server(port)
        logger.info(f"Prometheus metrics server started on port {port}")
        logger.info(f"Metrics available at http://localhost:{port}/metrics")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")


def get_metrics_text() -> str:
    """
    Get metrics in Prometheus text format.

    Returns:
        Metrics text (empty if prometheus not available)

    Example:
        >>> metrics = get_metrics_text()
        >>> print(metrics)
    """
    if not PROMETHEUS_AVAILABLE:
        return ""

    try:
        return generate_latest().decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return ""


__all__ = [
    # Counters
    "documents_total",
    "segments_total",
    "glossary_violations_total",
    "term_enforcements_total",
    "cache_hits_total",
    "cache_misses_total",
    "api_calls_total",
    "translation_cost_usd",
    "tokens_total",

    # Histograms
    "duration_seconds",
    "segment_length_chars",
    "batch_size",

    # Gauges
    "daily_budget_usd",
    "daily_spent_usd",
    "daily_budget_pct",
    "active_jobs",
    "cache_entries",
    "queue_size",

    # Helper functions
    "track_duration",
    "record_document",
    "record_segments",
    "record_violation",
    "record_enforcement",
    "record_cache_hit",
    "record_cache_miss",
    "record_api_call",
    "record_cost",
    "record_tokens",
    "update_budget",
    "start_metrics_server",
    "get_metrics_text",
]
