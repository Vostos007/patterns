# Quick Start - KPS

**Начните работать с KPS за 5 минут!**

---

## Шаг 1: Установка (1 минута)

```bash
cd dev/PDF_PARSER_2.0
pip install -r requirements.txt

# Настроить API ключи
export OPENAI_API_KEY="sk-..."
# или
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Шаг 2: Простейший перевод (2 минуты)

### Вариант 1: Автоматический (рекомендуется)

```python
from kps.core import UnifiedPipeline

# 1. Создать pipeline
pipeline = UnifiedPipeline()

# 2. Перевести документ
result = pipeline.process("pattern.pdf", target_languages=["en", "fr"])

# 3. Готово!
print(f"Успех: {result.success}")
print(f"Выходные файлы: {result.output_files}")
```

**Что произошло:**
- ✅ Текст извлечён из PDF (AI Docling или PyMuPDF)
- ✅ Переведён с глоссарием (ru → en, ru → fr)
- ✅ Система самообучилась (сохранила в память)
- ✅ Экспортировано в PDF и IDML
- ✅ Файлы в папке `output/`

### Вариант 2: Пошаговый (контроль)

```python
from kps.core import UnifiedPipeline, PipelineConfig, ExtractionMethod

# Настроить
config = PipelineConfig(
    extraction_method=ExtractionMethod.DOCLING,  # AI extraction
    enable_few_shot=True,                        # Самообучение
    enable_auto_suggestions=True                 # Автопредложения
)

# Создать
pipeline = UnifiedPipeline(config)

# Обработать
result = pipeline.process("document.pdf", ["en"])

# Проверить
print(f"Cache hit rate: {result.cache_hit_rate:.0%}")
print(f"Translation stats: {result.translation_stats}")
```

---

## Шаг 3: Добавить базу знаний (2 минуты)

### Создать базу знаний

```python
from kps.knowledge import KnowledgeBase

# 1. Создать базу
kb = KnowledgeBase("data/knowledge.db")

# 2. Загрузить документы
kb.ingest_folder("knowledge/", recursive=True)
# → Система автоматически разобьёт на секции,
#   категоризирует, создаст embeddings

# 3. Проверить
stats = kb.get_statistics()
print(f"Загружено: {stats['total_entries']} секций")
print(f"По категориям: {stats['by_category']}")
```

### Использовать с pipeline

```python
from kps.core import UnifiedPipeline
from kps.knowledge import KnowledgeBase

# Создать базу знаний
kb = KnowledgeBase("data/knowledge.db")
kb.ingest_folder("knowledge/", recursive=True)

# Создать pipeline
pipeline = UnifiedPipeline()

# Подключить базу знаний (для RAG)
pipeline.translator.knowledge_base = kb

# Теперь перевод использует RAG!
result = pipeline.process("document.pdf", ["en"])

# Система автоматически:
# ✅ Ищет похожие примеры в базе
# ✅ Добавляет контекст к промпту AI
# ✅ Получает более точный перевод!
```

---

## Примеры

### Пример 1: Базовый перевод

```python
from kps.core import UnifiedPipeline

pipeline = UnifiedPipeline()
result = pipeline.process("pattern.pdf", ["en", "fr"])

if result.success:
    print("✅ Перевод завершён!")
    print(f"Файлы: {result.output_files}")
else:
    print(f"❌ Ошибка: {result.error}")
```

### Пример 2: С настройками

```python
from kps.core import UnifiedPipeline, PipelineConfig
from kps.core import ExtractionMethod, MemoryType

config = PipelineConfig(
    extraction_method=ExtractionMethod.DOCLING,  # AI extraction
    memory_type=MemoryType.SEMANTIC,             # Semantic memory
    enable_few_shot=True,                        # Few-shot learning
    output_formats=["pdf", "idml"]               # Output formats
)

pipeline = UnifiedPipeline(config)
result = pipeline.process("document.pdf", ["en"])
```

### Пример 3: Проверка кэша

```python
from kps.core import UnifiedPipeline

pipeline = UnifiedPipeline()

# Первый запуск
result1 = pipeline.process("document.pdf", ["en"])
print(f"Cache hit: {result1.cache_hit_rate:.0%}")  # 0%

# Второй запуск (тот же документ)
result2 = pipeline.process("document.pdf", ["en"])
print(f"Cache hit: {result2.cache_hit_rate:.0%}")  # 90%+!
```

### Пример 4: База знаний

```python
from kps.knowledge import KnowledgeBase

# Создать
kb = KnowledgeBase("data/knowledge.db")

# Загрузить документы
kb.ingest_folder("knowledge/books/", recursive=True)
kb.ingest_folder("knowledge/patterns/", recursive=True)

# Поиск
results = kb.search("как вязать косы", limit=5)
for r in results:
    print(f"- {r.title} ({r.category.value})")

# Статистика
stats = kb.get_statistics()
print(f"\nВсего: {stats['total_entries']} записей")
print("По категориям:")
for cat, count in stats['by_category'].items():
    print(f"  {cat}: {count}")
```

---

## Структура папок

```
dev/PDF_PARSER_2.0/
├── data/                    # Данные
│   ├── knowledge.db        # База знаний
│   ├── memory.db           # Translation memory
│   └── glossary.json       # Глоссарий
│
├── knowledge/               # Документы для обучения
│   ├── patterns/           # Узоры
│   ├── techniques/         # Техники
│   ├── yarns/              # Пряжа
│   └── projects/           # Готовые проекты
│
├── input/                   # Входные документы
│   └── pattern.pdf
│
└── output/                  # Результаты
    ├── pattern_EN/
    │   ├── pattern_EN.pdf
    │   └── pattern_EN.idml
    └── pattern_FR/
        ├── pattern_FR.pdf
        └── pattern_FR.idml
```

---

## Конфигурация

### API ключи

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic Claude (альтернатива)
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Пути (опционально)

```bash
export GLOSSARY_PATH="data/glossary.json"
export MEMORY_DB_PATH="data/memory.db"
export KNOWLEDGE_DB_PATH="data/knowledge.db"
```

---

## Troubleshooting

### Проблема: Модули не найдены

```bash
pip install -r requirements.txt
```

### Проблема: API ключ не работает

```bash
# Проверить, что ключ экспортирован
echo $OPENAI_API_KEY

# Если пусто:
export OPENAI_API_KEY="sk-..."
```

### Проблема: Медленный перевод

```python
# Включить semantic memory для кэша
from kps.core import PipelineConfig, MemoryType

config = PipelineConfig(
    memory_type=MemoryType.SEMANTIC,  # Включить кэш
    enable_few_shot=True               # Few-shot learning
)

pipeline = UnifiedPipeline(config)
```

### Проблема: Низкое качество

```python
# Использовать базу знаний для RAG
kb = KnowledgeBase("data/knowledge.db")
kb.ingest_folder("knowledge/", recursive=True)

pipeline.translator.knowledge_base = kb
# → Теперь переводы точнее!
```

---

## Следующие шаги

1. **Изучить примеры:**
   ```bash
   python examples/unified_pipeline_example.py
   python examples/knowledge_base_example.py
   ```

2. **Прочитать документацию:**
   - [UNIFIED_PIPELINE.md](./docs/UNIFIED_PIPELINE.md) - Полное руководство
   - [KNOWLEDGE_BASE.md](./docs/KNOWLEDGE_BASE.md) - База знаний
   - [SELF_LEARNING_TRANSLATION.md](./docs/SELF_LEARNING_TRANSLATION.md) - Самообучение

3. **Настроить под себя:**
   - Добавить свой глоссарий
   - Загрузить документы в базу знаний
   - Настроить конфигурацию pipeline

---

## Команды для копирования

```bash
# Установка
cd dev/PDF_PARSER_2.0
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."

# Запуск примера
python -c "
from kps.core import UnifiedPipeline

pipeline = UnifiedPipeline()
result = pipeline.process('input/pattern.pdf', ['en', 'fr'])
print(f'Успех: {result.success}')
print(f'Файлы: {result.output_files}')
"

# Создание базы знаний
python -c "
from kps.knowledge import KnowledgeBase

kb = KnowledgeBase('data/knowledge.db')
kb.ingest_folder('knowledge/', recursive=True)

stats = kb.get_statistics()
print(f'Загружено: {stats[\"total_entries\"]} записей')
"
```

---

## Полная документация

- [README.md](./README.md) - Обзор системы
- [UNIFIED_PIPELINE.md](./docs/UNIFIED_PIPELINE.md) - Главная система
- [KNOWLEDGE_BASE.md](./docs/KNOWLEDGE_BASE.md) - База знаний
- [SECTION_SPLITTING.md](./docs/SECTION_SPLITTING.md) - Умное разбиение
- [CONTEXT_AWARE_CHUNKING.md](./docs/CONTEXT_AWARE_CHUNKING.md) - RAG с overlap
- [SELF_LEARNING_TRANSLATION.md](./docs/SELF_LEARNING_TRANSLATION.md) - Самообучение

---

**Готово! Вы запустили KPS за 5 минут!** 🎉

**Следующий шаг:** Изучите [UNIFIED_PIPELINE.md](./docs/UNIFIED_PIPELINE.md) для углублённого понимания системы.
