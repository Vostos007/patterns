-- KPS Database Schema Migration 001: Initial Schema
-- Created for enterprise ML localization system
-- Supports: glossary terms, translations, semantic memory, billing, RAG search

-- =============================================================================
-- DOCUMENTS TABLE
-- =============================================================================
create table if not exists documents (
    id serial primary key,
    filename text not null,
    file_hash text unique not null,  -- SHA256 for deduplication
    source_lang text not null,
    file_size_bytes bigint,
    page_count int,
    created_at timestamp default now(),
    processed_at timestamp,
    status text default 'pending'  -- pending, processing, completed, failed
);

create index idx_documents_hash on documents(file_hash);
create index idx_documents_status on documents(status);
create index idx_documents_created on documents(created_at desc);


-- =============================================================================
-- SEGMENTS TABLE
-- =============================================================================
create table if not exists segments (
    id serial primary key,
    document_id int references documents(id) on delete cascade,
    segment_id text not null,  -- e.g., "p.materials.001.seg0"
    src_text text not null,
    src_lang text not null,
    position_order int not null,  -- for reconstruction
    created_at timestamp default now()
);

create index idx_segments_document on segments(document_id);
create index idx_segments_segment_id on segments(segment_id);
create unique index idx_segments_unique on segments(document_id, segment_id);


-- =============================================================================
-- TRANSLATIONS TABLE
-- =============================================================================
create table if not exists translations (
    id serial primary key,
    segment_id int references segments(id) on delete cascade,
    tgt_lang text not null,
    translated_text text not null,
    model text not null,  -- e.g., "gpt-4o-mini"
    glossary_version text,  -- SHA256 hash for cache versioning
    tokens_in int,
    tokens_out int,
    cost_usd numeric(10, 6),
    created_at timestamp default now(),
    from_cache boolean default false
);

create index idx_translations_segment on translations(segment_id);
create index idx_translations_lang on translations(tgt_lang);
create index idx_translations_model on translations(model);


-- =============================================================================
-- TRANSLATIONS_TRAINING TABLE (TMX imports)
-- =============================================================================
create table if not exists translations_training (
    id serial primary key,
    src_lang text not null,
    tgt_lang text not null,
    src_text text not null,
    tgt_text text not null,
    source text,  -- e.g., "tmx_import", "user_correction"
    created_at timestamp default now()
);

-- Unique constraint to prevent duplicates (md5 or sha256 based)
create unique index idx_translations_training_unique
on translations_training(
    md5(src_lang || src_text || tgt_lang || tgt_text)
);

create index idx_translations_training_lang on translations_training(src_lang, tgt_lang);


-- =============================================================================
-- GLOSSARY_TERMS TABLE
-- =============================================================================
create table if not exists glossary_terms (
    id serial primary key,
    domain text not null,  -- e.g., "knitting", "sewing"
    src_lang text not null,
    tgt_lang text not null,
    src_term text not null,
    tgt_term text not null,
    aliases text[],  -- Alternative forms
    category text,  -- "abbreviation", "term", "unit"
    flags jsonb default '{}',  -- {"protected": false, "enforce_case": false}
    created_at timestamp default now(),
    updated_at timestamp default now()
);

create unique index idx_glossary_terms_unique
on glossary_terms(domain, src_lang, tgt_lang, src_term, tgt_term);

create index idx_glossary_terms_domain on glossary_terms(domain);
create index idx_glossary_terms_lang on glossary_terms(src_lang, tgt_lang);


-- =============================================================================
-- SEMANTIC_CACHE TABLE (P7: Versioned translation cache)
-- =============================================================================
create table if not exists semantic_cache (
    cache_key text primary key,  -- SHA256 of {text_norm, src, tgt, glossary_version, model}
    src_text text not null,
    tgt_text text not null,
    src_lang text not null,
    tgt_lang text not null,
    glossary_version text not null,
    model text not null,
    created_at timestamp default now(),
    last_accessed timestamp default now()
);

create index idx_semantic_cache_last_accessed on semantic_cache(last_accessed);
create index idx_semantic_cache_lang on semantic_cache(src_lang, tgt_lang);


-- =============================================================================
-- BILLING_USAGE TABLE (P6: Budget tracking)
-- =============================================================================
create table if not exists billing_usage (
    id serial primary key,
    job_id text not null,
    model text not null,
    tokens_in int not null,
    tokens_out int not null,
    cost_usd numeric(10, 6) not null,
    ts timestamp default now()
);

create index idx_billing_usage_ts on billing_usage(ts);
create index idx_billing_usage_job on billing_usage(job_id);
create index idx_billing_usage_date on billing_usage(date(ts));


-- =============================================================================
-- JOBS TABLE
-- =============================================================================
create table if not exists jobs (
    id serial primary key,
    job_id text unique not null,
    document_id int references documents(id),
    target_languages text[] not null,
    status text default 'pending',  -- pending, running, completed, failed
    started_at timestamp,
    completed_at timestamp,
    error_message text,
    created_at timestamp default now()
);

create index idx_jobs_job_id on jobs(job_id);
create index idx_jobs_status on jobs(status);
create index idx_jobs_created on jobs(created_at desc);


-- =============================================================================
-- SEARCH_CORPUS TABLE (P5: Full-text search for BM25)
-- =============================================================================
-- PostgreSQL full-text search (ts_vector)
create table if not exists search_corpus (
    id serial primary key,
    segment_id int references segments(id) on delete cascade,
    text tsvector not null  -- Full-text search index
);

create index idx_search_corpus_text on search_corpus using gin(text);
create unique index idx_search_corpus_segment on search_corpus(segment_id);


-- =============================================================================
-- EMBEDDINGS TABLE (P5: Vector search)
-- =============================================================================
-- Requires pgvector extension: CREATE EXTENSION vector;
-- Uncomment when pgvector is installed
/*
create extension if not exists vector;

create table if not exists embeddings (
    id serial primary key,
    segment_id int references segments(id) on delete cascade,
    vec vector(384)  -- text-embedding-3-small dimension
);

create index idx_embeddings_vec on embeddings using ivfflat(vec vector_cosine_ops) with (lists = 100);
create unique index idx_embeddings_segment on embeddings(segment_id);
*/


-- =============================================================================
-- MIGRATION METADATA
-- =============================================================================
create table if not exists schema_migrations (
    version int primary key,
    name text not null,
    applied_at timestamp default now()
);

insert into schema_migrations (version, name) values (1, '001_initial_schema')
on conflict (version) do nothing;


-- =============================================================================
-- INITIAL DATA COMMENTS
-- =============================================================================
comment on table documents is 'PDF/DOCX source documents';
comment on table segments is 'Extracted text segments from documents';
comment on table translations is 'Translated segments with metadata';
comment on table translations_training is 'Training data from TMX imports';
comment on table glossary_terms is 'Multilingual glossary with term pairs';
comment on table semantic_cache is 'Versioned translation cache (P7)';
comment on table billing_usage is 'API usage tracking for budget control (P6)';
comment on table jobs is 'Translation job queue and status';
comment on table search_corpus is 'Full-text search corpus for BM25 (P5)';
-- comment on table embeddings is 'Vector embeddings for semantic search (P5)';

-- End of migration 001
