# KPS - Knitting Pattern System

**Интеллектуальная система перевода вязальных документов с самообучением и RAG**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

## 🎯 Что это?

KPS - это полная система для работы с вязальными документами:

- 📄 **Извлечение** текста из PDF (Docling AI / PyMuPDF)
- 🌍 **Перевод** с глоссарием и самообучением (ru/en/fr)
- 🧠 **База знаний** с RAG и автоматической категоризацией
- 📝 **Экспорт** в InDesign (IDML) с сохранением стилей
- ✅ **Контроль качества** переводов

---

## 🚀 Быстрый старт

### Установка

```bash
cd dev/PDF_PARSER_2.0
pip install -r requirements.txt

# Настроить API ключи
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Использование (3 строки!)

```python
from kps.core import UnifiedPipeline

pipeline = UnifiedPipeline()
result = pipeline.process("pattern.pdf", target_languages=["en", "fr"])
# → Готово! Переведённые файлы в output/
```

**Результат:**
- ✅ Текст извлечён (AI-powered Docling)
- ✅ Переведён с глоссарием (ru → en, ru → fr)
- ✅ Система самообучилась (запомнила термины)
- ✅ Экспорт в PDF и IDML

📖 **Подробнее:** [QUICKSTART.md](./QUICKSTART.md)

> 🔄 **Синхронизация глоссария**
>
> 1. Обновите `/Users/vostos/Dev/Hollywool patterns/глоссарий.json` (или `dev/PDF_PARSER_2.0/data/glossary.json`).
> 2. Запустите `dev/PDF_PARSER_2.0/.venv/bin/python scripts/sync_glossary.py` — скрипт обновит `config/glossaries/knitting_custom.yaml`.
> 3. Коммитьте и JSON, и YAML. UnifiedPipeline автоматически подхватит свежий YAML.

---

## ⚡ Ключевые возможности

### 1. Unified Pipeline - Всё в одном

Одна точка входа для всей системы:

```python
from kps.core import UnifiedPipeline

pipeline = UnifiedPipeline()
result = pipeline.process("document.pdf", ["en", "fr"])

print(f"Успех: {result.success}")
print(f"Cache hit: {result.cache_hit_rate:.0%}")  # 90% из кэша!
```

📖 [UNIFIED_PIPELINE.md](./docs/UNIFIED_PIPELINE.md)

---

### 2. Knowledge Base - Самообучаемая база знаний

```python
from kps.knowledge import KnowledgeBase

# Создать и загрузить
kb = KnowledgeBase("data/knowledge.db")
kb.ingest_folder("knowledge/", recursive=True)

# Система автоматически:
# - Разбила документы на секции (главы, разделы)
# - Категоризировала (patterns, techniques, yarns...)
# - Создала embeddings для поиска
# - Разбила на чанки с overlap для RAG

# Поиск
results = kb.search("как вязать косы")

# RAG для перевода
context = kb.get_translation_context("провяжите 2 петли", "ru", "en")
# → Добавит контекст из базы знаний к промпту ИИ!
```

**Технологии:**
- 📄 **Section Splitting** - 1 книга → 50+ секций с категориями
- 🧩 **Context-Aware Chunking** - чанки с overlap (контекст не теряется!)
- 🎯 **RAG** - Retrieval-Augmented Generation
- 🔍 **Semantic Search** - embeddings + cosine similarity

📖 Документация:
- [KNOWLEDGE_BASE.md](./docs/KNOWLEDGE_BASE.md)
- [SECTION_SPLITTING.md](./docs/SECTION_SPLITTING.md)
- [CONTEXT_AWARE_CHUNKING.md](./docs/CONTEXT_AWARE_CHUNKING.md)

---

### 3. Self-Learning Translation - Самообучение

```python
from kps.translation import GlossaryTranslator, SemanticMemory

memory = SemanticMemory("data/memory.db")
translator = GlossaryTranslator(orchestrator, glossary, memory=memory)

# Первый раз - AI перевод
result = translator.translate(segments, "en")
# → Сохранено в память

# Второй раз - из кэша
result = translator.translate(segments, "en")
# → Instant! Cache hit!

# Похожий текст - few-shot learning
result = translator.translate(similar_segments, "en")
# → ИИ видит примеры из памяти → лучше перевод!
```

**Особенности:**
- 💾 **Translation Memory** - кэш переводов
- 🔍 **Semantic Search** - находит похожие переводы
- 🎓 **Few-Shot Learning** - ИИ учится на примерах
- 📊 **Статистика** - usage_count, quality_score

📖 [SELF_LEARNING_TRANSLATION.md](./docs/SELF_LEARNING_TRANSLATION.md)

---

## 📁 Структура проекта

```
kps/
├── core/                      # Ядро системы
│   └── unified_pipeline.py   ⭐ Главная точка входа
│
├── translation/               # Система перевода
│   ├── orchestrator.py       # AI перевод (OpenAI/Anthropic)
│   ├── glossary_translator.py # Перевод с глоссарием
│   ├── translation_memory.py  # Кэш переводов
│   ├── semantic_memory.py     # Семантический поиск
│   └── glossary/              # Управление глоссарием
│
├── knowledge/                 # База знаний ⭐
│   ├── base.py               # KnowledgeBase (SQLite + embeddings)
│   ├── splitter.py           # Section splitting
│   ├── chunker.py            # Context-aware chunking
│   └── generator.py          # Генератор описаний
│
├── extraction/                # Извлечение текста
│   ├── docling_extractor.py  # AI extraction
│   └── pymupdf_extractor.py  # Быстрый fallback
│
├── indesign/                  # Экспорт в InDesign
│   ├── idml_exporter.py      # IDML export
│   └── style_manager.py      # Управление стилями
│
├── qa/                        # Контроль качества
│   └── pipeline.py           # QA pipeline
│
└── anchoring/                 # Система якорей
    └── markers.py            # Маркеры

examples/                      # Примеры
├── unified_pipeline_example.py          ⭐
├── knowledge_base_example.py            ⭐
├── section_splitting_example.py         ⭐
└── context_aware_chunking_example.py    ⭐

docs/                          # Документация
├── README.md                  # Этот файл
├── QUICKSTART.md              # Быстрый старт
├── UNIFIED_PIPELINE.md        # Главная система
├── KNOWLEDGE_BASE.md          # База знаний
├── SECTION_SPLITTING.md       # Умное разбиение
└── CONTEXT_AWARE_CHUNKING.md  # RAG с overlap
```

---

## 🏗️ Архитектура

```
┌───────────────────────────────────────┐
│    UnifiedPipeline (Entry Point)      │
└───────────────────────────────────────┘
             ↓
┌───────────────────────────────────────┐
│        Extraction Layer               │
│   (Docling AI / PyMuPDF)             │
└───────────────────────────────────────┘
             ↓
┌───────────────────────────────────────┐
│       Translation Layer               │
│  Glossary + Memory + Orchestrator     │
└───────────────────────────────────────┘
             ↓
┌───────────────────────────────────────┐
│      Knowledge Base Layer ⭐          │
│  Section Split + Chunk + RAG          │
└───────────────────────────────────────┘
             ↓
┌───────────────────────────────────────┐
│        Export Layer                   │
│     (PDF / IDML / JSON)              │
└───────────────────────────────────────┘
```

---

## 📚 Документация

### Основная

| Документ | Описание |
|----------|----------|
| [README.md](./README.md) | Этот файл - обзор системы |
| [QUICKSTART.md](./QUICKSTART.md) | Быстрый старт за 5 минут |
| [UNIFIED_PIPELINE.md](./docs/UNIFIED_PIPELINE.md) | Полное руководство по главной системе |

### База знаний ⭐

| Документ | Описание |
|----------|----------|
| [KNOWLEDGE_BASE.md](./docs/KNOWLEDGE_BASE.md) | Обзор базы знаний |
| [SECTION_SPLITTING.md](./docs/SECTION_SPLITTING.md) | Умное разбиение документов |
| [CONTEXT_AWARE_CHUNKING.md](./docs/CONTEXT_AWARE_CHUNKING.md) | RAG с overlap |

### Самообучение

| Документ | Описание |
|----------|----------|
| [SELF_LEARNING_TRANSLATION.md](./docs/SELF_LEARNING_TRANSLATION.md) | Система самообучения |
| [SEMANTIC_MEMORY_ARCHITECTURE.md](./docs/SEMANTIC_MEMORY_ARCHITECTURE.md) | Архитектура памяти |

---

## 💡 Примеры

### Базовое использование

```bash
# Unified Pipeline
python examples/unified_pipeline_example.py

# Self-Learning
python examples/self_learning_translation_example.py
```

### База знаний

```bash
# Knowledge Base
python examples/knowledge_base_example.py

# Section Splitting
python examples/section_splitting_example.py

# Context-Aware Chunking
python examples/context_aware_chunking_example.py
```

---

## 🎓 Обучение

### Новичок → Опытный пользователь

1. **Прочитать:** [QUICKSTART.md](./QUICKSTART.md) (5 мин)
2. **Запустить:** `examples/unified_pipeline_example.py`
3. **Изучить:** [UNIFIED_PIPELINE.md](./docs/UNIFIED_PIPELINE.md)
4. **Углубиться:** [KNOWLEDGE_BASE.md](./docs/KNOWLEDGE_BASE.md)

---

## 📊 Производительность

| Операция | Время | Примечание |
|----------|-------|------------|
| Extraction (Docling) | ~2s/page | AI-powered |
| Extraction (PyMuPDF) | ~0.1s/page | Fast fallback |
| Translation (cached) | <1ms | ⚡ Instant! |
| Translation (AI) | ~3s | OpenAI API |
| Semantic search | ~50ms | 10K entries |
| Knowledge ingestion | ~5s | 100 documents |

### Кэш эффективность

- **First run:** 100% AI
- **Second run:** 90% cache hit
- **Similar patterns:** 70% cache + few-shot

---

## 🔧 Конфигурация

### Pipeline Config

```python
from kps.core import PipelineConfig, ExtractionMethod

config = PipelineConfig(
    extraction_method=ExtractionMethod.DOCLING,  # AI extraction
    enable_few_shot=True,                         # Самообучение
    enable_auto_suggestions=True,                 # Автопредложения
)

pipeline = UnifiedPipeline(config)
```

### Knowledge Base Config

```python
from kps.knowledge import KnowledgeBase, ChunkingStrategy

kb = KnowledgeBase(
    "data/knowledge.db",
    split_sections=True,                          # Разбиение на секции
    use_chunking=True,                            # Chunking с overlap
    chunk_size=1000,                              # Размер чанка
    chunk_overlap=200,                            # Overlap (20%)
    model_preset="claude-3"                       # Авто-настройка
)
```

---

## 🐛 Troubleshooting

**Q: Модули не найдены**
```bash
pip install -r requirements.txt
```

**Q: API ключи не работают**
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Q: Медленный перевод**
```python
# Включите semantic memory для кэша
config = PipelineConfig(memory_type=MemoryType.SEMANTIC)
```

**Q: Низкое качество перевода**
```python
# Используйте базу знаний для RAG
kb = KnowledgeBase("data/knowledge.db")
kb.ingest_folder("knowledge/")
pipeline.translator.knowledge_base = kb
```

---

## 🎯 Roadmap

- [x] Unified Pipeline
- [x] Self-Learning Translation
- [x] Semantic Memory
- [x] Knowledge Base
- [x] Section Splitting
- [x] Context-Aware Chunking
- [ ] Web UI
- [ ] REST API
- [ ] Multi-threading
- [ ] Cloud deployment

---

## 📝 Лицензия

MIT License

---

## 📞 Поддержка

- **Документация:** [docs/](./docs/)
- **Примеры:** [examples/](./examples/)
- **Issues:** GitHub Issues

---

**KPS - Умная система перевода с самообучением и RAG** 🧶✨
