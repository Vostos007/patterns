"""
Пример использования Knowledge Base - системы накопления знаний.

Показывает:
1. Загрузка знаний из папок
2. Автоматическая категоризация
3. Поиск релевантной информации
4. Использование для перевода (RAG)
5. Генерация описаний изделий
"""

from pathlib import Path

from kps.knowledge import (
    KnowledgeBase,
    KnowledgeCategory,
    PatternGenerator,
    ProjectRequirements,
)


def setup_knowledge_base():
    """Создание и настройка базы знаний."""
    print("=" * 70)
    print("ПРИМЕР 1: Создание и загрузка базы знаний")
    print("=" * 70)

    # Создать базу знаний
    kb = KnowledgeBase("data/knowledge.db")

    print(f"\n✓ База знаний создана: data/knowledge.db")

    # Загрузить знания из разных папок
    # (Папки должны существовать с файлами)
    knowledge_folders = [
        ("knowledge/patterns", KnowledgeCategory.PATTERN),
        ("knowledge/techniques", KnowledgeCategory.TECHNIQUE),
        ("knowledge/yarns", KnowledgeCategory.YARN),
        ("knowledge/tools", KnowledgeCategory.TOOL),
        ("knowledge/projects", KnowledgeCategory.PROJECT),
    ]

    total_loaded = 0

    for folder, category in knowledge_folders:
        folder_path = Path(folder)

        if folder_path.exists():
            print(f"\nЗагрузка из {folder}...")
            count = kb.ingest_folder(str(folder_path), category=category, recursive=True)
            total_loaded += count
            print(f"  ✓ Загружено {count} документов ({category.value})")
        else:
            print(f"\n⚠ Папка не найдена: {folder} (пропускаем)")

    print(f"\n{'=' * 70}")
    print(f"ИТОГО: Загружено {total_loaded} документов в базу знаний")
    print(f"{'=' * 70}")

    return kb


def search_examples(kb: KnowledgeBase):
    """Примеры поиска в базе знаний."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 2: Поиск в базе знаний")
    print("=" * 70)

    # Поиск техник
    print("\n1. Поиск техник вязания кос:")
    results = kb.search(
        "как вязать косы", category=KnowledgeCategory.TECHNIQUE, limit=3
    )

    if results:
        for i, entry in enumerate(results, 1):
            print(f"\n  [{i}] {entry.title}")
            print(f"      Категория: {entry.category}")
            print(f"      Язык: {entry.language}")
            print(f"      Источник: {entry.source_file}")
            # Показать первые 100 символов
            preview = entry.content[:100].replace("\n", " ")
            print(f"      Превью: {preview}...")
    else:
        print("  ⚠ Ничего не найдено (база знаний пуста)")

    # Поиск пряжи
    print("\n2. Поиск информации о мохере:")
    results = kb.search("мохер", category=KnowledgeCategory.YARN, limit=2)

    if results:
        for i, entry in enumerate(results, 1):
            print(f"\n  [{i}] {entry.title}")
            preview = entry.content[:100].replace("\n", " ")
            print(f"      {preview}...")
    else:
        print("  ⚠ Ничего не найдено")

    # Общий поиск без категории
    print("\n3. Общий поиск по всем категориям:")
    results = kb.search("шарф", limit=5)

    if results:
        for i, entry in enumerate(results, 1):
            print(f"  [{i}] {entry.title} ({entry.category})")
    else:
        print("  ⚠ Ничего не найдено")


def translation_context_example(kb: KnowledgeBase):
    """Пример использования знаний для перевода."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 3: Использование знаний для перевода (RAG)")
    print("=" * 70)

    # Пример фразы для перевода
    text = "Провяжите 2 петли вместе лицевой"

    print(f"\nИсходный текст: '{text}'")
    print(f"Перевод: ru → en")

    # Получить контекст из базы знаний
    context = kb.get_translation_context(text, source_lang="ru", target_lang="en")

    if context:
        print(f"\nКонтекст из базы знаний:")
        print("-" * 70)
        print(context)
        print("-" * 70)
        print("\n✓ Этот контекст будет добавлен к промпту ИИ для более точного перевода")
    else:
        print("\n⚠ Контекст не найден (база знаний пуста)")


def pattern_generation_example(kb: KnowledgeBase):
    """Пример генерации описания изделия."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 4: Генерация описания изделия")
    print("=" * 70)

    # Создать генератор
    generator = PatternGenerator(kb)

    # Требования к изделию
    requirements = ProjectRequirements(
        project_type="шарф",
        yarn_type="мохер",
        technique="ажурное вязание",
        skill_level="intermediate",
        language="ru",
    )

    print(f"\nТребования:")
    print(f"  Изделие: {requirements.project_type}")
    print(f"  Пряжа: {requirements.yarn_type}")
    print(f"  Техника: {requirements.technique}")
    print(f"  Уровень: {requirements.skill_level}")

    print(f"\nГенерация описания...")

    try:
        # Сгенерировать описание
        description = generator.generate(requirements)

        print(f"\n{'=' * 70}")
        print(f"РЕЗУЛЬТАТ:")
        print(f"{'=' * 70}")

        print(f"\n📝 НАЗВАНИЕ: {description.title}")
        print(f"\n📄 ОПИСАНИЕ:\n{description.description}")

        print(f"\n🧶 МАТЕРИАЛЫ:")
        for key, value in description.materials.items():
            print(f"  - {key}: {value}")

        print(f"\n🔧 ТЕХНИКИ ({len(description.techniques)}):")
        for tech in description.techniques:
            print(f"  - {tech}")

        print(f"\n🎨 УЗОРЫ ({len(description.patterns)}):")
        for pattern in description.patterns:
            print(f"  - {pattern}")

        print(f"\n⏱ ВРЕМЯ: {description.estimated_time}")
        print(f"📊 УРОВЕНЬ: {description.skill_level}")

        if description.sources:
            print(f"\n📚 ИСТОЧНИКИ:")
            for source in description.sources:
                print(f"  - {source}")

        print(f"\n{'=' * 70}")
        print(f"ИНСТРУКЦИИ:")
        print(f"{'=' * 70}")
        print(description.instructions)

    except Exception as e:
        print(f"\n⚠ Ошибка генерации: {e}")
        print("  (Скорее всего база знаний пуста)")


def statistics_example(kb: KnowledgeBase):
    """Пример получения статистики базы знаний."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 5: Статистика базы знаний")
    print("=" * 70)

    stats = kb.get_statistics()

    print(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
    print(f"  Всего записей: {stats['total_entries']}")
    print(f"  Размер БД: {stats['database_size']}")

    if stats['total_entries'] > 0:
        print(f"\n📁 ПО КАТЕГОРИЯМ:")
        for category, count in stats["by_category"].items():
            print(f"  {category:12} : {count:4} записей")

        print(f"\n🌍 ПО ЯЗЫКАМ:")
        for lang, count in stats["by_language"].items():
            print(f"  {lang:12} : {count:4} записей")

        print(f"\n🔝 ПОПУЛЯРНЫЕ КЛЮЧЕВЫЕ СЛОВА:")
        for keyword, count in stats.get("top_keywords", [])[:10]:
            print(f"  {keyword:20} : {count:3} раз")
    else:
        print("\n⚠ База знаний пуста")


def integration_example():
    """Пример интеграции с системой перевода."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 6: Интеграция с системой перевода")
    print("=" * 70)

    print("""
Интеграция знаний в процесс перевода:

1. ЗАГРУЗКА ЗНАНИЙ:
   kb = KnowledgeBase("data/knowledge.db")
   kb.ingest_folder("knowledge/", recursive=True)

2. СОЗДАНИЕ ПЕРЕВОДЧИКА:
   translator = GlossaryTranslator(orchestrator, glossary)

3. ПЕРЕВОД С ИСПОЛЬЗОВАНИЕМ ЗНАНИЙ:
   # Получить контекст из базы знаний
   context = kb.get_translation_context(text, "ru", "en")

   # Добавить к глоссарию
   glossary_context = glossary.build_context(...) + context

   # Перевести с учётом знаний
   result = orchestrator.translate_batch(segments, glossary_context)

4. РЕЗУЛЬТАТ:
   ✓ Более точный перевод терминов
   ✓ Учёт контекста вязания
   ✓ Консистентность с предыдущими переводами

Это автоматически используется в UnifiedPipeline!
    """)


def main():
    """Запустить все примеры."""
    print("\n" + "🧶" * 35)
    print("KNOWLEDGE BASE - База знаний о вязании")
    print("🧶" * 35)

    try:
        # 1. Создать и загрузить
        kb = setup_knowledge_base()

        # 2. Примеры поиска
        search_examples(kb)

        # 3. Контекст для перевода
        translation_context_example(kb)

        # 4. Генерация описания
        pattern_generation_example(kb)

        # 5. Статистика
        statistics_example(kb)

        # 6. Интеграция
        integration_example()

        print("\n\n" + "=" * 70)
        print("✅ ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ")
        print("=" * 70)

        print("\nKEY FEATURES:")
        print("  ✓ Автоматическая загрузка документов из папок")
        print("  ✓ Категоризация по типам (узоры, техники, пряжа...)")
        print("  ✓ Семантический поиск с embeddings")
        print("  ✓ RAG для улучшения переводов")
        print("  ✓ Генерация описаний изделий на основе знаний")
        print("  ✓ Самообучение и накопление опыта")

        print("\nQUICK START:")
        print("  kb = KnowledgeBase('data/knowledge.db')")
        print("  kb.ingest_folder('knowledge/', recursive=True)")
        print("  results = kb.search('узор', category=PATTERN)")

        print("\n💡 База знаний растёт с каждым документом!")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("\nВозможные причины:")
        print("  - Не создана папка knowledge/ с файлами")
        print("  - Не установлены зависимости")
        print("  - Проблемы с путями к файлам")

        print("\nСоздайте структуру папок:")
        print("  knowledge/")
        print("    ├── patterns/     # Узоры и схемы")
        print("    ├── techniques/   # Техники вязания")
        print("    ├── yarns/        # Виды пряжи")
        print("    ├── tools/        # Инструменты")
        print("    └── projects/     # Готовые изделия")


if __name__ == "__main__":
    main()
