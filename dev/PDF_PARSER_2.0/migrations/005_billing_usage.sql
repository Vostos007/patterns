-- P6: Billing & Budget Control
-- Tracks API usage and costs for budget management

create table if not exists billing_usage (
  id bigserial primary key,
  ts timestamptz default now(),
  job_id text not null,
  model text not null,
  tokens_in int not null,
  tokens_out int not null,
  cost_usd numeric not null
);

-- Index for daily aggregations
create index if not exists billing_usage_ts_idx on billing_usage(ts desc);

-- Index for job lookups
create index if not exists billing_usage_job_idx on billing_usage(job_id);

-- Index for model-specific queries
create index if not exists billing_usage_model_idx on billing_usage(model);

-- Comments
comment on table billing_usage is 'API usage tracking for budget control and cost reporting';
comment on column billing_usage.job_id is 'Unique job/task identifier';
comment on column billing_usage.model is 'OpenAI model name (e.g., gpt-4o-mini)';
comment on column billing_usage.tokens_in is 'Input tokens (prompt)';
comment on column billing_usage.tokens_out is 'Output tokens (completion)';
comment on column billing_usage.cost_usd is 'Estimated cost in USD';
