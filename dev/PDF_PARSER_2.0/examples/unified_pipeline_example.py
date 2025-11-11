"""
Пример использования Unified Pipeline - единой системы обработки документов.

Показывает:
1. Простейшее использование (одна строка)
2. С настройками
3. Мониторинг прогресса
4. Статистика и метрики
"""

from pathlib import Path

from kps.core.unified_pipeline import (
    ExtractionMethod,
    MemoryType,
    PipelineConfig,
    UnifiedPipeline,
)


def simple_example():
    """Простейший пример - всё автоматически."""
    print("=" * 70)
    print("ПРИМЕР 1: Простейшее использование")
    print("=" * 70)

    # Создать pipeline с настройками по умолчанию
    pipeline = UnifiedPipeline()

    # Обработать документ
    result = pipeline.process(
        input_file="input/document.pdf", target_languages=["en", "fr"]
    )

    # Результат
    print(f"\n✓ Обработано: {result.source_file}")
    print(f"  Язык источника: {result.source_language}")
    print(f"  Страниц: {result.pages_extracted}")
    print(f"  Сегментов: {result.segments_extracted}")
    print(f"  Переведено на: {', '.join(result.target_languages)}")
    print(f"  Использовано из кэша: {result.cache_hit_rate:.0%}")
    print(f"  Стоимость: ${result.translation_cost:.4f}")
    print(f"  Время: {result.processing_time:.1f}s")

    print(f"\nВыходные файлы:")
    for lang, files in result.output_files.items():
        for fmt, filepath in files.items():
            print(f"  {lang} [{fmt}]: {filepath}")


def configured_example():
    """Пример с настройками."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 2: С настройками")
    print("=" * 70)

    # Настроить pipeline
    config = PipelineConfig(
        # Извлечение
        extraction_method=ExtractionMethod.DOCLING,  # AI-powered
        use_ocr=False,
        # Перевод
        memory_type=MemoryType.SEMANTIC,  # Embeddings + RAG
        memory_path="data/semantic_memory.db",
        glossary_path="glossary.yaml",
        enable_few_shot=True,  # Few-shot learning
        enable_auto_suggestions=True,  # Автопредложения терминов
        # QA
        enable_qa=False,  # Пока отключено
        # Экспорт
        export_formats=["json"],
        style_template="templates/indesign/master-template-styles.yaml",
    )

    # Создать pipeline
    pipeline = UnifiedPipeline(config)

    # Обработать
    result = pipeline.process("input/document.pdf", target_languages=["en"])

    print(f"\n✓ Обработка завершена")
    print(f"  Метод извлечения: {result.extraction_method}")
    print(f"  Cache hit: {result.cache_hit_rate:.0%}")
    print(f"  Найдено терминов глоссария: {result.glossary_terms_found}")

    if result.errors:
        print(f"\n⚠ Ошибки:")
        for error in result.errors:
            print(f"  - {error}")

    if result.warnings:
        print(f"\n⚠ Предупреждения:")
        for warning in result.warnings:
            print(f"  - {warning}")


def batch_processing():
    """Пример пакетной обработки."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 3: Пакетная обработка")
    print("=" * 70)

    # Pipeline для пакетной обработки
    config = PipelineConfig(
        extraction_method=ExtractionMethod.PYMUPDF,  # Быстрее
        memory_type=MemoryType.SEMANTIC,
        enable_few_shot=True,
    )

    pipeline = UnifiedPipeline(config)

    # Список файлов
    input_files = [
        "input/document1.pdf",
        "input/document2.pdf",
        "input/document3.pdf",
    ]

    target_langs = ["en", "fr"]

    results = []
    total_cost = 0.0
    total_time = 0.0

    print(f"\nОбработка {len(input_files)} файлов...")
    print("-" * 70)

    for i, input_file in enumerate(input_files, 1):
        print(f"\n[{i}/{len(input_files)}] {Path(input_file).name}")

        try:
            result = pipeline.process(input_file, target_langs)

            results.append(result)
            total_cost += result.translation_cost
            total_time += result.processing_time

            print(f"  ✓ Cache: {result.cache_hit_rate:.0%}, Cost: ${result.translation_cost:.4f}")

        except FileNotFoundError:
            print(f"  ✗ Файл не найден (пропускаем)")
            continue
        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
            continue

    # Итоговая статистика
    print("\n" + "=" * 70)
    print("ИТОГИ ПАКЕТНОЙ ОБРАБОТКИ")
    print("=" * 70)

    if results:
        avg_cache = sum(r.cache_hit_rate for r in results) / len(results)
        total_segments = sum(r.segments_extracted for r in results)

        print(f"Обработано файлов: {len(results)}/{len(input_files)}")
        print(f"Всего сегментов: {total_segments}")
        print(f"Средний cache hit: {avg_cache:.0%}")
        print(f"Общая стоимость: ${total_cost:.4f}")
        print(f"Общее время: {total_time:.1f}s")
        print(f"Средняя скорость: {total_segments/total_time:.1f} сегментов/сек")
    else:
        print("Не удалось обработать ни один файл")


def statistics_example():
    """Пример работы со статистикой."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 4: Статистика и метрики")
    print("=" * 70)

    pipeline = UnifiedPipeline()

    # Получить статистику системы
    stats = pipeline.get_statistics()

    print("\nСтатистика системы:")
    print("-" * 70)
    print(f"Терминов в глоссарии: {stats.get('glossary_terms', 0)}")
    print(f"Память переводов: {'✓ Включена' if stats.get('memory_enabled') else '✗ Отключена'}")

    if stats.get('memory_enabled'):
        print(f"Тип памяти: {stats.get('memory_type')}")
        print(f"Записей в памяти: {stats.get('total_entries', 0)}")
        print(f"Всего использований: {stats.get('total_usage', 0)}")
        print(f"Средняя оценка качества: {stats.get('average_quality', 0):.1%}")

        if 'language_pairs' in stats:
            print(f"\nЯзыковые пары:")
            for pair, count in stats['language_pairs'].items():
                print(f"  {pair}: {count} переводов")


def progressive_learning_demo():
    """Демонстрация прогрессивного обучения."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 5: Прогрессивное обучение")
    print("=" * 70)

    # Pipeline с semantic memory
    config = PipelineConfig(
        memory_type=MemoryType.SEMANTIC,
        enable_few_shot=True,
        enable_auto_suggestions=True,
    )

    pipeline = UnifiedPipeline(config)

    print("\nСимуляция работы в течение месяца...")
    print("-" * 70)

    # Симуляция: один и тот же документ несколько раз
    simulated_results = [
        {"week": 1, "cache_hit": 0.10, "cost": 10.0, "quality": 0.91},
        {"week": 2, "cache_hit": 0.30, "cost": 7.0, "quality": 0.93},
        {"week": 3, "cache_hit": 0.60, "cost": 4.0, "quality": 0.95},
        {"week": 4, "cache_hit": 0.75, "cost": 2.5, "quality": 0.97},
    ]

    for data in simulated_results:
        print(f"\nНеделя {data['week']}:")
        print(f"  Cache hit: {data['cache_hit']:.0%}")
        print(f"  Стоимость: ${data['cost']:.2f}")
        print(f"  Качество: {data['quality']:.1%}")

    print("\n" + "=" * 70)
    print("ПРОГРЕСС:")
    print("-" * 70)
    print("  Cache hit: 10% → 75% (+65%)")
    print("  Стоимость: $10 → $2.5 (-75%)")
    print("  Качество: 91% → 97% (+6%)")
    print("\n✓ Система обучилась и стала эффективнее!")


def main():
    """Запустить все примеры."""

    print("\n" + "🚀" * 35)
    print("UNIFIED PIPELINE - Единая система обработки документов")
    print("🚀" * 35)

    try:
        # Примеры
        simple_example()
        configured_example()
        batch_processing()
        statistics_example()
        progressive_learning_demo()

        print("\n\n" + "=" * 70)
        print("✅ ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ")
        print("=" * 70)

        print("\nKEY FEATURES:")
        print("  ✓ Единая точка входа - один pipeline для всего")
        print("  ✓ Автоматический выбор метода извлечения")
        print("  ✓ Semantic memory с embeddings и RAG")
        print("  ✓ Прогрессивное самообучение")
        print("  ✓ Пакетная обработка документов")
        print("  ✓ Подробная статистика и метрики")

        print("\nUSAGE:")
        print("  pipeline = UnifiedPipeline()")
        print('  result = pipeline.process("document.pdf", ["en", "fr"])')
        print("\n💡 Просто и эффективно!")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("\nВозможные причины:")
        print("  - Не найдены входные файлы (создайте папку input/)")
        print("  - Не установлены зависимости")
        print("  - Проблемы с API ключами")


if __name__ == "__main__":
    main()
