"""
Пример разбиения сложных документов на секции.

Демонстрирует:
1. Как один документ (книга, инструкция) разбивается на секции
2. Каждая секция категоризируется отдельно
3. Поиск по конкретным секциям
"""

from kps.knowledge import (
    KnowledgeBase,
    KnowledgeCategory,
    DocumentSplitter,
    SplitStrategy,
)


# Пример сложного документа (книга с разными разделами)
SAMPLE_BOOK = """
# Полное руководство по вязанию

## Глава 1: Инструменты

Для вязания вам понадобятся следующие инструменты:

### Спицы
Спицы бывают разные - прямые, круговые, чулочные. Размер спиц обозначается в миллиметрах
и зависит от толщины пряжи. Для начинающих рекомендуются спицы 3-4 мм.

### Крючки
Крючок используется для вязания крючком и для поднятия петель. Размеры крючков
также обозначаются в миллиметрах.

## Глава 2: Пряжа

Правильный выбор пряжи - залог успеха вашего изделия.

### Мохер
Мохер - легкая воздушная пряжа из шерсти ангорских коз. Отлично подходит для шарфов,
палантинов и ажурных изделий. Обычно вяжется спицами 4-6 мм.

### Шерсть мериноса
Мериносовая шерсть - мягкая, теплая, гипоаллергенная. Идеальна для детских вещей
и зимней одежды. Хорошо держит форму.

## Глава 3: Основные техники

Научимся основным техникам вязания.

### Набор петель
Набор петель - это начало любого вязания. Существует несколько способов:
традиционный набор, итальянский набор, набор с дополнительной нитью.

### Лицевые и изнаночные петли
Лицевая петля (knit) и изнаночная петля (purl) - основа платочного и чулочного
вязания. Все узоры строятся на комбинации этих двух петель.

### Прибавления и убавления
Для формирования изделия нужно уметь прибавлять и убавлять петли.
Прибавления: накид, вывязывание из одной петли двух.
Убавления: 2 вместе лицевой (k2tog), 2 вместе изнаночной.

## Глава 4: Узоры

Популярные узоры для вязания.

### Косы (Cable pattern)
Косы - классический узор, который создаётся путём перекрещивания петель.
Для вязания кос используется дополнительная спица или булавка.

Коса 2×2:
- Переснять 2 петли на дополнительную спицу
- Провязать следующие 2 петли
- Провязать петли с дополнительной спицы
- Повторять каждые 4-6 рядов

### Ажурный узор "Листья"
Ажурный узор создаётся при помощи накидов и убавлений.
Красиво смотрится на шарфах и палантинах из мохера.

## Глава 5: Готовые проекты

### Простой шарф
Материалы:
- Пряжа: 200г мохера
- Спицы: 5 мм
- Время: 10-15 часов
- Уровень: начинающий

Описание:
Набрать 40 петель. Вязать платочной вязкой (все петли лицевые) до длины 150 см.
Закрыть петли. По желанию добавить кисточки на концах.

### Шапка с косами
Материалы:
- Пряжа: 100г шерсти мериноса
- Круговые спицы: 4 мм
- Дополнительная спица для кос
- Время: 8-12 часов
- Уровень: средний

Описание:
Набрать 96 петель на круговые спицы. Вязать резинку 2×2 на 5 см.
Затем перейти на узор с косами. Через 20 см начать убавления для макушки.
"""


def example_1_split_strategies():
    """Пример 1: Разные стратегии разбиения."""
    print("=" * 70)
    print("ПРИМЕР 1: Стратегии разбиения документа")
    print("=" * 70)

    splitter = DocumentSplitter()

    # Автоматическое определение стратегии
    print("\n1. AUTO - автоматическое определение:")
    sections = splitter.split(SAMPLE_BOOK, strategy=SplitStrategy.AUTO)
    print(f"   Найдено секций: {len(sections)}")
    for i, section in enumerate(sections[:5], 1):
        print(f"   [{i}] Level {section.level}: {section.title}")

    # Markdown заголовки
    print("\n2. MARKDOWN - по заголовкам (# ## ###):")
    sections = splitter.split(SAMPLE_BOOK, strategy=SplitStrategy.MARKDOWN)
    print(f"   Найдено секций: {len(sections)}")
    for i, section in enumerate(sections[:5], 1):
        print(f"   [{i}] Level {section.level}: {section.title}")


def example_2_categorization():
    """Пример 2: Автоматическая категоризация секций."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 2: Категоризация каждой секции")
    print("=" * 70)

    from kps.knowledge.splitter import categorize_section

    splitter = DocumentSplitter()
    sections = splitter.split(SAMPLE_BOOK, strategy=SplitStrategy.MARKDOWN)

    print(f"\nДокумент разбит на {len(sections)} секций:\n")

    # Категоризировать каждую секцию
    for section in sections:
        category = categorize_section(section)
        preview = section.content[:60].replace("\n", " ")
        print(f"[{category.value:10}] {section.title}")
        print(f"              {preview}...")
        print()

    # Статистика по категориям
    from collections import Counter

    categories = [categorize_section(s) for s in sections]
    stats = Counter(categories)

    print("\nСтатистика по категориям:")
    for cat, count in stats.most_common():
        print(f"  {cat.value:12} : {count} секций")


def example_3_knowledge_base_integration():
    """Пример 3: Загрузка в базу знаний."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 3: Загрузка сложного документа в базу знаний")
    print("=" * 70)

    import tempfile
    from pathlib import Path

    # Создать временный файл
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".md", delete=False
    ) as f:
        f.write(SAMPLE_BOOK)
        temp_file = Path(f.name)

    # Создать базу знаний с разбиением на секции
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_kb.db"

        print("\n1. С разбиением на секции (split_sections=True):")
        kb_split = KnowledgeBase(
            str(db_path), use_embeddings=False, split_sections=True
        )

        # Создать папку и скопировать файл
        knowledge_dir = Path(tmpdir) / "knowledge"
        knowledge_dir.mkdir()
        import shutil

        dest_file = knowledge_dir / "complete_guide.md"
        shutil.copy(temp_file, dest_file)

        # Загрузить
        count = kb_split.ingest_folder(str(knowledge_dir))
        print(f"   Загружено секций: {count}")

        # Статистика
        stats = kb_split.get_statistics()
        print(f"\n   Распределение по категориям:")
        for category, cnt in stats["by_category"].items():
            print(f"     {category:12} : {cnt} секций")

        print(f"\n2. Без разбиения на секции (split_sections=False):")
        db_path2 = Path(tmpdir) / "test_kb2.db"
        kb_nosplit = KnowledgeBase(
            str(db_path2), use_embeddings=False, split_sections=False
        )

        count2 = kb_nosplit.ingest_folder(str(knowledge_dir))
        print(f"   Загружено документов: {count2}")
        print(f"   (весь документ как одна запись)")

        # Удалить временный файл
        temp_file.unlink()


def example_4_search_specific_sections():
    """Пример 4: Поиск в конкретных секциях."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 4: Поиск по секциям")
    print("=" * 70)

    import tempfile
    from pathlib import Path

    # Создать временный файл и базу
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".md", delete=False
    ) as f:
        f.write(SAMPLE_BOOK)
        temp_file = Path(f.name)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "search_kb.db"
        kb = KnowledgeBase(str(db_path), use_embeddings=False, split_sections=True)

        # Загрузить книгу
        knowledge_dir = Path(tmpdir) / "knowledge"
        knowledge_dir.mkdir()
        import shutil

        dest_file = knowledge_dir / "guide.md"
        shutil.copy(temp_file, dest_file)

        kb.ingest_folder(str(knowledge_dir))

        # Поиск в разных категориях
        print("\n1. Поиск инструментов:")
        results = kb.search("спицы", category=KnowledgeCategory.TOOL, limit=3)
        for entry in results:
            print(f"   - {entry.title}")
            print(f"     {entry.content[:100]}...")

        print("\n2. Поиск пряжи:")
        results = kb.search("мохер", category=KnowledgeCategory.YARN, limit=3)
        for entry in results:
            print(f"   - {entry.title}")
            print(f"     {entry.content[:100]}...")

        print("\n3. Поиск техник:")
        results = kb.search("петли", category=KnowledgeCategory.TECHNIQUE, limit=3)
        for entry in results:
            print(f"   - {entry.title}")
            print(f"     {entry.content[:100]}...")

        print("\n4. Поиск готовых проектов:")
        results = kb.search("шарф", category=KnowledgeCategory.PROJECT, limit=3)
        for entry in results:
            print(f"   - {entry.title}")
            print(f"     Материалы: {entry.content[:80]}...")

        temp_file.unlink()


def example_5_metadata():
    """Пример 5: Метаданные секций."""
    print("\n\n" + "=" * 70)
    print("ПРИМЕР 5: Метаданные секций")
    print("=" * 70)

    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".md", delete=False
    ) as f:
        f.write(SAMPLE_BOOK)
        temp_file = Path(f.name)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "meta_kb.db"
        kb = KnowledgeBase(str(db_path), use_embeddings=False, split_sections=True)

        knowledge_dir = Path(tmpdir) / "knowledge"
        knowledge_dir.mkdir()
        import shutil

        dest_file = knowledge_dir / "guide.md"
        shutil.copy(temp_file, dest_file)

        kb.ingest_folder(str(knowledge_dir))

        # Получить первую секцию
        results = kb.search("спицы", limit=1)
        if results:
            entry = results[0]
            print(f"\nЗапись: {entry.title}")
            print(f"Категория: {entry.category.value}")
            print(f"Источник: {entry.source_file}")
            print(f"\nМетаданные секции:")
            for key, value in entry.metadata.items():
                print(f"  {key:20} : {value}")

        temp_file.unlink()


def main():
    """Запустить все примеры."""
    print("\n" + "📚" * 35)
    print("SECTION SPLITTING - Разбиение документов на секции")
    print("📚" * 35)

    try:
        example_1_split_strategies()
        example_2_categorization()
        example_3_knowledge_base_integration()
        example_4_search_specific_sections()
        example_5_metadata()

        print("\n\n" + "=" * 70)
        print("✅ ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ")
        print("=" * 70)

        print("\n📖 КЛЮЧЕВАЯ ФИЧА:")
        print("  Один документ (книга) → много секций → разные категории!")
        print()
        print("  Документ: 'Полное руководство по вязанию.md'")
        print("  ↓")
        print("  Секция 1: 'Спицы' → TOOL")
        print("  Секция 2: 'Крючки' → TOOL")
        print("  Секция 3: 'Мохер' → YARN")
        print("  Секция 4: 'Мериносовая шерсть' → YARN")
        print("  Секция 5: 'Набор петель' → TECHNIQUE")
        print("  Секция 6: 'Лицевые петли' → STITCH")
        print("  Секция 7: 'Косы' → PATTERN")
        print("  Секция 8: 'Простой шарф' → PROJECT")
        print("  ...")
        print()
        print("  → Каждая секция индексируется и ищется отдельно!")
        print("  → Поиск по категориям работает точно!")
        print("  → RAG использует релевантные секции, не весь документ!")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
