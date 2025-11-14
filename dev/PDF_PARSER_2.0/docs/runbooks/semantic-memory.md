# Runbook: Семантическая память

## Окружение
1. `cd dev/PDF_PARSER_2.0`
2. `set -a && source .env && set +a`
3. Проверить переменные: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `POSTGRES_DSN`.

## Прогрев глоссария
1. `python3 -m scripts/sync_glossary.py --source notion --dest config/glossaries/knitting_custom.yaml`
2. `python3 -m scripts/seed_glossary_memory --glossary config/glossaries/knitting_custom.yaml --db data/translation_memory.db --source ru --target en`
3. Проверить `metadata` → ключ `glossary_seed:ru:en` = актуальный hash.

## Переиндексация
```
python3 -m scripts/reindex_semantic_memory \
  --db data/translation_memory.db \
  --target-version 1 \
  --batch 256
```
`DRY RUN`: добавить `--dry-run`.

## Переключение на Postgres
1. В `.env`: `POSTGRES_DSN=postgresql://...`
2. В конфиге: `semantic_backend=SemanticMemoryBackend.POSTGRES`.
3. Выполнить миграцию `psql < migrations/20251114_add_pgvector.sql`.

## Тестирование
1. `python3 -m pytest dev/PDF_PARSER_2.0/tests/test_translation_system.py -vv`
2. `python3 -m kps.cli translate --input to_translate/... --glossary config/...`
3. При ошибках TermValidator временно добавьте `--skip-translation-qa` и зафиксируйте сегмент.

## Release checklist
1. Обновить `.env` и заcommитить изменённые YAML (если нужно).
2. Выполнить блоки «Прогрев глоссария», «Переиндексация», «Переключение на Postgres» (если применимо).
3. Прогнать полный пайплайн (например `КАРДИГАН peer gynt.docx`).
4. Проверить UI-service/dashboard — они читают те же ключи из `.env`.
5. Снять метрики: latency RAG, cache hitrate, затраты OpenAI.
6. Записать итог в release-notes и поставить тег `semantic-memory-refresh-YYY.MM.DD`.
