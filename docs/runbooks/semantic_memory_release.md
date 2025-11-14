# Semantic Memory Release Checklist

Используем этот runbook при включении pgvector-бэкенда или подготовке релиза памяти.

## 1. Подготовка окружения
1. `cd dev/PDF_PARSER_2.0`
2. `python3 -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `source .env` (в нём `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `POSTGRES_DSN`)

## 2. Синхронизировать глоссарий
```bash
python3 scripts/sync_glossary.py
```
Коммитим `data/glossary.json` и `config/glossaries/knitting_custom.yaml`.

## 3. Прогреть semantic memory
### SQLite
```bash
python3 scripts/seed_glossary_memory.py --backend sqlite
python3 scripts/reindex_semantic_memory.py --backend sqlite
```

### Postgres + pgvector
```bash
python3 scripts/seed_glossary_memory.py --backend pgvector --dsn "$POSTGRES_DSN"
python3 scripts/reindex_semantic_memory.py --backend pgvector --dsn "$POSTGRES_DSN"
```
Скрипт reindex создаёт временную таблицу, пересчитывает embeddings и обновляет индекс `semantic_entries_embedding_idx`.

## 4. RAG sanity-check
1. `python3 -m pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -vv`
2. `python3 -m pytest dev/PDF_PARSER_2.0/tests/test_translation_orchestrator.py -vv`

## 5. Smoke-тест «КАРДИГАН»
```bash
source .env
python3 -m kps.cli translate \
  "/Users/vostos/Dev/Hollywool patterns/КАРДИГАН peer gynt.docx" \
  --lang en,fr --format docx,pdf --verbose
```
Проверяем `dev/PDF_PARSER_2.0/runtime/output/peer-gynt/v***/`. Если появляются ошибки терминов, прогоняем `scripts/seed_glossary_memory.py --fix-missing`.

## 6. UI Control Room
1. `cd dev/ui_service && ./start.sh` — сервис автоматически читает `.env`.
2. `cd dev/ui_dashboard && ./start.sh` — `NEXT_PUBLIC_API_BASE` берётся из `.env.local`.
3. Через дашборд загружаем «КАРДИГАН», убеждаемся, что артефакты появились в `translations/`.

## 7. Релиз
- Обновить README/CHANGELOG.
- Закрыть план `docs/plans/2025-11-14-semantic-memory-pipeline-refresh.md`.
- Отправить release note и зафиксировать build-артефакты.
