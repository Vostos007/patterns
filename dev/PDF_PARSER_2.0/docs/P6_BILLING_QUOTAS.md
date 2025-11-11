# P6: Billing & Budget Control

## Overview

P6 implements comprehensive cost management and budget enforcement for OpenAI API usage:

1. **Cost Tracking**: Real-time recording of API usage (tokens, models, costs)
2. **Budget Enforcement**: Three-tier policy system (allow/degrade/deny)
3. **Quota Management**: Daily and per-job spending limits
4. **Reporting**: CSV exports, Prometheus metrics, Grafana dashboards

## Architecture

```
[Translation Request]
         ↓
  [Estimate Cost] ← Model pricing table
         ↓
  [Check Budget] ← Daily spent, job limit
         ↓
    ┌────┴────┐
    ↓         ↓         ↓
 [allow]  [degrade] [deny]
    ↓         ↓         ↓
 Use GPT-4  Use mini  Queue/reject
    ↓         ↓         ↓
  [Record Usage] → billing_usage table
         ↓
  [Prometheus Metrics] → Grafana
```

### Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| `kps/billing/cost.py` | Cost estimation | Per-1K token pricing |
| `kps/billing/limits.py` | Budget enforcement | PostgreSQL queries |
| `migrations/005_billing_usage.sql` | Usage tracking schema | PostgreSQL |
| `kps/metrics.py` | Prometheus metrics | prometheus_client |

## Cost Estimation

### Pricing Model

Current OpenAI pricing (per 1K tokens):

```python
PRICES_PER_1K = {
    # GPT-4o mini (recommended)
    "gpt-4o-mini": {
        "in": 0.15,   # $0.15 per 1K input tokens
        "out": 0.60,  # $0.60 per 1K output tokens
    },

    # GPT-4.1 (premium)
    "gpt-4.1": {
        "in": 5.00,   # $5.00 per 1K input tokens
        "out": 15.00, # $15.00 per 1K output tokens
    },

    # Embeddings
    "text-embedding-3-small": {
        "in": 0.02,   # $0.02 per 1K tokens
        "out": 0.00,  # No output cost
    },
}
```

### Usage Calculation

```python
from kps.billing.cost import Usage, estimate_cost

# Example: Translate 500-word document
usage = Usage(
    model="gpt-4o-mini",
    tokens_in=750,   # ~500 words + context
    tokens_out=800   # ~530 words translated
)

cost = estimate_cost(usage)
print(f"Cost: ${cost:.4f}")  # Cost: $0.5925

# Breakdown:
# Input:  (750/1000)  * $0.15 = $0.1125
# Output: (800/1000)  * $0.60 = $0.4800
# Total:                        $0.5925
```

### Pre-Translation Estimation

```python
from kps.billing.cost import estimate_translation_cost
from tiktoken import encoding_for_model

# Estimate before translation
src_text = "Провяжите лицевую петлю в каждую петлю предыдущего ряда."
context = "..." # Retrieved context

enc = encoding_for_model("gpt-4o-mini")
tokens_in = len(enc.encode(src_text + context))
tokens_out_estimate = int(tokens_in * 1.2)  # Estimate 20% longer translation

projected_cost = estimate_cost(Usage(
    model="gpt-4o-mini",
    tokens_in=tokens_in,
    tokens_out=tokens_out_estimate
))

print(f"Projected cost: ${projected_cost:.4f}")
```

## Budget Enforcement

### Three-Tier Policy System

| Policy | Condition | Action | Use Case |
|--------|-----------|--------|----------|
| **allow** | Within budget | Proceed with requested model | Normal operation |
| **degrade** | Approaching limit | Use cheaper model (GPT-4o-mini) | Cost optimization |
| **deny** | Exceeds limit | Reject or queue for tomorrow | Hard budget cap |

### Configuration

```bash
# Environment variables (defaults)
export KPS_BUDGET_DAILY_USD=50.0      # Daily spending limit
export KPS_BUDGET_JOB_USD=5.0          # Per-job spending limit
export KPS_BUDGET_POLICY=degrade       # Default policy: allow/degrade/deny
```

### Policy Logic

```python
from kps.billing.limits import check_budget

# Check before translation
policy = check_budget(
    db_url="postgresql://user:pass@localhost/kps",
    job_id="doc-12345",
    projected_cost=0.85  # $0.85 estimated
)

if policy == "allow":
    # Proceed with requested model
    translate_with_gpt4(doc)

elif policy == "degrade":
    # Switch to cheaper model
    logging.warning("Budget approaching limit, using mini model")
    translate_with_mini(doc)

elif policy == "deny":
    # Queue or reject
    logging.error("Budget exceeded, queueing for tomorrow")
    queue_for_later(doc)
```

### Budget Check Logic

```python
# Check daily spending
daily_spent = get_daily_spent(db_url)  # Query billing_usage for today
daily_limit = float(os.getenv("KPS_BUDGET_DAILY_USD", "50.0"))

if daily_spent + projected_cost > daily_limit:
    return "deny"  # Hard limit

# Check per-job spending
job_limit = float(os.getenv("KPS_BUDGET_JOB_USD", "5.0"))

if projected_cost > job_limit:
    return "degrade"  # Single job too expensive, use mini

return "allow"
```

## Usage Tracking

### Database Schema

```sql
create table if not exists billing_usage (
  id bigserial primary key,
  ts timestamptz default now(),
  job_id text not null,
  model text not null,
  tokens_in int not null,
  tokens_out int not null,
  cost_usd numeric not null
);

-- Indexes for reporting
create index billing_usage_ts_idx on billing_usage(ts desc);
create index billing_usage_job_idx on billing_usage(job_id);
create index billing_usage_model_idx on billing_usage(model);
```

### Recording Usage

```python
from kps.billing.cost import Usage, estimate_cost
import psycopg2

def record_usage(db_url: str, job_id: str, usage: Usage):
    """Record API usage to database."""
    cost = estimate_cost(usage)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    cur.execute("""
        insert into billing_usage(job_id, model, tokens_in, tokens_out, cost_usd)
        values (%s, %s, %s, %s, %s)
    """, (job_id, usage.model, usage.tokens_in, usage.tokens_out, cost))

    conn.commit()
    cur.close()
    conn.close()

# Usage
usage = Usage(model="gpt-4o-mini", tokens_in=750, tokens_out=800)
record_usage(db_url, job_id="doc-12345", usage=usage)
```

### Querying Usage

```sql
-- Daily spending
select date(ts) as day, sum(cost_usd) as total_cost
from billing_usage
where ts >= current_date - interval '30 days'
group by date(ts)
order by day desc;

-- Spending by model
select model, count(*) as requests, sum(cost_usd) as total_cost
from billing_usage
where ts >= current_date
group by model;

-- Top jobs by cost
select job_id, sum(cost_usd) as job_cost, count(*) as api_calls
from billing_usage
group by job_id
order by job_cost desc
limit 10;
```

## Reporting

### CSV Export

```python
from kps.billing.reports import export_daily_report
import csv

def export_daily_report(db_url: str, output_path: str):
    """Export daily spending report to CSV."""
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    cur.execute("""
        select date(ts) as day,
               model,
               count(*) as requests,
               sum(tokens_in) as total_tokens_in,
               sum(tokens_out) as total_tokens_out,
               sum(cost_usd) as total_cost
        from billing_usage
        where ts >= current_date - interval '30 days'
        group by date(ts), model
        order by day desc, model
    """)

    rows = cur.fetchall()

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Day", "Model", "Requests", "Tokens In", "Tokens Out", "Cost USD"])
        writer.writerows(rows)

    cur.close()
    conn.close()

# Usage
export_daily_report(db_url, "billing_report.csv")
```

### CLI Command

```bash
# Export billing report
kps billing report --start 2025-11-01 --end 2025-11-11 --output report.csv

# Check current spending
kps billing status

# Output:
# Daily budget: $50.00
# Spent today: $12.45 (24.9%)
# Jobs completed: 8
# Average cost per job: $1.56
```

## Prometheus Metrics

### Metrics Defined

```python
from prometheus_client import Counter, Histogram, Gauge

# Cost tracking
TRANSLATION_COST = Counter(
    "kps_translation_cost_dollars_total",
    "Total translation cost in dollars",
    ["model", "target_lang"],
)

# Token usage
TOKENS_USED = Counter(
    "kps_tokens_used_total",
    "Total tokens used",
    ["model", "direction"],  # direction: in/out
)

# Budget utilization
BUDGET_UTILIZATION = Gauge(
    "kps_budget_utilization_ratio",
    "Current budget utilization (0.0-1.0)",
    ["period"],  # period: daily/monthly
)
```

### Recording Metrics

```python
from kps.metrics import record_translation_cost

# Record cost
record_translation_cost(
    model="gpt-4o-mini",
    target_lang="en",
    cost=0.5925
)

# Record token usage
TOKENS_USED.labels(model="gpt-4o-mini", direction="in").inc(750)
TOKENS_USED.labels(model="gpt-4o-mini", direction="out").inc(800)

# Update budget utilization
daily_spent = get_daily_spent(db_url)
daily_limit = float(os.getenv("KPS_BUDGET_DAILY_USD", "50.0"))
BUDGET_UTILIZATION.labels(period="daily").set(daily_spent / daily_limit)
```

## Grafana Dashboard

### Panel 1: Daily Spending

```promql
# Daily cost by model
sum by (model) (
  increase(kps_translation_cost_dollars_total[1d])
)
```

### Panel 2: Budget Utilization

```promql
# Current budget utilization (0-1)
kps_budget_utilization_ratio{period="daily"}
```

### Panel 3: Cost per Document

```promql
# Average cost per document (last 24h)
sum(increase(kps_translation_cost_dollars_total[24h]))
/
sum(increase(kps_documents_processed_total[24h]))
```

### Panel 4: Token Usage

```promql
# Tokens per minute by direction
rate(kps_tokens_used_total[5m])
```

### Alerting Rules

```yaml
groups:
  - name: billing_alerts
    rules:
      # Alert at 80% daily budget
      - alert: BudgetUtilization80
        expr: kps_budget_utilization_ratio{period="daily"} > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Daily budget 80% utilized"

      # Alert at 100% daily budget
      - alert: BudgetExceeded
        expr: kps_budget_utilization_ratio{period="daily"} >= 1.0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Daily budget limit reached"
```

## Integration Example

### Complete Translation Pipeline with Budget Control

```python
from kps.billing.cost import Usage, estimate_cost
from kps.billing.limits import check_budget
from kps.metrics import record_translation_cost
import tiktoken

def translate_document_with_budget(
    doc_id: int,
    db_url: str,
    model: str = "gpt-4o-mini"
):
    """Translate document with budget enforcement."""

    # Load document
    segments = load_segments(doc_id)

    # Estimate cost
    enc = tiktoken.encoding_for_model(model)
    total_tokens_in = sum(len(enc.encode(s.text)) for s in segments)
    total_tokens_out = int(total_tokens_in * 1.2)

    projected_usage = Usage(
        model=model,
        tokens_in=total_tokens_in,
        tokens_out=total_tokens_out
    )
    projected_cost = estimate_cost(projected_usage)

    # Check budget
    policy = check_budget(db_url, f"doc-{doc_id}", projected_cost)

    if policy == "deny":
        raise RuntimeError(f"Budget exceeded. Projected cost: ${projected_cost:.2f}")

    elif policy == "degrade":
        logging.warning(f"Degrading to mini model to stay within budget")
        model = "gpt-4o-mini"

    # Translate
    actual_tokens_in = 0
    actual_tokens_out = 0

    for segment in segments:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": segment.text}]
        )

        # Track usage
        actual_tokens_in += response.usage.prompt_tokens
        actual_tokens_out += response.usage.completion_tokens

        # Save translation
        save_translation(segment.id, response.choices[0].message.content)

    # Record usage
    actual_usage = Usage(
        model=model,
        tokens_in=actual_tokens_in,
        tokens_out=actual_tokens_out
    )
    actual_cost = estimate_cost(actual_usage)

    record_usage(db_url, f"doc-{doc_id}", actual_usage)
    record_translation_cost(model, "en", actual_cost)

    logging.info(f"Document {doc_id} translated. Cost: ${actual_cost:.2f}")

    return actual_cost
```

## Success Criteria

### P6.1: Zero Budget Overruns

- **Metric**: Daily spending never exceeds `KPS_BUDGET_DAILY_USD`
- **Target**: 100% compliance over 30-day period
- **Validation**: Daily query of `sum(cost_usd) group by date(ts)`

### P6.2: Cost Tracking Accuracy

- **Metric**: Recorded cost vs. OpenAI invoice
- **Target**: ≤5% variance
- **Validation**: Monthly reconciliation with OpenAI usage dashboard

### P6.3: Reporting Availability

- **Metric**: CSV reports and Grafana dashboards available
- **Target**: 99.9% uptime
- **Validation**: Automated checks every 5 minutes

### P6.4: Alerting Reliability

- **Metric**: Budget alerts fire correctly
- **Target**: 80% and 100% alerts trigger within 5 minutes
- **Validation**: Simulate budget scenarios in staging

## Performance Considerations

### Database Indexes

```sql
-- Fast daily aggregations
create index billing_usage_ts_idx on billing_usage(ts desc);

-- Fast job lookups
create index billing_usage_job_idx on billing_usage(job_id);

-- Fast model-specific queries
create index billing_usage_model_idx on billing_usage(model);
```

### Query Optimization

```sql
-- Efficient daily spending check (uses billing_usage_ts_idx)
select sum(cost_usd) from billing_usage
where ts >= current_date;

-- Efficient job spending check (uses billing_usage_job_idx)
select sum(cost_usd) from billing_usage
where job_id = 'doc-12345';
```

### Caching

```python
from functools import lru_cache
from datetime import datetime

@lru_cache(maxsize=1)
def get_daily_spent_cached(db_url: str, date: str) -> float:
    """Cache daily spending for current date (1 entry)."""
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("select sum(cost_usd) from billing_usage where ts >= current_date")
    total = cur.fetchone()[0] or 0.0
    cur.close()
    conn.close()
    return float(total)

# Usage (cache invalidates when date changes)
daily_spent = get_daily_spent_cached(db_url, datetime.now().strftime("%Y-%m-%d"))
```

## Migration

### From No Budget Control

1. Run migration: `psql -f migrations/005_billing_usage.sql`
2. Set environment variables: `KPS_BUDGET_DAILY_USD`, `KPS_BUDGET_JOB_USD`
3. Integrate `check_budget()` into translation pipeline
4. Monitor metrics for 7 days
5. Adjust limits based on actual usage

### Backfilling Historical Data (Optional)

```python
# If you have historical OpenAI API logs
def backfill_usage_from_logs(log_file: str, db_url: str):
    """Parse OpenAI logs and backfill billing_usage table."""
    import json

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    with open(log_file) as f:
        for line in f:
            log = json.loads(line)

            usage = Usage(
                model=log["model"],
                tokens_in=log["usage"]["prompt_tokens"],
                tokens_out=log["usage"]["completion_tokens"]
            )
            cost = estimate_cost(usage)

            cur.execute("""
                insert into billing_usage(ts, job_id, model, tokens_in, tokens_out, cost_usd)
                values (%s, %s, %s, %s, %s, %s)
            """, (log["timestamp"], log["job_id"], log["model"],
                  usage.tokens_in, usage.tokens_out, cost))

    conn.commit()
    cur.close()
    conn.close()
```

## Testing

### Unit Tests

```bash
# Test cost estimation
pytest tests/unit/billing/test_cost.py -v

# Test budget checks
pytest tests/unit/billing/test_limits.py -v
```

### Integration Tests

```bash
# End-to-end billing pipeline
pytest tests/integration/test_billing_pipeline.py -v
```

### Manual Validation

```bash
# Simulate budget scenarios
export KPS_BUDGET_DAILY_USD=10.0
export KPS_BUDGET_JOB_USD=2.0

kps translate test.pdf --src-lang ru --tgt-lang en

# Check recorded usage
psql kps -c "select * from billing_usage order by ts desc limit 5"

# Check Prometheus metrics
curl http://localhost:9108/metrics | grep kps_translation_cost
```

## Troubleshooting

### Issue: Budget check is slow

**Symptom**: Translation pipeline stalls for 1-2 seconds before each job

**Cause**: Daily spending query without index

**Fix**:
```sql
create index if not exists billing_usage_ts_idx on billing_usage(ts desc);
vacuum analyze billing_usage;
```

### Issue: Cost variance > 5%

**Symptom**: Recorded costs don't match OpenAI invoice

**Cause**: Pricing table out of date or incorrect token counting

**Fix**:
1. Update `PRICES_PER_1K` in `kps/billing/cost.py` with latest OpenAI pricing
2. Verify token counting with `tiktoken.encoding_for_model()`
3. Reconcile with OpenAI usage API: https://platform.openai.com/usage

### Issue: Budget alerts not firing

**Symptom**: No alerts when daily budget reaches 80%

**Cause**: Prometheus not scraping metrics or alert rule misconfigured

**Fix**:
```bash
# Check metrics endpoint
curl http://localhost:9108/metrics | grep budget_utilization

# Verify Prometheus is scraping
curl http://localhost:9090/api/v1/targets

# Check alert rules in Prometheus UI
open http://localhost:9090/alerts
```

## References

- [OpenAI Pricing](https://openai.com/pricing)
- [tiktoken Documentation](https://github.com/openai/tiktoken)
- [Prometheus Alerting](https://prometheus.io/docs/alerting/latest/overview/)
- [PostgreSQL Date/Time Functions](https://www.postgresql.org/docs/current/functions-datetime.html)

## Support

For issues or questions:
- Check daily spending: `kps billing status`
- Export report: `kps billing report --output report.csv`
- Monitor metrics: `http://localhost:9108/metrics`
- Check logs: `tail -f logs/kps.log | grep billing`
