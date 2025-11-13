# Usage Guide - KPS

**Полное руководство по работе с системой**

---

## 📖 Содержание

1. [Введение](#введение)
2. [Установка](#установка)
3. [Базовое использование](#базовое-использование)
4. [Продвинутое использование](#продвинутое-использование)
5. [База знаний](#база-знаний)
6. [Самообучение](#самообучение)
7. [Конфигурация](#конфигурация)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Введение

KPS - это интеллектуальная система перевода вязальных документов с тремя ключевыми возможностями:

1. **Unified Pipeline** - простая точка входа для всей системы
2. **Knowledge Base** - самообучаемая база знаний с RAG
3. **Self-Learning** - система запоминает переводы и учится

---

## Установка

### Требования

- Python 3.11+
- API ключ OpenAI или Anthropic

### Установка зависимостей

```bash
cd dev/PDF_PARSER_2.0
pip install -r requirements.txt
```

#### Доп. зависимости для DOCX/PDF

- **Pandoc** — нужен для DOCX: скачайте с официального сайта и убедитесь, что бинарь `pandoc` доступен в `$PATH`.citeturn0search0
- **WeasyPrint + системные библиотеки** — для PDF рендера требуется установленный `weasyprint` и пакеты `cairo`, `Pango`, `GDK-PixBuf` (на macOS это `brew install pango cairo gdk-pixbuf libffi`). Подробные инструкции — в официальном гайде.citeturn5search0
- (Опционально) `pip install weasyprint markdown` — чтобы локально пересобирать HTML → PDF из сохранённых снапшотов.

### Настройка API ключей

```bash
# OpenAI (рекомендуется)
export OPENAI_API_KEY="sk-..."

# Или Anthropic Claude
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Базовое использование

### Простейший перевод

```python
from kps.core import UnifiedPipeline

# Создать
pipeline = UnifiedPipeline()

# Перевести
result = pipeline.process("pattern.pdf", target_languages=["en", "fr"])

# Проверить
if result.success:
    print(f"✅ Готово!")
    print(f"Файлы: {result.output_files}")
else:
    print(f"❌ Ошибка: {result.error}")
```

**Результат:**
- `output/pattern_EN/pattern_EN.pdf` - английская версия
- `output/pattern_EN/pattern_EN.idml` - для InDesign
- `output/pattern_FR/pattern_FR.pdf` - французская версия
- `output/pattern_FR/pattern_FR.idml` - для InDesign

---

### С настройками

```python
from kps.core import UnifiedPipeline, PipelineConfig
from kps.core import ExtractionMethod, MemoryType

# Настроить
config = PipelineConfig(
    # Extraction
    extraction_method=ExtractionMethod.DOCLING,  # AI extraction

    # Translation
    enable_few_shot=True,                        # Few-shot learning
    enable_auto_suggestions=True,                # Автопредложения

    # Memory
    memory_type=MemoryType.SEMANTIC,             # Semantic cache

    # Output
    output_formats=["pdf", "idml"]               # Форматы
)

# Создать
pipeline = UnifiedPipeline(config)

# Перевести
result = pipeline.process("document.pdf", ["en"])
```

---

## Продвинутое использование

### Поэтапная обработка

```python
from kps.core import UnifiedPipeline

pipeline = UnifiedPipeline()

# 1. Extraction
extraction_result = pipeline._extract_content("document.pdf")
print(f"Извлечено: {len(extraction_result.segments)} сегментов")

# 2. Segmentation
segments = pipeline._segment_content(extraction_result)
print(f"Сегментов для перевода: {len(segments)}")

# 3. Language detection
source_lang = pipeline._detect_language(segments)
print(f"Язык: {source_lang}")

# 4. Translation
target_lang = "en"
translated = pipeline.translator.translate(segments, target_lang, source_lang)
print(f"Переведено: {len(translated.translated_segments)} сегментов")

# 5. Export
output_file = pipeline._export_translation(
    translated.translated_segments,
    "output/result.pdf"
)
print(f"Экспорт: {output_file}")
```

---

### Множественный перевод

```python
from kps.core import UnifiedPipeline

pipeline = UnifiedPipeline()

# Перевести на несколько языков
result = pipeline.process(
    "document.pdf",
    target_languages=["en", "fr", "de", "es"]
)

# Проверить результаты
for lang, files in result.output_files.items():
    print(f"{lang}: {files}")

# Output:
# en: ['output/document_EN/document_EN.pdf', 'output/document_EN/document_EN.idml']
# fr: ['output/document_FR/document_FR.pdf', 'output/document_FR/document_FR.idml']
# ...
```

---

### Проверка кэша

```python
from kps.core import UnifiedPipeline

pipeline = UnifiedPipeline()

# Первый раз - AI перевод
result1 = pipeline.process("document.pdf", ["en"])
print(f"Cache hit rate: {result1.cache_hit_rate:.0%}")  # 0% (новый документ)
print(f"Translation time: {result1.translation_time}s")

# Второй раз - из кэша
result2 = pipeline.process("document.pdf", ["en"])
print(f"Cache hit rate: {result2.cache_hit_rate:.0%}")  # 90%+ (из памяти)
print(f"Translation time: {result2.translation_time}s")   # <1s!
```

---

## База знаний

### Создание и загрузка

```python
from kps.knowledge import KnowledgeBase

# Создать базу
kb = KnowledgeBase("data/knowledge.db")

# Загрузить документы
kb.ingest_folder("knowledge/books/", recursive=True)
kb.ingest_folder("knowledge/patterns/", recursive=True)
kb.ingest_folder("knowledge/techniques/", recursive=True)

# Статистика
stats = kb.get_statistics()
print(f"Загружено: {stats['total_entries']} записей")
print(f"По категориям: {stats['by_category']}")
```

**Что происходит:**
1. Документы разбиваются на **секции** (главы, разделы)
2. Каждая секция **категоризируется** (patterns, techniques, yarns...)
3. Секции разбиваются на **чанки с overlap** (сохранение контекста)
4. Создаются **embeddings** для семантического поиска
5. Всё сохраняется в **SQLite** базу

---

### Поиск в базе

```python
from kps.knowledge import KnowledgeBase, KnowledgeCategory

kb = KnowledgeBase("data/knowledge.db")

# Общий поиск
results = kb.search("как вязать косы", limit=5)
for r in results:
    print(f"- {r.title} ({r.category.value})")

# Поиск в категории
results = kb.search(
    "косы",
    category=KnowledgeCategory.TECHNIQUE,
    limit=3
)

# Поиск на языке
results = kb.search("cables", language="en", limit=5)
```

---

### Интеграция с pipeline

```python
from kps.core import UnifiedPipeline
from kps.knowledge import KnowledgeBase

# 1. Создать базу знаний
kb = KnowledgeBase("data/knowledge.db")
kb.ingest_folder("knowledge/", recursive=True)

# 2. Создать pipeline
pipeline = UnifiedPipeline()

# 3. Подключить базу знаний
pipeline.translator.knowledge_base = kb

# 4. Теперь перевод использует RAG!
result = pipeline.process("document.pdf", ["en"])

# Система автоматически:
# - Ищет похожие примеры в базе знаний
# - Добавляет контекст к промпту AI
# - Получает более точный перевод!
```

---

### Настройка chunking

```python
from kps.knowledge import KnowledgeBase, ChunkingStrategy

# С настройками chunking
kb = KnowledgeBase(
    "data/knowledge.db",

    # Section splitting
    split_sections=True,                           # Разбиение на секции
    split_strategy=SplitStrategy.AUTO,             # Авто-определение

    # Context-aware chunking
    use_chunking=True,                             # Включить chunking
    chunk_size=1000,                               # Размер чанка (символов)
    chunk_overlap=200,                             # Overlap (20%)
    chunking_strategy=ChunkingStrategy.SEMANTIC,   # Семантическое

    # Или использовать предустановку
    model_preset="claude-3"  # Авто-настройка для Claude 3
)

kb.ingest_folder("knowledge/")
```

**Model Presets:**
- `gpt-3.5`: chunk_size=800, overlap=150
- `gpt-4`: chunk_size=1200, overlap=200
- `claude-2`: chunk_size=2000, overlap=300
- `claude-3`: chunk_size=3000, overlap=400

---

## Самообучение

### Translation Memory

```python
from kps.translation import TranslationMemory, GlossaryTranslator

# Создать memory
memory = TranslationMemory("data/memory.json")

# Использовать с переводчиком
translator = GlossaryTranslator(
    orchestrator=orchestrator,
    glossary=glossary,
    memory=memory
)

# Первый перевод - через AI
result = translator.translate(segments, "en")
# → Сохранено в память

# Второй перевод - из кэша
result = translator.translate(segments, "en")
# → Cache hit! Instant!

# Статистика
stats = memory.get_statistics("ru", "en")
print(f"Переводов в памяти: {stats['total_translations']}")
print(f"Средний quality score: {stats['avg_quality']:.2f}")
```

---

### Semantic Memory

```python
from kps.translation import SemanticMemory, GlossaryTranslator

# Создать semantic memory (с embeddings)
memory = SemanticMemory("data/memory.db", use_embeddings=True)

# Использовать
translator = GlossaryTranslator(
    orchestrator=orchestrator,
    glossary=glossary,
    memory=memory
)

# Перевод
result = translator.translate(segments, "en")

# Похожий текст - найдёт в памяти
similar_segments = [...]  # Похожий текст
result = translator.translate(similar_segments, "en")
# → Найдены похожие переводы (semantic search)
# → Few-shot learning с примерами
# → Более точный перевод!

# Поиск похожих переводов
similar = memory.find_similar_translations(
    "Провяжите 2 петли вместе",
    source_lang="ru",
    target_lang="en",
    threshold=0.85
)

for s in similar:
    print(f"{s.source_text} → {s.translated_text}")
    print(f"Similarity: {s.similarity:.2%}")
```

---

### Few-Shot Learning

```python
from kps.translation import GlossaryTranslator, SemanticMemory

memory = SemanticMemory("data/memory.db")

# Включить few-shot learning
translator = GlossaryTranslator(
    orchestrator=orchestrator,
    glossary=glossary,
    memory=memory,
    enable_few_shot=True  # ⭐
)

# Перевод с few-shot learning
result = translator.translate(segments, "en", source_lang="ru")

# Система автоматически:
# 1. Ищет 3-5 лучших примеров из памяти (highest quality_score)
# 2. Добавляет их к промпту AI:
#    "Examples:
#     - лицевая петля → knit stitch
#     - изнаночная петля → purl stitch
#     ...
#     Now translate: провяжите 2 петли вместе"
# 3. AI видит примеры → более точный перевод!
```

---

## Конфигурация

### Pipeline Config

```python
from kps.core import PipelineConfig
from kps.core import ExtractionMethod, MemoryType

config = PipelineConfig(
    # Extraction
    extraction_method=ExtractionMethod.DOCLING,  # AUTO / DOCLING / PYMUPDF
    fallback_to_pymupdf=True,                    # Fallback если Docling failed

    # Translation
    enable_few_shot=True,                        # Few-shot learning
    enable_auto_suggestions=True,                # Автопредложения

    # Memory
    memory_type=MemoryType.SEMANTIC,             # NONE / SIMPLE / SEMANTIC

    # Knowledge Base
    use_knowledge_base=True,                     # Использовать KB для RAG

    # Output
    output_formats=["pdf", "idml"],              # Форматы экспорта
    output_dir="output",                         # Папка для результатов
)

pipeline = UnifiedPipeline(config)
```

---

### Environment Variables

```bash
# API Keys
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Paths
export GLOSSARY_PATH="data/glossary.json"
export MEMORY_DB_PATH="data/memory.db"
export KNOWLEDGE_DB_PATH="data/knowledge.db"

# Directories
export OUTPUT_DIR="output"
export KNOWLEDGE_DIR="knowledge"
```

---

### Glossary Config

```json
{
  "knitting": {
    "ru": {
      "en": {
        "лицевая петля": "knit stitch",
        "изнаночная петля": "purl stitch",
        "накид": "yarn over",
        "2 вместе": "knit 2 together (k2tog)"
      },
      "fr": {
        "лицевая петля": "maille endroit",
        "изнаночная петля": "maille envers"
      }
    }
  }
}
```

---

## Best Practices

### 1. Всегда используйте UnifiedPipeline

```python
# ✅ Правильно
from kps.core import UnifiedPipeline
pipeline = UnifiedPipeline()
result = pipeline.process("doc.pdf", ["en"])

# ❌ Неправильно (низкоуровневый API)
from kps.extraction import DoclingExtractor
extractor = DoclingExtractor()
# ... много кода
```

---

### 2. Используйте базу знаний

```python
# ✅ Правильно - с базой знаний (RAG)
kb = KnowledgeBase("data/knowledge.db")
kb.ingest_folder("knowledge/")
pipeline.translator.knowledge_base = kb

# ❌ Без базы знаний - качество ниже
```

---

### 3. Включайте semantic memory

```python
# ✅ Правильно - semantic memory
config = PipelineConfig(
    memory_type=MemoryType.SEMANTIC,  # Semantic search + embeddings
    enable_few_shot=True               # Few-shot learning
)

# ❌ Без памяти - нет кэша, нет обучения
config = PipelineConfig(memory_type=MemoryType.NONE)
```

---

### 4. Пополняйте базу знаний

```python
# Регулярно добавляйте новые документы
kb = KnowledgeBase("data/knowledge.db")

# Загрузить новые книги
kb.ingest_folder("knowledge/new_books/", recursive=True)

# Загрузить переведённые документы
kb.ingest_folder("output/", recursive=True)

# Система самообучается!
```

---

### 5. Мониторьте качество

```python
# Проверяйте статистику
result = pipeline.process("doc.pdf", ["en"])

print(f"Cache hit rate: {result.cache_hit_rate:.0%}")  # Цель: >70%
print(f"Translation time: {result.translation_time}s") # Цель: <10s
print(f"Success: {result.success}")                    # Должно быть True

# Проверяйте память
stats = memory.get_statistics("ru", "en")
print(f"Translations: {stats['total_translations']}")  # Растёт с каждым переводом
print(f"Avg quality: {stats['avg_quality']:.2f}")     # Должен быть >0.8
```

---

## Troubleshooting

### Проблема: ModuleNotFoundError

```bash
pip install -r requirements.txt
```

---

### Проблема: API key not found

```bash
# Проверить
echo $OPENAI_API_KEY

# Установить
export OPENAI_API_KEY="sk-..."
```

---

### Проблема: Медленный перевод

**Причина:** Нет кэша, всё через AI

**Решение:**
```python
config = PipelineConfig(
    memory_type=MemoryType.SEMANTIC,  # Включить кэш
    enable_few_shot=True               # Few-shot
)
```

---

### Проблема: Низкое качество перевода

**Причина:** Нет контекста для AI

**Решение:**
```python
# 1. Создать базу знаний
kb = KnowledgeBase("data/knowledge.db")
kb.ingest_folder("knowledge/", recursive=True)

# 2. Подключить к pipeline
pipeline.translator.knowledge_base = kb

# 3. Теперь RAG добавляет контекст!
```

---

### Проблема: Теряется контекст на границах чанков

**Причина:** Нет overlap

**Решение:**
```python
kb = KnowledgeBase(
    "data/knowledge.db",
    use_chunking=True,      # Включить chunking
    chunk_overlap=200       # Overlap 20%
)
```

---

### Проблема: Ошибка при извлечении

**Причина:** Docling failed

**Решение:**
```python
config = PipelineConfig(
    extraction_method=ExtractionMethod.PYMUPDF,  # Использовать fallback
    # или
    fallback_to_pymupdf=True                     # Авто-fallback
)
```

---

## Заключение

KPS - это комплексная система с 3 ключевыми компонентами:

1. **Unified Pipeline** - простая точка входа
2. **Knowledge Base** - самообучаемая база с RAG
3. **Self-Learning** - система запоминает и учится

**Минимальный код:**
```python
from kps.core import UnifiedPipeline

pipeline = UnifiedPipeline()
result = pipeline.process("doc.pdf", ["en", "fr"])
```

**Максимальная мощь:**
```python
from kps.core import UnifiedPipeline, PipelineConfig
from kps.knowledge import KnowledgeBase

# База знаний
kb = KnowledgeBase("data/knowledge.db")
kb.ingest_folder("knowledge/", recursive=True)

# Pipeline
config = PipelineConfig(
    extraction_method=ExtractionMethod.DOCLING,
    memory_type=MemoryType.SEMANTIC,
    enable_few_shot=True
)

pipeline = UnifiedPipeline(config)
pipeline.translator.knowledge_base = kb

# Перевод с максимальным качеством!
result = pipeline.process("doc.pdf", ["en"])
```

---

**Следующие шаги:**
- Изучите [KNOWLEDGE_BASE.md](./docs/KNOWLEDGE_BASE.md)
- Изучите [SECTION_SPLITTING.md](./docs/SECTION_SPLITTING.md)
- Изучите [CONTEXT_AWARE_CHUNKING.md](./docs/CONTEXT_AWARE_CHUNKING.md)

**KPS - умная система с самообучением и RAG!** 🧶✨
