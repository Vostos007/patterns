# Refactoring Notes - KPS

**Список изменений для оптимизации проекта**

---

## ❌ Файлы для удаления (устаревшие)

### Translation (устаревшие компоненты)

```bash
# Удалить устаревшие файлы
rm kps/translation/multi_stage_pipeline.py    # Заменён unified_pipeline
rm kps/translation/language_router.py          # Устарел
rm kps/translation/verification.py             # Устарел
rm kps/translation/glossary/advanced_matcher.py # Функциональность в glossary_translator
```

**Причина:** Система была упрощена. MultiStage pipeline заменён на Unified Pipeline.

---

### Examples (устаревшие примеры)

```bash
# Удалить устаревшие примеры
rm examples/multi_stage_translation_demo.py        # Устарел
rm examples/translation_orchestrator_enhanced.py   # Устарел
rm examples/simple_translation_example.py          # Дублирует unified_pipeline_example
rm examples/anchoring_example.py                   # Специфичен для QA
rm examples/demo_marker_injection.py               # Специфичен для QA
rm examples/simple_marker_demo.py                  # Специфичен для QA
rm examples/style_manager_demo.py                  # Специфичен для InDesign
rm examples/pymupdf_extraction_demo.py             # Низкоуровневый
rm examples/docling_extraction_demo.py             # Низкоуровневый
```

**Причина:** Старые примеры для устаревших компонентов или слишком низкоуровневые.

---

### Documentation (устаревшая)

```bash
# Удалить устаревшую документацию
rm docs/SIMPLIFIED_TRANSLATION.md  # Заменено на UNIFIED_PIPELINE.md

# Удалить старые папки
rm -rf docs/guides/
rm -rf docs/plans/
rm -rf docs/reference/
rm -rf docs/reports/
rm -rf docs/summaries/
```

**Причина:** Старая структура документации. Новая документация в корне docs/.

---

## ✅ Актуальные файлы

### Core (ядро системы)

```
kps/core/
├── unified_pipeline.py   ⭐ Главная точка входа
├── document.py           ✓ Document model
├── assets.py             ✓ Asset management
├── bbox.py               ✓ BBox utilities
└── placeholders.py       ✓ Placeholder system
```

---

### Translation (система перевода)

```
kps/translation/
├── orchestrator.py          ⭐ AI translation (OpenAI/Anthropic)
├── glossary_translator.py  ⭐ Translation with glossary
├── translation_memory.py    ⭐ Simple cache
├── semantic_memory.py       ⭐ Semantic cache with embeddings
└── glossary/
    ├── manager.py           ✓ Glossary management
    └── selector.py          ✓ Language selector
```

---

### Knowledge (база знаний) ⭐ NEW

```
kps/knowledge/
├── base.py       ⭐ KnowledgeBase (main class)
├── splitter.py   ⭐ Section splitting
├── chunker.py    ⭐ Context-aware chunking
└── generator.py  ⭐ Pattern generator
```

---

### Extraction (извлечение)

```
kps/extraction/
├── docling_extractor.py   ✓ AI extraction (recommended)
├── pymupdf_extractor.py   ✓ Fast fallback
└── segmenter.py           ✓ Text segmentation
```

---

### InDesign (экспорт)

```
kps/indesign/
├── idml_exporter.py    ✓ IDML export
├── idml_parser.py      ✓ IDML parsing
├── style_manager.py    ✓ Style management
└── ... (много других файлов, все нужны)
```

---

### QA (контроль качества)

```
kps/qa/
└── pipeline.py    ✓ QA pipeline
└── ... (много файлов, все нужны для QA)
```

---

### Anchoring (якоря)

```
kps/anchoring/
├── anchor.py      ✓ Anchor system
├── markers.py     ✓ Markers
└── columns.py     ✓ Column detection
```

---

## 📁 Рекомендуемая структура после чистки

```
dev/PDF_PARSER_2.0/
├── README.md                      ⭐ Главный файл
├── QUICKSTART.md                  ⭐ Быстрый старт
├── requirements.txt
│
├── kps/                           # Исходный код
│   ├── core/                      # Ядро
│   ├── translation/               # Перевод
│   ├── knowledge/                 # База знаний ⭐
│   ├── extraction/                # Извлечение
│   ├── indesign/                  # InDesign
│   ├── qa/                        # QA
│   └── anchoring/                 # Anchoring
│
├── examples/                      # Примеры
│   ├── unified_pipeline_example.py          ⭐
│   ├── knowledge_base_example.py            ⭐
│   ├── section_splitting_example.py         ⭐
│   ├── context_aware_chunking_example.py    ⭐
│   ├── semantic_memory_example.py           ✓
│   └── self_learning_translation_example.py ✓
│
├── docs/                          # Документация
│   ├── UNIFIED_PIPELINE.md        ⭐
│   ├── KNOWLEDGE_BASE.md          ⭐
│   ├── SECTION_SPLITTING.md       ⭐
│   ├── CONTEXT_AWARE_CHUNKING.md  ⭐
│   ├── SELF_LEARNING_TRANSLATION.md
│   └── SEMANTIC_MEMORY_ARCHITECTURE.md
│
├── data/                          # Данные
│   ├── glossary.json
│   ├── memory.db
│   └── knowledge.db
│
├── knowledge/                     # Документы для обучения
│   ├── patterns/
│   ├── techniques/
│   ├── yarns/
│   └── projects/
│
└── tests/                         # Тесты
    └── test_translation_system.py
```

---

## 🔧 Команды для рефакторинга

### Шаг 1: Backup (обязательно!)

```bash
cd dev/PDF_PARSER_2.0
git add -A
git commit -m "backup before refactoring"
```

---

### Шаг 2: Удалить устаревшие файлы

```bash
# Translation
rm kps/translation/multi_stage_pipeline.py
rm kps/translation/language_router.py
rm kps/translation/verification.py
rm kps/translation/glossary/advanced_matcher.py

# Examples
rm examples/multi_stage_translation_demo.py
rm examples/translation_orchestrator_enhanced.py
rm examples/simple_translation_example.py
rm examples/anchoring_example.py
rm examples/demo_marker_injection.py
rm examples/simple_marker_demo.py
rm examples/style_manager_demo.py
rm examples/pymupdf_extraction_demo.py
rm examples/docling_extraction_demo.py

# Documentation
rm docs/SIMPLIFIED_TRANSLATION.md
rm -rf docs/guides/ docs/plans/ docs/reference/ docs/reports/ docs/summaries/
```

---

### Шаг 3: Commit изменения

```bash
git add -A
git commit -m "refactor: remove obsolete files and reorganize structure

Removed:
- Obsolete multi-stage translation system
- Outdated examples
- Old documentation structure

Kept:
- UnifiedPipeline (main entry point)
- Knowledge Base system
- Self-learning translation
- All production code
"
```

---

## 📊 Статистика

### До рефакторинга

```
Total files: ~150
Code files: ~80
Examples: 15
Docs: 20+ files
```

### После рефакторинга

```
Total files: ~100 (-33%)
Code files: ~70 (-12%)
Examples: 6 (-60%, только актуальные)
Docs: 7 (-65%, только актуальные)
```

**Упрощение: ~35% меньше файлов, но вся функциональность сохранена!**

---

## ✅ Проверка после рефакторинга

```bash
# 1. Проверить импорты
python -c "from kps.core import UnifiedPipeline; print('✓ Core OK')"
python -c "from kps.knowledge import KnowledgeBase; print('✓ Knowledge OK')"
python -c "from kps.translation import GlossaryTranslator; print('✓ Translation OK')"

# 2. Запустить примеры
python examples/unified_pipeline_example.py
python examples/knowledge_base_example.py

# 3. Проверить документацию
ls docs/*.md | wc -l  # Должно быть ~7 файлов
```

---

## 💡 Следующие шаги

1. **Создать tests/** папку с тестами
2. **Добавить CI/CD** (GitHub Actions)
3. **Создать Docker** образ
4. **Добавить Web UI** (опционально)
5. **Опубликовать** в PyPI (опционально)

---

## 🎯 Результат

После рефакторинга проект:

✅ **Проще** - меньше файлов, чёткая структура
✅ **Понятнее** - только актуальные примеры и документация
✅ **Чище** - убраны устаревшие компоненты
✅ **Мощнее** - сохранена вся функциональность
✅ **Документирован** - полная и актуальная документация

---

**Важно:** Не удаляйте файлы в `kps/indesign/`, `kps/qa/`, `kps/anchoring/` - они все нужны для production!
