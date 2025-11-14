-- pgvector installation and semantic memory tables
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS semantic_translations (
    id BIGSERIAL PRIMARY KEY,
    hash TEXT UNIQUE NOT NULL,
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    source_lang TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    glossary_terms JSONB,
    usage_count INTEGER DEFAULT 1,
    quality_score REAL DEFAULT 1.0,
    embedding vector(1536),
    context TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS term_suggestions (
    id BIGSERIAL PRIMARY KEY,
    source_text TEXT NOT NULL,
    translated_text TEXT,
    source_lang TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    frequency INTEGER DEFAULT 1,
    confidence REAL DEFAULT 0.5,
    contexts JSONB,
    UNIQUE(source_text, source_lang, target_lang)
);

CREATE INDEX IF NOT EXISTS idx_semantic_lang_pair
    ON semantic_translations (source_lang, target_lang);
