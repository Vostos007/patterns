"""
Budget limits and usage tracking.

Provides:
- Usage recording to database
- Daily/per-job budget checks
- Policy decisions (allow/degrade/deny)
"""

import os
import logging

logger = logging.getLogger(__name__)

# Budget configuration from environment variables
DAILY_USD = float(os.getenv("KPS_BUDGET_DAILY_USD", "50.0"))
JOB_USD = float(os.getenv("KPS_BUDGET_JOB_USD", "5.0"))


def record_usage(
    db_url: str,
    job_id: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
) -> None:
    """
    Record API usage to database.

    Args:
        db_url: PostgreSQL connection string
        job_id: Unique job identifier
        model: Model name
        tokens_in: Input tokens
        tokens_out: Output tokens
        cost_usd: Cost in USD

    Example:
        >>> record_usage(
        ...     "postgresql://user:pass@localhost/kps",
        ...     job_id="job_123",
        ...     model="gpt-4o-mini",
        ...     tokens_in=1000,
        ...     tokens_out=500,
        ...     cost_usd=0.45
        ... )
    """
    try:
        import psycopg2
    except ImportError:
        raise RuntimeError("psycopg2 not installed. Install with: pip install psycopg2-binary")

    conn = psycopg2.connect(db_url)
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute(
            """
            insert into billing_usage(job_id, model, tokens_in, tokens_out, cost_usd)
            values (%s,%s,%s,%s,%s)
            """,
            (job_id, model, tokens_in, tokens_out, cost_usd),
        )

    conn.close()
    logger.info(f"Recorded usage: job={job_id}, model={model}, cost=${cost_usd:.4f}")


def daily_spent(db_url: str) -> float:
    """
    Get total spending for current day.

    Args:
        db_url: PostgreSQL connection string

    Returns:
        Total cost in USD for today

    Example:
        >>> spent = daily_spent("postgresql://...")
        >>> print(f"Today: ${spent:.2f}")
        Today: $12.34
    """
    try:
        import psycopg2
    except ImportError:
        raise RuntimeError("psycopg2 not installed")

    conn = psycopg2.connect(db_url)

    with conn.cursor() as cur:
        cur.execute(
            """
            select coalesce(sum(cost_usd), 0)
            from billing_usage
            where ts::date = now()::date
            """
        )
        total = float(cur.fetchone()[0])

    conn.close()
    return total


def check_budget(db_url: str, job_id: str, projected_cost: float) -> str:
    """
    Check if job can proceed within budget constraints.

    Returns policy decision:
    - "allow": Proceed with requested model
    - "degrade": Use cheaper model (e.g., *-mini)
    - "deny": Reject/queue for later (budget exceeded)

    Args:
        db_url: PostgreSQL connection string
        job_id: Job identifier
        projected_cost: Estimated cost for this job

    Returns:
        Policy decision: "allow", "degrade", or "deny"

    Example:
        >>> policy = check_budget("postgresql://...", "job_123", 0.5)
        >>> if policy == "allow":
        ...     # Use requested model
        ...     pass
        >>> elif policy == "degrade":
        ...     # Switch to cheaper model
        ...     model = "gpt-4o-mini"
        >>> else:  # deny
        ...     # Queue for tomorrow
        ...     pass
    """
    # Check per-job limit
    if projected_cost > JOB_USD:
        logger.warning(
            f"Job {job_id} projected cost ${projected_cost:.2f} exceeds "
            f"per-job limit ${JOB_USD:.2f} - degrading to cheaper model"
        )
        return "degrade"

    # Check daily limit
    day_total = daily_spent(db_url)
    if day_total + projected_cost > DAILY_USD:
        logger.error(
            f"Job {job_id} would exceed daily budget: "
            f"${day_total:.2f} + ${projected_cost:.2f} > ${DAILY_USD:.2f}"
        )
        return "deny"

    # Within budget
    logger.debug(
        f"Job {job_id} approved: ${projected_cost:.2f} "
        f"(daily: ${day_total:.2f}/{DAILY_USD:.2f})"
    )
    return "allow"


def get_budget_status(db_url: str) -> dict:
    """
    Get current budget status.

    Args:
        db_url: PostgreSQL connection string

    Returns:
        Dict with budget information

    Example:
        >>> status = get_budget_status("postgresql://...")
        >>> print(status)
        {
            'daily_spent': 12.34,
            'daily_limit': 50.0,
            'daily_remaining': 37.66,
            'daily_pct': 24.68,
            'job_limit': 5.0
        }
    """
    spent = daily_spent(db_url)
    remaining = max(0, DAILY_USD - spent)
    pct = (spent / DAILY_USD * 100) if DAILY_USD > 0 else 0

    return {
        "daily_spent": spent,
        "daily_limit": DAILY_USD,
        "daily_remaining": remaining,
        "daily_pct": pct,
        "job_limit": JOB_USD,
    }


__all__ = [
    "DAILY_USD",
    "JOB_USD",
    "record_usage",
    "daily_spent",
    "check_budget",
    "get_budget_status",
]
