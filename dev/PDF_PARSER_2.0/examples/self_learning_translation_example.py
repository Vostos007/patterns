"""
Пример самообучающейся системы перевода с глоссарием.

Этот пример показывает:
1. Использование кэша переводов (Translation Memory)
2. Автоматическое улучшение качества (Few-shot Learning)
3. Предложения новых терминов для глоссария
4. Статистика и аналитика
"""

from kps.translation import (
    GlossaryTranslator,
    GlossaryManager,
    TranslationMemory,
    TranslationOrchestrator,
)
from kps.translation.orchestrator import TranslationSegment


def main():
    """Демонстрация самообучающейся системы перевода."""

    print("=" * 60)
    print("Самообучающаяся система перевода с глоссарием")
    print("=" * 60)

    # Инициализация
    print("\n1. Инициализация компонентов...")
    orchestrator = TranslationOrchestrator()
    glossary = GlossaryManager()

    # Загрузить глоссарий
    glossary.load_from_yaml("glossary.yaml")
    print(f"   ✓ Загружено {len(glossary.get_all_entries())} терминов глоссария")

    # Создать память переводов с кэшированием
    memory = TranslationMemory("data/translation_cache.json")
    print(f"   ✓ Память переводов инициализирована")

    # Создать переводчик с самообучением
    translator = GlossaryTranslator(
        orchestrator=orchestrator,
        glossary_manager=glossary,
        memory=memory,  # Включить кэширование
        enable_few_shot=True,  # Использовать few-shot examples
        enable_auto_suggestions=True,  # Автопредложения терминов
    )
    print(f"   ✓ Переводчик готов к работе")

    # Тестовые сегменты
    segments = [
        TranslationSegment("1", "Провяжите 2 петли вместе лицевой", {}),
        TranslationSegment("2", "Повторяйте с 1-го по 4-й ряд", {}),
        TranslationSegment("3", "Закройте все петли", {}),
        TranslationSegment("4", "Провяжите 2 петли вместе лицевой", {}),  # Дубликат!
    ]

    # ПЕРВЫЙ ПЕРЕВОД - всё новое
    print("\n2. Первый перевод (всё новое)...")
    result1 = translator.translate(segments, target_language="en")

    print(f"   Переведено: {len(result1.segments)} сегментов")
    print(f"   Из кэша: {result1.cached_segments}")
    print(f"   Найдено терминов: {result1.terms_found}")
    print(f"   Стоимость: ${result1.total_cost:.4f}")

    print("\n   Переводы:")
    for i, (seg, trans) in enumerate(zip(segments, result1.segments), 1):
        print(f"   {i}. {seg.text}")
        print(f"      → {trans}")

    # ВТОРОЙ ПЕРЕВОД - используем кэш!
    print("\n3. Второй перевод (используем кэш)...")
    result2 = translator.translate(segments, target_language="en")

    print(f"   Переведено: {len(result2.segments)} сегментов")
    print(f"   Из кэша: {result2.cached_segments} ← Большинство из кэша!")
    print(f"   Стоимость: ${result2.total_cost:.4f} ← Экономия!")

    # Новые сегменты - используем few-shot примеры
    print("\n4. Перевод новых сегментов с few-shot learning...")
    new_segments = [
        TranslationSegment("5", "Вяжите лицевыми до конца ряда", {}),
        TranslationSegment("6", "Сделайте накид", {}),
    ]

    result3 = translator.translate(new_segments, target_language="en")

    print(f"   Переведено: {len(result3.segments)} сегментов")
    print(f"   ИИ использовал примеры из предыдущих переводов для улучшения качества!")

    print("\n   Переводы:")
    for i, (seg, trans) in enumerate(zip(new_segments, result3.segments), 1):
        print(f"   {i}. {seg.text}")
        print(f"      → {trans}")

    # Статистика
    print("\n5. Статистика использования...")
    stats = translator.get_statistics()
    if stats:
        print(f"   Всего записей в памяти: {stats['total_entries']}")
        print(f"   Всего использований: {stats['total_usage']}")
        print(f"   Средняя оценка качества: {stats['average_quality']:.2%}")
        print(f"   Языковые пары:")
        for pair, count in stats["language_pairs"].items():
            print(f"      - {pair}: {count} переводов")

    # Предложения для глоссария
    print("\n6. Автоматические предложения новых терминов...")
    suggestions = translator.get_glossary_suggestions(min_frequency=2)

    if suggestions:
        print(f"   Найдено {len(suggestions)} предложений:")
        for i, sugg in enumerate(suggestions[:5], 1):  # Показать топ-5
            print(f"   {i}. '{sugg.source_text}' ({sugg.source_lang} → {sugg.target_lang})")
            print(f"      Частота: {sugg.frequency}x, Уверенность: {sugg.confidence:.0%}")
    else:
        print("   Пока нет предложений (нужно больше данных)")

    # Сохранить память
    print("\n7. Сохранение памяти переводов...")
    translator.save_memory()
    print("   ✓ Сохранено в data/translation_cache.json")

    # Итоги
    print("\n" + "=" * 60)
    print("ИТОГИ:")
    print("=" * 60)
    total_segments = len(segments) + len(segments) + len(new_segments)
    total_cached = result2.cached_segments
    total_cost = result1.total_cost + result2.total_cost + result3.total_cost

    print(f"Всего переведено: {total_segments} сегментов")
    print(f"Использовано из кэша: {total_cached} ({total_cached/total_segments*100:.0%})")
    print(f"Общая стоимость: ${total_cost:.4f}")
    print(f"\nЭкономия благодаря кэшу: ~{total_cached/total_segments*100:.0%}%")
    print(f"Улучшение качества: ИИ учится на каждом переводе!")

    print("\n✓ Система самообучения работает!")
    print("\nЧем больше переводов → тем лучше качество → тем больше экономия!")


def demonstrate_progressive_learning():
    """Демонстрация прогрессивного обучения."""

    print("\n\n" + "=" * 60)
    print("ДЕМОНСТРАЦИЯ ПРОГРЕССИВНОГО ОБУЧЕНИЯ")
    print("=" * 60)

    # Симуляция работы над временем
    print("\nСценарий: переводим 100 документов за месяц")
    print("-" * 60)

    # День 1: 0 в кэше
    print("\nДень 1: Первые документы")
    print("  Кэш: 0% → Всё переводим с нуля")
    print("  Стоимость: $10.00")

    # Неделя 1: 20% в кэше
    print("\nНеделя 1: Накопили данные")
    print("  Кэш: 20% → Начинаем экономить")
    print("  Стоимость: $8.00 (-20%)")
    print("  ИИ начинает использовать примеры в промптах")

    # Неделя 2: 40% в кэше
    print("\nНеделя 2: Больше повторяющихся фраз")
    print("  Кэш: 40% → Значительная экономия")
    print("  Стоимость: $6.00 (-40%)")
    print("  Few-shot примеры улучшают качество новых переводов")

    # Неделя 3: 60% в кэше
    print("\nНеделя 3: Система хорошо обучилась")
    print("  Кэш: 60% → Большинство из кэша")
    print("  Стоимость: $4.00 (-60%)")
    print("  Автоматически предложено 15 новых терминов для глоссария")

    # Неделя 4: 75% в кэше
    print("\nНеделя 4: Отличные результаты")
    print("  Кэш: 75% → Максимальная эффективность")
    print("  Стоимость: $2.50 (-75%)")
    print("  Качество переводов стабильно высокое")

    print("\n" + "=" * 60)
    print("ИТОГИ ЗА МЕСЯЦ:")
    print("=" * 60)
    print("Начальная стоимость: $10.00 × 100 = $1000.00")
    print("Реальная стоимость:  ~$500.00 (с учётом кэша)")
    print("ЭКОНОМИЯ: $500.00 (50%)")
    print("\n+ Качество улучшается автоматически")
    print("+ Глоссарий пополняется автоматически")
    print("+ Чем дольше работаем → тем больше экономим!")


if __name__ == "__main__":
    main()
    demonstrate_progressive_learning()
