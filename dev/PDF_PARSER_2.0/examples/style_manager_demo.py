#!/usr/bin/env python3
"""
Style Manager Demo

Демонстрация работы с системой стилей InDesign для KPS v2.0.
Показывает, как загружать стили, применять их к контенту и генерировать IDML.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kps.indesign.style_manager import StyleManager


def demo_load_styles():
    """Демо 1: Загрузка стилей из YAML."""
    print("=" * 80)
    print("DEMO 1: Загрузка стилей из YAML")
    print("=" * 80)

    # Путь к конфигурации
    styles_yaml = Path(__file__).parent.parent / "templates" / "indesign" / "master-template-styles.yaml"

    if not styles_yaml.exists():
        print(f"❌ Файл не найден: {styles_yaml}")
        return

    # Загрузить стили
    print(f"\n📂 Загрузка стилей из: {styles_yaml.name}")
    manager = StyleManager.from_yaml(styles_yaml)

    print(f"\n✅ Загружено:")
    print(f"   - Стилей параграфов: {len(manager.paragraph_styles)}")
    print(f"   - Стилей символов: {len(manager.character_styles)}")
    print(f"   - Стилей объектов: {len(manager.object_styles)}")
    print(f"   - Цветовых образцов: {len(manager.colors)}")


def demo_paragraph_styles():
    """Демо 2: Работа со стилями параграфов."""
    print("\n" + "=" * 80)
    print("DEMO 2: Стили параграфов")
    print("=" * 80)

    styles_yaml = Path(__file__).parent.parent / "templates" / "indesign" / "master-template-styles.yaml"
    manager = StyleManager.from_yaml(styles_yaml)

    # Примеры стилей
    style_names = ["Heading1", "Heading2", "BodyText", "MaterialsList", "FigureCaption"]

    print("\n📝 Определения стилей параграфов:\n")

    for name in style_names:
        style = manager.get_paragraph_style(name)
        if style:
            print(f"   {name}:")
            print(f"      Шрифт: {style.font_family} {style.font_style}")
            print(f"      Размер: {style.size} pt")
            print(f"      Интерлиньяж: {style.leading} pt")
            print(f"      Перед абзацем: {style.space_before} pt")
            print(f"      После абзаца: {style.space_after} pt")
            if style.based_on != "[No Paragraph Style]":
                print(f"      Основан на: {style.based_on}")
            print()


def demo_content_mapping():
    """Демо 3: Маппинг типов контента на стили."""
    print("=" * 80)
    print("DEMO 3: Маппинг типов контента на стили")
    print("=" * 80)

    styles_yaml = Path(__file__).parent.parent / "templates" / "indesign" / "master-template-styles.yaml"
    manager = StyleManager.from_yaml(styles_yaml)

    # Примеры типов контента
    content_types = [
        "section_title",
        "paragraph",
        "materials_list",
        "figure_caption",
        "note",
        "row_instruction",
    ]

    print("\n🔗 Маппинг типов контента:\n")

    for content_type in content_types:
        style_ref = manager.get_style_for_content(content_type)
        if style_ref:
            print(f"   {content_type:20} → {style_ref}")
        else:
            print(f"   {content_type:20} → ❌ НЕ НАЙДЕН")


def demo_character_styles():
    """Демо 4: Стили символов (встроенное форматирование)."""
    print("\n" + "=" * 80)
    print("DEMO 4: Стили символов")
    print("=" * 80)

    styles_yaml = Path(__file__).parent.parent / "templates" / "indesign" / "master-template-styles.yaml"
    manager = StyleManager.from_yaml(styles_yaml)

    style_names = ["Emphasis", "Strong", "Abbreviation", "Number"]

    print("\n✨ Стили символов (для встроенного форматирования):\n")

    for name in style_names:
        style = manager.get_character_style(name)
        if style:
            print(f"   {name}:")
            if style.font_family:
                print(f"      Шрифт: {style.font_family}")
            if style.font_style:
                print(f"      Начертание: {style.font_style}")
            if style.size:
                print(f"      Размер: {style.size}")
            if style.underline:
                print(f"      Подчёркивание: Да")
            if style.no_break:
                print(f"      Запрет разрыва: Да")
            print()


def demo_language_settings():
    """Демо 5: Языковые настройки."""
    print("=" * 80)
    print("DEMO 5: Языковые настройки")
    print("=" * 80)

    styles_yaml = Path(__file__).parent.parent / "templates" / "indesign" / "master-template-styles.yaml"
    manager = StyleManager.from_yaml(styles_yaml)

    languages = ["ru", "en", "fr"]

    print("\n🌍 Настройки для разных языков:\n")

    for lang in languages:
        settings = manager.get_language_settings(lang)
        if settings:
            print(f"   {lang.upper()}:")
            print(f"      Словарь: {settings.get('hyphenation_dictionary', 'N/A')}")
            print(f"      Компоновщик: {settings.get('composer', 'N/A')}")

            quotes = settings.get('quotes', {})
            if quotes:
                print(f"      Кавычки: {quotes.get('opening_double', '')} ... {quotes.get('closing_double', '')}")
            print()


def demo_apply_styles():
    """Демо 6: Применение стилей к блокам контента."""
    print("=" * 80)
    print("DEMO 6: Применение стилей к блокам")
    print("=" * 80)

    styles_yaml = Path(__file__).parent.parent / "templates" / "indesign" / "master-template-styles.yaml"
    manager = StyleManager.from_yaml(styles_yaml)

    # Примеры блоков на разных языках
    examples = [
        ("section_title", "ru", "Материалы"),
        ("paragraph", "en", "100% merino wool"),
        ("figure_caption", "fr", "Figure 1: Détails du fil"),
    ]

    print("\n🎨 Применение стилей к контенту:\n")

    for block_type, language, text in examples:
        print(f"   Текст: '{text}'")
        print(f"   Тип: {block_type}, Язык: {language}")

        # Получить атрибуты стиля
        attrs = manager.apply_style_to_block(block_type, language)

        print(f"   Применяемые атрибуты:")
        for key, value in attrs.items():
            print(f"      {key}: {value}")
        print()


def demo_object_styles():
    """Демо 7: Стили объектов (изображения, рамки)."""
    print("=" * 80)
    print("DEMO 7: Стили объектов")
    print("=" * 80)

    styles_yaml = Path(__file__).parent.parent / "templates" / "indesign" / "master-template-styles.yaml"
    manager = StyleManager.from_yaml(styles_yaml)

    object_names = ["FigureInline", "FigureBlock", "Chart"]

    print("\n🖼️  Стили объектов (изображения и рамки):\n")

    for name in object_names:
        style = manager.get_object_style(name)
        if style:
            print(f"   {name}:")
            print(f"      Тип привязки: {style.anchored_position}")
            print(f"      Точка привязки: {style.anchor_point}")
            print(f"      Выравнивание: {style.horizontal_alignment}")
            print(f"      Обтекание текстом: {style.text_wrap}")
            if style.max_width:
                print(f"      Макс. ширина: {style.max_width}")
            print()


def demo_full_example():
    """Демо 8: Полный пример применения стилей."""
    print("=" * 80)
    print("DEMO 8: Полный пример применения")
    print("=" * 80)

    styles_yaml = Path(__file__).parent.parent / "templates" / "indesign" / "master-template-styles.yaml"
    manager = StyleManager.from_yaml(styles_yaml)

    print("\n📄 Пример документа с применёнными стилями:\n")

    # Структура документа
    document_structure = [
        ("section_title", "Materials", "ru"),
        ("paragraph", "100% шерсть мериноса, 400м/100г", "ru"),
        ("gauge_info", "Плотность: 22п × 30р = 10см лицевой гладью", "ru"),
        ("figure_caption", "Рис. 1: Пряжа и образец", "ru"),
    ]

    for block_type, text, language in document_structure:
        # Получить стиль
        style_ref = manager.get_style_for_content(block_type)
        style = manager.get_paragraph_style(style_ref.split("/")[1]) if style_ref else None

        if style:
            print(f"   {text}")
            print(f"      └─ Стиль: {style_ref}")
            print(f"         Шрифт: {style.font_family} {style.font_style} {style.size}pt/{style.leading}pt")
            if style.alignment != "LeftAlign":
                print(f"         Выравнивание: {style.alignment}")
            print()


def main():
    """Запустить все демонстрации."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 25 + "Style Manager Demo" + " " * 35 + "║")
    print("╚" + "=" * 78 + "╝")

    try:
        demo_load_styles()
        demo_paragraph_styles()
        demo_content_mapping()
        demo_character_styles()
        demo_language_settings()
        demo_apply_styles()
        demo_object_styles()
        demo_full_example()

        print("\n" + "=" * 80)
        print("✅ Все демонстрации завершены успешно!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
