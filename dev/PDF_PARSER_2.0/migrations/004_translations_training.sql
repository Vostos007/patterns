-- P4: TBX/TMX Interoperability
-- Translation memory table for training data

create table if not exists translations_training (
  id bigserial primary key,
  src_lang text not null,
  tgt_lang text not null,
  src_text text not null,
  tgt_text text not null,
  created_at timestamptz default now()
);

-- Unique index to prevent duplicate translations
-- Using MD5 for faster comparison on large texts
create unique index if not exists translations_training_uq
  on translations_training (src_lang, tgt_lang, md5(src_text), md5(tgt_text));

-- Index for fast lookups by language pair
create index if not exists translations_training_lang_idx
  on translations_training (src_lang, tgt_lang);

-- Index for chronological queries
create index if not exists translations_training_created_idx
  on translations_training (created_at desc);

-- Comments
comment on table translations_training is 'Translation memory imported from TMX files for training and few-shot learning';
comment on column translations_training.src_text is 'Source segment text';
comment on column translations_training.tgt_text is 'Target segment text (human translation)';
