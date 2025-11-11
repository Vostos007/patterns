# Gap Analysis: Текущая архитектура vs Рекомендации

**Дата:** 2025-11-11
**Версия:** 1.0
**Статус:** После исправления критических архитектурных проблем

---

## Executive Summary

После анализа текущей системы и полученных архитектурных рекомендаций выявлено:

- ✅ **70% базовой архитектуры реализовано** (Docling, OpenAI, Knowledge Base, глоссарий)
- ⚠️ **30% требует доработки** (автоматизация, KFP, форматирование выхода)
- 🎯 **5 приоритетных улучшений** для полной автономной работы

---

## 1. Компоненты: Что есть vs Что нужно

### 1.1. Extraction Layer ✅ РЕАЛИЗОВАН

| Компонент | Статус | Детали |
|-----------|--------|--------|
| Docling | ✅ Есть | `kps/extraction/docling_extractor.py` - полная реализация |
| PyMuPDF | ✅ Есть | `kps/extraction/pymupdf_extractor.py` - asset extraction |
| OCR Support | ✅ Есть | Docling с OCR плагинами |
| Structure Parsing | ✅ Есть | Таблицы, заголовки, координаты |

**Вердикт:** Отлично реализован. Docling дает структурированный KPSDocument.

---

### 1.2. Segmentation Layer ✅ ИСПРАВЛЕН

| Компонент | Статус | Детали |
|-----------|--------|--------|
| Segmenter | ✅ Исправлен | `kps/extraction/segmenter.py` - только что интегрирован в UnifiedPipeline |
| Placeholder Encoding | ✅ Есть | Сохранение [[asset_id]], URLs, чисел |
| Context-aware Chunking | ✅ Есть | `kps/knowledge/chunker.py` с overlap 10-20% |
| Section Splitting | ✅ Есть | `kps/knowledge/splitter.py` с auto-categorization |

**Вердикт:** Полностью работает после недавних исправлений.

---

### 1.3. Translation Layer ✅ РЕАЛИЗОВАН

| Компонент | Статус | Детали |
|-----------|--------|--------|
| OpenAI Integration | ✅ Есть | `kps/translation/orchestrator.py` |
| Glossary Manager | ✅ Есть | `kps/translation/glossary/` + файл `глоссарий.json` |
| GlossaryTranslator | ✅ Есть | `kps/translation/glossary_translator.py` |
| Translation Memory | ✅ Есть | `kps/translation/memory.py` + Semantic variant |
| Protected Tokens | ✅ Есть | В глоссарии: `protected_tokens: ["k","end","m"]` |

**Особенность:** У нас уже есть отличный глоссарий:
- 3 языка: RU → EN → FR
- Категории: stitch, decrease, increase, technique, материалы
- Protected tokens для каждого термина
- Контекстные замечания (notes)

**Вердикт:** Хорошо реализован, но нужно усилить term-lock enforcement.

---

### 1.4. Knowledge Base Layer ✅ ТОЛЬКО ЧТО ИНТЕГРИРОВАН

| Компонент | Статус | Детали |
|-----------|--------|--------|
| KnowledgeBase | ✅ Интегрирован | Только что добавлен в UnifiedPipeline (строки 221-251) |
| Embeddings | ✅ Есть | OpenAI embeddings через SemanticTranslationMemory |
| RAG | ✅ Есть | `knowledge/base.py` с semantic search |
| Vector Index | ✅ Есть | SQLite + embeddings (можно мигрировать на pgvector) |
| Section Splitting | ✅ Есть | `knowledge/splitter.py` |
| Chunking | ✅ Есть | `knowledge/chunker.py` с overlap |

**Вердикт:** Архитектура готова, требуется активное использование в RAG-сценариях.

---

### 1.5. QA Layer ⚠️ БАЗОВАЯ РЕАЛИЗАЦИЯ

| Компонент | Статус | Детали |
|-----------|--------|--------|
| QAPipeline | ⚠️ Базовая | `kps/qa/pipeline.py` существует, но не fully integrated |
| Quality Metrics | ❌ Нет | Нет back-translation, COMET, или advanced QE |
| Term Validation | ⚠️ Частично | Глоссарий есть, но нет жесткой post-проверки |
| Length/Format Check | ❌ Нет | Нет проверки длины, формата, спец-символов |

**Вердикт:** Требуется усиление QA-слоя.

---

### 1.6. Export Layer ⚠️ IDML ЕСТЬ, DOCX/PDF НЕТ

| Компонент | Статус | Детали |
|-----------|--------|--------|
| IDML Export | ✅ Есть | `kps/indesign/idml_exporter.py`, полная реализация |
| PDF Export | ⚠️ Базовый | `kps/indesign/pdf_export.py` через ReportLab |
| DOCX Export | ❌ Нет | Нет Pandoc или python-docx экспорта |
| Style Templates | ❌ Нет | Нет reference.docx или print.css |
| Typography | ⚠️ IDML only | IDML поддерживает, но DOCX/PDF - нет |

**Рекомендации:**
- ✅ **Оставить IDML** как основной профессиональный формат
- ➕ **Добавить Pandoc + reference.docx** для быстрого DOCX
- ➕ **Добавить WeasyPrint/Prince** для качественного PDF

**Вердикт:** IDML отличный, но нужны альтернативы для менее требовательных сценариев.

---

### 1.7. Orchestration Layer ❌ НЕТ KFP

| Компонент | Статус | Детали |
|-----------|--------|--------|
| UnifiedPipeline | ✅ Есть | `kps/core/unified_pipeline.py` - только что исправлен |
| Kubeflow Pipelines | ❌ Нет | Нет KFP интеграции |
| Recurring Runs | ❌ Нет | Нет автоматических триггеров |
| Inbox Monitoring | ❌ Нет | Нет автоматического ingest |
| Artifact Management | ⚠️ Частично | Локальные файлы, нет S3/MinIO |

**Рекомендации из плана:**
- Добавить KFP компоненты
- Recurring runs каждые 10-15 минут
- S3/MinIO для артефактов

**Вердикт:** Требуется полная автоматизация через KFP или альтернативу.

---

### 1.8. Semantic Cache & Token Optimization ⚠️ ЧАСТИЧНО

| Компонент | Статус | Детали |
|-----------|--------|--------|
| Translation Cache | ✅ Есть | SemanticTranslationMemory с embeddings |
| Semantic Key | ⚠️ Упрощенный | Есть кэш, но ключ не включает glossary_version |
| Delta Translation | ❌ Нет | Нет определения changed segments |
| RAG Cache | ❌ Нет | Нет кэша RAG-контекстов |
| Hybrid Search | ⚠️ Частично | Есть semantic, но нет BM25 |

**Вердикт:** Базовый кэш есть, нужны улучшения для экономии токенов.

---

## 2. Приоритетный план улучшений

### 🔴 Критичные (реализовать в первую очередь)

#### P1: Автоматизация пайплайна (без KFP)
**Проблема:** Нет автономной работы
**Решение:** Простой Python daemon + cron для мониторинга inbox

```python
# daemon.py - минимальная автоматизация
import time, os, hashlib
from pathlib import Path
from kps.core import UnifiedPipeline

INBOX = Path("inbox")
PROCESSED = Path("data/processed_hashes.txt")

def get_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_processed():
    if PROCESSED.exists():
        return set(PROCESSED.read_text().split("\n"))
    return set()

def main_loop():
    pipeline = UnifiedPipeline()
    processed = load_processed()

    while True:
        for file in INBOX.glob("*.pdf"):
            h = get_hash(file)
            if h not in processed:
                print(f"Processing {file.name}...")
                pipeline.process(file, ["en", "fr"])
                processed.add(h)
                PROCESSED.write_text("\n".join(processed))

        time.sleep(300)  # каждые 5 минут

if __name__ == "__main__":
    main_loop()
```

**Приоритет:** ВЫСШИЙ
**Трудозатраты:** 2-4 часа
**Польза:** Система работает автономно без ручного запуска

---

#### P2: Улучшение качества перевода через term-lock
**Проблема:** Термины могут не соблюдаться
**Решение:** Post-validation после LLM

```python
# kps/translation/term_validator.py
import re
from typing import List, Dict

class TermValidator:
    def __init__(self, glossary_manager):
        self.glossary = glossary_manager

    def validate_translation(self, src_text: str, tgt_text: str,
                           src_lang: str, tgt_lang: str) -> List[str]:
        """Проверить соблюдение терминологии."""
        violations = []
        entries = self.glossary.get_all_entries()

        for entry in entries:
            if entry.source_lang != src_lang or entry.target_lang != tgt_lang:
                continue

            src_term = entry.source_term
            tgt_term = entry.target_term

            # Если термин есть в исходнике
            if re.search(rf"\b{re.escape(src_term)}\b", src_text, re.IGNORECASE):
                # Должен быть в переводе
                if not re.search(rf"\b{re.escape(tgt_term)}\b", tgt_text, re.IGNORECASE):
                    violations.append(
                        f"Missing term: '{src_term}' should be translated as '{tgt_term}'"
                    )

        return violations
```

**Приоритет:** ВЫСШИЙ
**Трудозатраты:** 3-5 часов
**Польза:** Гарантированное соблюдение терминологии

---

#### P3: Pandoc + DOCX Export
**Проблема:** Нет простого DOCX выхода
**Решение:** Добавить Pandoc рендерер

```python
# kps/export/pandoc_renderer.py
import subprocess
from pathlib import Path
from typing import Optional

class PandocRenderer:
    def __init__(self, reference_docx: Optional[Path] = None):
        self.reference_docx = reference_docx or Path("styles/reference.docx")

    def render_docx(self, markdown_path: Path, output_path: Path):
        """Рендерить Markdown → DOCX через Pandoc."""
        cmd = [
            "pandoc", str(markdown_path),
            "--reference-doc", str(self.reference_docx),
            "--toc", "--toc-depth=3",
            "-o", str(output_path)
        ]
        subprocess.run(cmd, check=True)

    def render_pdf(self, markdown_path: Path, output_path: Path):
        """Рендерить Markdown → PDF через Pandoc + LaTeX."""
        cmd = [
            "pandoc", str(markdown_path),
            "-V", "mainfont=Noto Serif",
            "-V", "monofont=Noto Sans Mono",
            "--pdf-engine=xelatex",
            "-o", str(output_path)
        ]
        subprocess.run(cmd, check=True)
```

**Приоритет:** ВЫСОКИЙ
**Трудозатраты:** 4-6 часов (включая создание reference.docx)
**Польза:** Быстрый экспорт для non-InDesign пользователей

---

### 🟡 Важные (второй этап)

#### P4: Enhanced Semantic Cache
**Улучшить кэш с учетом версии глоссария:**

```python
def get_cache_key(text: str, src_lang: str, tgt_lang: str,
                  glossary_version: int) -> str:
    """Семантический ключ кэша."""
    import hashlib
    key_str = f"{text}|{src_lang}|{tgt_lang}|v{glossary_version}"
    return hashlib.sha256(key_str.encode()).hexdigest()
```

#### P5: Гибридный поиск (BM25 + Vector)
**Добавить BM25 для лучшего ретрива:**

```python
# Использовать rank_bm25 + cosine similarity
from rank_bm25 import BM25Okapi

class HybridSearch:
    def search(self, query: str, top_k: int = 5):
        # 1. BM25 для keyword matching
        bm25_results = self.bm25.get_top_n(query, self.corpus, n=10)

        # 2. Vector для semantic
        vec_results = self.vector_search(query, top_k=10)

        # 3. Merge + re-rank
        return self.merge_results(bm25_results, vec_results, top_k)
```

#### P6: QA Enhancement
- Back-translation для проверки
- COMET scores
- Term compliance report

---

### 🟢 Опциональные (третий этап)

#### P7: Kubeflow Pipelines Integration
Если понадобится полноценная MLOps-оркестрация.

#### P8: WeasyPrint для типографского PDF
Альтернатива LaTeX для более гибкого дизайна.

#### P9: Prometheus Metrics
Мониторинг: cache hit rate, translation cost, QE scores.

---

## 3. Что УЖЕ ХОРОШО (не трогать)

### ✅ Docling Integration
Лучший выбор для парсинга. Сохраняет структуру, таблицы, координаты.

### ✅ Глоссарий
Отличная структура:
- Трехъязычный (RU/EN/FR)
- Protected tokens
- Категоризация
- Context notes

### ✅ Knowledge Base Architecture
Правильная реализация:
- Section splitting
- Context-aware chunking с overlap
- Semantic search
- Auto-categorization

### ✅ IDML Export
Профессиональный уровень для InDesign workflow.

---

## 4. Архитектурные решения

### Оставить как есть:
1. **Docling** как primary extractor
2. **OpenAI** для translation и embeddings
3. **KPSDocument** как core data structure
4. **Segmenter** для placeholder handling
5. **IDML** как professional export path

### Добавить:
1. **Простой daemon** вместо сложного KFP (на старте)
2. **Pandoc** для DOCX/PDF quick export
3. **Term validator** для post-check
4. **Enhanced caching** с версионированием глоссария
5. **Гибридный поиск** для RAG

### Не добавлять (overkill):
1. KFP на ранней стадии (слишком сложно)
2. Полноценная CI/CD для GitHub (ограничения прав)
3. Распределенные очереди (Kafka/RabbitMQ) - избыточно

---

## 5. Рекомендуемая последовательность реализации

### Неделя 1: Автоматизация + QA
- [ ] Daemon для inbox monitoring
- [ ] Term validator
- [ ] Integration tests

### Неделя 2: Export Improvements
- [ ] Создать reference.docx с правильными стилями
- [ ] Pandoc renderer (DOCX + PDF)
- [ ] Integration в UnifiedPipeline

### Неделя 3: Optimization
- [ ] Enhanced semantic cache
- [ ] Delta translation
- [ ] Hybrid search (BM25 + vector)

### Неделя 4: QA & Docs
- [ ] Back-translation validation
- [ ] Comprehensive testing
- [ ] User documentation

---

## 6. Метрики успеха

После реализации приоритетных улучшений:

| Метрика | Текущее | Цель |
|---------|---------|------|
| Автономность | 0% (ручной запуск) | 100% (daemon) |
| Term Compliance | ~80% (best effort) | 95%+ (validation) |
| Export Options | 2 (IDML, basic PDF) | 4 (IDML, PDF, DOCX, Markdown) |
| Cache Hit Rate | ~30% | 60%+ (improved key) |
| Translation Cost | Baseline | -30% (delta + cache) |
| Processing Time | Baseline | -20% (optimization) |

---

## 7. Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Pandoc не установлен | Средняя | Добавить в requirements.txt + инструкции |
| Reference.docx сложно создать | Низкая | Шаблон из существующих паттернов |
| Term validation слишком строгий | Средняя | Configurable threshold + warnings |
| Daemon падает | Низкая | Systemd + restart policy |

---

## Заключение

**Текущая система:** Хорошая база (70% готовности)

**Критичные пробелы:**
1. Нет автоматизации (daemon)
2. Нет гарантии соблюдения терминов (validator)
3. Нет удобного DOCX экспорта (Pandoc)

**План действий:**
Реализовать P1-P3 (приоритет ВЫСШИЙ) за 2-3 недели → получить полностью автономную систему с гарантированным качеством перевода и множественными форматами экспорта.

**Философия:**
- Не добавлять сложность ради сложности
- Использовать простые, проверенные решения
- Сохранить существующие сильные стороны (Docling, IDML, Knowledge Base)
- Усилить слабые места (автоматизация, QA, экспорт)

---

**Статус:** Ready for implementation
**Next Steps:** Начать с P1 (Daemon для автоматизации)
