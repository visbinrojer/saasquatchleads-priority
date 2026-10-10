-- Production store for Priority.
-- The FastAPI demo writes data/runs.json through the same repository shape.
-- Swap the file adapter for Postgres (Supabase) without changing scoring.

create table if not exists buy_boxes (
  id uuid primary key,
  created_at timestamptz not null default now(),
  industries text[] not null,
  states text[] not null,
  revenue_min bigint not null,
  revenue_max bigint not null,
  employees_min integer not null,
  employees_max integer not null,
  exclude_franchise boolean not null default true,
  exclude_public boolean not null default true,
  exclude_pe boolean not null default true
);

create table if not exists score_runs (
  id uuid primary key,
  buy_box_id uuid not null references buy_boxes (id),
  created_at timestamptz not null default now(),
  input_hash text not null unique,
  total integer not null,
  enrich_count integer not null,
  hold_count integer not null,
  skip_count integer not null
);

create table if not exists companies (
  id uuid primary key,
  domain text not null,
  company text not null,
  industry text,
  city text,
  state text,
  country text,
  employees integer,
  revenue bigint,
  ownership text,
  raw jsonb not null default '{}'::jsonb,
  unique (domain)
);

create table if not exists scored_leads (
  id uuid primary key,
  run_id uuid not null references score_runs (id) on delete cascade,
  company_id uuid references companies (id),
  score integer not null,
  bucket text not null check (bucket in ('enrich', 'hold', 'skip')),
  warning boolean not null default false,
  duplicate_of text,
  reasons jsonb not null,
  angle text not null
);

create index if not exists scored_leads_run_bucket_idx
  on scored_leads (run_id, bucket, score desc);

-- Repeat rankings of the same file and buy box should hit input_hash
-- and return the existing run. That is the cache key. At higher volume,
-- put the same hash in Redis (Upstash) with a 24 hour TTL in front of Postgres.
