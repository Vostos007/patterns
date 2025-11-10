# Serena MCP - Полное руководство для CompetitorMonitor RU

## 🧠 Что такое Serena MCP?

Serena MCP предоставляет IDE-подобные инструменты для работы с кодом на уровне символов (классы, функции, методы), используя Language Server Protocol (LSP). Это позволяет работать с Python кодом **семантически**, а не через текстовый поиск.

**Ключевые преимущества:**
- ⚡ Снижение использования токенов на 70-90% (работа с символами вместо целых файлов)
- 🎯 Точная навигация по коду через LSP (Python, TypeScript, Go, Rust, Java и ещё 20+ языков)
- 🔍 Понимание зависимостей и отношений между символами
- ✏️ Редактирование на уровне символов (insert_after_symbol, replace_symbol_body)
- 💾 Система памяти для хранения архитектурных знаний о проекте

---

## 📚 Основные инструменты Serena

### 🔍 Поиск и навигация

#### `mcp__serena__get_symbols_overview`
Обзор файла без чтения всего содержимого.

**Параметры:**
- `relative_path`: путь к файлу
- `max_answer_chars`: лимит символов ответа (опционально)

**Использование:**
```python
get_symbols_overview("src/core/scraper_engine.py")
# → Возвращает структуру: классы, методы, функции верхнего уровня
```

**Когда использовать:**
- Первое знакомство с файлом
- Понимание структуры без чтения всего кода
- Поиск нужных символов перед детальным изучением

---

#### `mcp__serena__find_symbol`
Поиск символов по имени с поддержкой паттернов.

**Параметры:**
- `name_path`: путь символа (например, "ClassName/method")
- `relative_path`: ограничить поиск файлом/директорией (опционально)
- `include_body`: включить тело символа (default: false)
- `depth`: глубина дочерних символов (default: 0)
- `substring_matching`: поиск по подстроке (default: false)
- `include_kinds`: фильтр по типам (классы=5, функции=12, методы=6)
- `exclude_kinds`: исключить типы символов

**Использование:**
```python
# Найти класс
find_symbol("ScraperEngine")

# Найти метод класса с телом
find_symbol("ScraperEngine/scrape_product", include_body=True)

# Найти все методы класса
find_symbol("ScraperEngine", depth=1)

# Поиск по подстроке
find_symbol("parse", substring_matching=True)

# Только функции
find_symbol("extract", include_kinds=[12])
```

**Паттерны name_path:**
- `method` - любой символ с именем "method" (в любом месте)
- `Class/method` - метод "method" в классе "Class" (или вложенных классах)
- `/Class/method` - ТОЛЬКО в топ-уровне (абсолютный путь)

---

#### `mcp__serena__find_referencing_symbols`
Поиск всех ссылок на символ.

**Параметры:**
- `name_path`: путь к символу
- `relative_path`: файл, где находится символ
- `include_kinds` / `exclude_kinds`: фильтры

**Использование:**
```python
find_referencing_symbols("make_request", "src/core/scraper_engine.py")
# → Где используется функция make_request?
# → Какие модули зависят от этой функции?
```

**Когда использовать:**
- Перед изменением функции/метода
- Анализ зависимостей
- Рефакторинг кода
- Понимание flow выполнения

---

#### `mcp__serena__search_for_pattern`
Regex поиск по паттерну в коде.

**Параметры:**
- `substring_pattern`: regex паттерн
- `relative_path`: ограничить директорией/файлом
- `context_lines_before` / `context_lines_after`: контекст
- `restrict_search_to_code_files`: только код (default: false)
- `paths_include_glob`: glob для включения файлов
- `paths_exclude_glob`: glob для исключения файлов

**Использование:**
```python
# Найти все вызовы функции
search_for_pattern(r"make_request\(", context_lines_after=2)

# Поиск только в парсерах
search_for_pattern(
    r"def parse_",
    paths_include_glob="src/parsers/**/*.py"
)

# Исключить тесты
search_for_pattern(
    r"class.*Parser",
    paths_exclude_glob="**/test_*.py"
)
```

---

### ✏️ Редактирование кода

#### `mcp__serena__replace_symbol_body`
Замена тела символа целиком.

**Параметры:**
- `name_path`: путь к символу
- `relative_path`: файл с символом
- `body`: новое тело (включая сигнатуру для функций)

**Использование:**
```python
replace_symbol_body(
    "parse_product",
    "src/parsers/base_parser.py",
    """def parse_product(self, html: str) -> Product:
    \"\"\"Parse product from HTML.\"\"\"
    # New implementation
    return Product(...)
"""
)
```

**⚠️ ВАЖНО:**
- `body` включает сигнатуру функции/метода
- НЕ включает docstring над функцией (если он отдельно)
- НЕ включает импорты

---

#### `mcp__serena__insert_after_symbol`
Вставка кода после символа.

**Параметры:**
- `name_path`: символ, после которого вставить
- `relative_path`: файл
- `body`: код для вставки

**Использование:**
```python
# Добавить новый метод после существующего
insert_after_symbol(
    "ScraperEngine/scrape_product",
    "src/core/scraper_engine.py",
    """
    async def scrape_products_batch(self, urls: list[str]) -> list[Product]:
        \"\"\"Scrape multiple products.\"\"\"
        return [await self.scrape_product(url) for url in urls]
"""
)

# Добавить класс в конец файла
insert_after_symbol(
    "LastClass",
    "src/parsers/parsers.py",
    """
class NewSiteParser(BaseParser):
    def parse_product(self, html: str) -> Product:
        ...
"""
)
```

---

#### `mcp__serena__insert_before_symbol`
Вставка кода до символа.

**Параметры:**
- `name_path`: символ, перед которым вставить
- `relative_path`: файл
- `body`: код для вставки

**Использование:**
```python
# Добавить импорт перед первым классом
insert_before_symbol(
    "ScraperEngine",
    "src/core/scraper_engine.py",
    "from typing import Protocol\n\n"
)

# Добавить докстринг перед функцией
insert_before_symbol(
    "parse_variations",
    "src/parsers/variation_parser.py",
    '"""Module for parsing product variations."""\n\n'
)
```

---

#### `mcp__serena__rename_symbol`
Переименование символа во всём проекте.

**Параметры:**
- `name_path`: текущее имя символа
- `relative_path`: файл с символом
- `new_name`: новое имя

**Использование:**
```python
rename_symbol(
    "parse_variations",
    "src/parsers/variation_parser.py",
    "extract_product_variations"
)
# → Обновит все ссылки на функцию во всём проекте
```

---

### 📁 Работа с файлами

#### `mcp__serena__list_dir`
Просмотр структуры директорий.

**Параметры:**
- `relative_path`: путь к директории ("." для корня)
- `recursive`: рекурсивный обход
- `skip_ignored_files`: пропустить .gitignore файлы

**Использование:**
```python
# Структура проекта
list_dir(".", recursive=True, skip_ignored_files=True)

# Только парсеры
list_dir("src/parsers", recursive=False)
```

---

#### `mcp__serena__find_file`
Поиск файлов по маске.

**Параметры:**
- `file_mask`: маска файла (* и ? wildcards)
- `relative_path`: где искать

**Использование:**
```python
# Все Python файлы
find_file("*.py", "src")

# Все парсеры
find_file("*_parser.py", "src/parsers")

# Тестовые файлы
find_file("test_*.py", "tests")
```

---

### 💾 Система памяти (Knowledge Base)

#### `mcp__serena__write_memory`
Сохранение знаний о проекте.

**Параметры:**
- `memory_name`: имя файла памяти (без расширения)
- `content`: содержимое (markdown)

**Использование:**
```python
write_memory(
    "proxy_rotation_architecture",
    """# Proxy Rotation Strategy

## Current Implementation
- Round-robin rotation
- Health checks every 5 minutes
- Automatic removal of failed proxies

## Future Improvements
- Weighted rotation based on success rate
- Geographic optimization
"""
)
```

**Что сохранять:**
- Архитектурные решения
- Паттерны реализации
- Стратегии антибот обхода
- Исправленные баги
- Оптимизации производительности

---

#### `mcp__serena__read_memory`
Чтение сохранённых знаний.

**Параметры:**
- `memory_file_name`: имя файла памяти

**Использование:**
```python
read_memory("proxy_rotation_architecture")
```

---

#### `mcp__serena__list_memories`
Список всех доступных памятей.

**Использование:**
```python
list_memories()
# → Показывает все сохранённые знания о проекте
```

---

#### `mcp__serena__delete_memory`
Удаление устаревшей памяти.

**Параметры:**
- `memory_file_name`: имя файла для удаления

**Использование:**
```python
delete_memory("obsolete_implementation_notes")
```

---

### 🎯 Управление проектом

#### `mcp__serena__activate_project`
Переключение между проектами.

**Параметры:**
- `project`: имя или путь к проекту

**Использование:**
```python
activate_project("/Users/vostos/Dev/Webscraper")
```

---

#### `mcp__serena__get_current_config`
Текущая конфигурация Serena.

**Использование:**
```python
get_current_config()
# → Показывает активный проект, режимы, доступные инструменты
```

---

#### `mcp__serena__check_onboarding_performed`
Проверка инициализации проекта.

**Использование:**
```python
check_onboarding_performed()
# → True/False - был ли выполнен onboarding
```

---

#### `mcp__serena__onboarding`
Инициализация нового проекта.

**Использование:**
```python
onboarding()
# → Создаёт необходимую структуру для работы Serena
```

---

### 🧠 Рефлексия и мышление

#### `mcp__serena__think_about_collected_information`
Анализ собранной информации.

**Когда использовать:**
- После серии поисковых операций
- После чтения нескольких символов
- Перед началом изменений

**Что проверяется:**
- Достаточно ли данных для задачи?
- Релевантна ли информация?
- Нужно ли собрать ещё данных?

---

#### `mcp__serena__think_about_task_adherence`
Проверка соответствия задаче.

**Когда использовать:**
- Перед большими изменениями
- После длительной работы
- При переключении контекста

**Что проверяется:**
- Правильное ли направление работы?
- Соответствует ли работа требованиям?
- Нет ли отклонений от задачи?

---

#### `mcp__serena__think_about_whether_you_are_done`
Проверка завершённости задачи.

**Когда использовать:**
- Перед завершением задачи
- После выполнения всех шагов
- Перед коммитом изменений

**Что проверяется:**
- Все ли требования выполнены?
- Нет ли пропущенных шагов?
- Готово ли решение к финализации?

---

## 🚀 Рабочие процессы (Workflows)

### 📖 Workflow: Изучение незнакомого кода

```bash
# 1. Обзор структуры проекта
list_dir("src", recursive=True, skip_ignored_files=True)
# → Понять организацию файлов и модулей

# 2. Обзор ключевых файлов (БЕЗ чтения всего содержимого)
get_symbols_overview("src/core/scraper_engine.py")
# → Увидеть классы, методы, функции

# 3. Целевой поиск нужного символа
find_symbol("ScraperEngine", depth=1)
# → Список всех методов класса

# 4. Детальное изучение конкретного метода
find_symbol("ScraperEngine/scrape_product", include_body=True)
# → Прочитать только нужный метод

# 5. Понять зависимости
find_referencing_symbols("make_request", "src/core/scraper_engine.py")
# → Кто использует эту функцию?

# 6. Рефлексия
think_about_collected_information
# → Достаточно ли информации для задачи?

# 7. Сохранить знания
write_memory("scraper_engine_architecture", "Notes about design...")
```

**Экономия токенов:**
- ❌ Чтение целого файла: ~2000 токенов
- ✅ Serena workflow: ~300 токенов
- **💰 Экономия: 85%**

---

### ✏️ Workflow: Рефакторинг кода

```bash
# 1. Найти символ для изменения
find_symbol("parse_variations", include_body=True, relative_path="src/parsers")
# → Увидеть текущую реализацию

# 2. Проанализировать использование
find_referencing_symbols("parse_variations", "src/parsers/variation_parser.py")
# → Проверить все места использования

# 3. Проверить задачу
think_about_task_adherence
# → Правильно ли понял требования?

# 4. Выполнить изменение
replace_symbol_body(
    "parse_variations",
    "src/parsers/variation_parser.py",
    new_implementation
)

# 5. Обновить зависимости (если нужно)
# Найти и обновить вызовы функции в других местах

# 6. Финальная проверка
think_about_whether_you_are_done
# → Всё ли выполнено?

# 7. Документировать
write_memory("variation_parser_refactoring", "Reasons and changes...")
```

---

### 🐛 Workflow: Исправление бага

```bash
# 1. Локализация проблемы
search_for_pattern(
    "error_pattern",
    context_lines_before=3,
    context_lines_after=3
)
# → Найти все вхождения проблемного кода

# 2. Анализ структуры файла с багом
get_symbols_overview("src/module_with_bug.py")

# 3. Детальный анализ проблемного символа
find_symbol("buggy_function", include_body=True, relative_path="src/module_with_bug.py")

# 4. Понять контекст использования
find_referencing_symbols("buggy_function", "src/module_with_bug.py")
# → Кто вызывает? Какие зависимости?

# 5. Проверить задачу
think_about_collected_information
# → Понятна ли причина бага?

# 6. Исправление
replace_symbol_body("buggy_function", "src/module_with_bug.py", fixed_code)

# 7. Сохранить знания
write_memory(
    "bug_fix_proxy_rotation_20250130",
    """# Bug Fix: Proxy Rotation Deadlock

## Problem
Proxy rotation caused deadlock when all proxies failed

## Solution
Added fallback to direct connection after N failures

## Files Changed
- src/core/simple_proxy_manager.py
"""
)
```

---

### 📝 Workflow: Добавление новой функциональности

```bash
# 1. Изучить существующий код
get_symbols_overview("src/parsers/base_parser.py")
list_memories()  # Проверить существующие знания

# 2. Найти базовый класс/паттерн
find_symbol("BaseParser", include_body=True, depth=1)
# → Понять интерфейс для реализации

# 3. Найти место вставки
find_symbol("LastParser")  # Последний парсер в файле

# 4. Добавить новый код
insert_after_symbol(
    "SittingKnittingParser",
    "src/parsers/parsers_registry.py",
    new_parser_code
)

# 5. Добавить импорты (если нужно)
insert_before_symbol(
    "BaseParser",
    "src/parsers/base_parser.py",
    "from typing import Protocol\n"
)

# 6. Проверка готовности
think_about_whether_you_are_done

# 7. Документировать решение
write_memory(
    "new_parser_implementation_guide",
    """# Adding New Site Parser

## Steps
1. Inherit from BaseParser
2. Implement parse_product()
3. Add to parsers_registry.py
4. Test with /variation-test
"""
)
```

---

## 💡 Best Practices

### ✅ DO: Эффективное использование

#### 1. Сначала обзор, потом детали
```python
# ✅ ПРАВИЛЬНО
get_symbols_overview("file.py")  # Структура - 200 токенов
find_symbol("TargetClass", depth=1)  # Методы класса - 100 токенов
find_symbol("TargetClass/method", include_body=True)  # Конкретный метод - 50 токенов
# ИТОГО: 350 токенов

# ❌ НЕПРАВИЛЬНО
Read("file.py")  # Весь файл - 2000+ токенов
```

#### 2. Используй символьные операции вместо текстовых
```python
# ✅ ПРАВИЛЬНО
replace_symbol_body("method", new_code)

# ❌ НЕПРАВИЛЬНО
# Regex замена через Edit - может сломать код
```

#### 3. Проверяй зависимости перед изменением
```python
# ✅ ПРАВИЛЬНО
find_referencing_symbols("function_to_change")  # Кто использует?
# Затем изменение
replace_symbol_body("function_to_change", new_impl)

# ❌ НЕПРАВИЛЬНО
replace_symbol_body("function_to_change", new_impl)  # Без проверки
# → Может сломать другие модули!
```

#### 4. Используй память для архитектурных знаний
```python
# ✅ ПРАВИЛЬНО
write_memory("proxy_rotation_strategy", """
## Strategy
- Round-robin with health checks
- Fallback to direct after 3 failures
""")

list_memories()  # Перед началом работы - что уже известно?
read_memory("proxy_rotation_strategy")  # Прочитать нужные знания
```

#### 5. Используй рефлексию перед завершением
```python
# ✅ ПРАВИЛЬНО
think_about_collected_information  # После сбора данных
think_about_task_adherence  # Перед большими изменениями
think_about_whether_you_are_done  # Перед завершением
```

---

### ❌ DON'T: Антипаттерны

#### 1. НЕ читай весь файл, если нужен только один символ
```python
# ❌ НЕПРАВИЛЬНО (2000+ токенов)
Read("src/parsers/variation_parser.py")

# ✅ ПРАВИЛЬНО (50 токенов)
find_symbol("VariationParser/parse_variations", include_body=True)
```

#### 2. НЕ используй regex для рефакторинга символов
```python
# ❌ НЕПРАВИЛЬНО
Edit(file, old_string=r"def old_name\(.*\):", new_string="def new_name(...):")
# → Может сломать код, не обновит все ссылки

# ✅ ПРАВИЛЬНО
rename_symbol("old_name", "src/file.py", "new_name")
# → Обновит все ссылки во всём проекте
```

#### 3. НЕ игнорируй зависимости
```python
# ❌ НЕПРАВИЛЬНО
replace_symbol_body("critical_function", new_code)
# → Сломает все модули, которые используют эту функцию

# ✅ ПРАВИЛЬНО
find_referencing_symbols("critical_function")  # Проверить
# Затем изменить с учётом обратной совместимости
replace_symbol_body("critical_function", backward_compatible_code)
```

#### 4. НЕ забывай индексировать большие проекты
```bash
# ❌ НЕПРАВИЛЬНО
# Работать без индексации - первый запрос будет долгим

# ✅ ПРАВИЛЬНО
# В терминале перед первым использованием:
serena project index

# Это ускорит все операции на порядок!
```

---

## 🎓 Примеры для CompetitorMonitor RU

### Пример 1: Добавить новый парсер для сайта

```python
# Шаг 1: Изучить существующие парсеры
get_symbols_overview("src/parsers/sittingknitting_parser.py")

# Шаг 2: Понять базовый класс
find_symbol("BaseParser", include_body=True, relative_path="src/parsers")

# Шаг 3: Проверить паттерн регистрации
search_for_pattern(
    r"class \w+Parser\(BaseParser\)",
    paths_include_glob="src/parsers/**/*.py"
)

# Шаг 4: Создать новый парсер
insert_after_symbol(
    "SittingKnittingParser",
    "src/parsers/sittingknitting_parser.py",
    """

class NewSiteParser(BaseParser):
    \"\"\"Parser for newsite.ru\"\"\"

    def parse_product(self, html: str) -> Product:
        soup = BeautifulSoup(html, 'html.parser')

        name = soup.select_one('.product-name').get_text(strip=True)
        price = self._extract_price(soup.select_one('.price').get_text())

        return Product(
            name=name,
            price=price,
            url=self.current_url,
            site="newsite.ru"
        )

    def _extract_price(self, price_text: str) -> float:
        # Extract numeric price
        return float(re.sub(r'[^\d.]', '', price_text))
"""
)

# Шаг 5: Сохранить паттерн
write_memory("parser_addition_guide", """
# Adding New Site Parser

## Template
1. Inherit from BaseParser
2. Implement parse_product(html: str) -> Product
3. Use BeautifulSoup for parsing
4. Follow CSS selector pattern from other parsers
5. Test with /variation-test

## Registration
- Add to src/parsers/<sitename>_parser.py
- Import in __init__.py if needed
""")
```

---

### Пример 2: Оптимизировать антибот систему

```python
# Шаг 1: Найти антибот менеджер
find_symbol("AntibotManager", depth=1)
# → Увидеть все методы: rotate_proxy, check_health, etc.

# Шаг 2: Изучить ротацию прокси
find_symbol("rotate_proxy", include_body=True, relative_path="src/core")

# Шаг 3: Проверить использование
find_referencing_symbols("rotate_proxy", "src/core/simple_proxy_manager.py")
# → Кто вызывает? Как часто? В каком контексте?

# Шаг 4: Найти проблемные паттерны
search_for_pattern(
    r"rotate_proxy\(",
    context_lines_after=2,
    paths_include_glob="src/**/*.py"
)

# Шаг 5: Оптимизировать реализацию
replace_symbol_body(
    "rotate_proxy",
    "src/core/simple_proxy_manager.py",
    """async def rotate_proxy(self) -> dict[str, str] | None:
    \"\"\"Rotate to next healthy proxy with weighted selection.\"\"\"
    if not self.proxies:
        return None

    # Weighted selection based on success rate
    weights = [p.get('success_rate', 0.5) for p in self.proxies]
    selected = random.choices(self.proxies, weights=weights, k=1)[0]

    self.current_proxy = selected
    return selected
"""
)

# Шаг 6: Документировать оптимизацию
write_memory("antibot_optimization_notes", """
# Proxy Rotation Optimization

## Changes Made
- Replaced round-robin with weighted selection
- Weight based on historical success rate
- Fallback to direct connection after 3 failures

## Performance Impact
- 30% reduction in blocked requests
- Better proxy utilization
- Automatic bad proxy filtering

## Files Modified
- src/core/simple_proxy_manager.py: rotate_proxy()
""")
```

---

### Пример 3: Рефакторинг парсинга вариаций

```python
# Шаг 1: Найти парсер вариаций
find_symbol("VariationParser", include_body=False, depth=2)
# → Увидеть структуру: методы, вложенные классы

# Шаг 2: Изучить метод парсинга
find_symbol("VariationParser/parse_variations", include_body=True)

# Шаг 3: Найти все использования
find_referencing_symbols("parse_variations", "src/parsers/variation_parser.py")
# → Проверить, кто использует этот метод

# Шаг 4: Проверить текущие тесты
search_for_pattern(
    r"test.*variation",
    paths_include_glob="tests/**/*.py"
)

# Шаг 5: Рефакторинг с переименованием
rename_symbol(
    "parse_variations",
    "src/parsers/variation_parser.py",
    "extract_product_variations"
)
# → Автоматически обновит все ссылки

# Шаг 6: Улучшить реализацию
replace_symbol_body(
    "extract_product_variations",
    "src/parsers/variation_parser.py",
    """def extract_product_variations(
    self,
    html: str,
    cms_type: str = "auto"
) -> list[ProductVariation]:
    \"\"\"Extract product variations with CMS detection.\"\"\"
    soup = BeautifulSoup(html, 'html.parser')

    # Auto-detect CMS if not specified
    if cms_type == "auto":
        cms_type = self._detect_cms(soup)

    # CMS-specific extraction
    extractor = self._get_cms_extractor(cms_type)
    variations = extractor.extract(soup)

    return [
        ProductVariation(
            size=v['size'],
            color=v.get('color'),
            sku=v.get('sku'),
            stock=v.get('stock', 0),
            price=v.get('price')
        )
        for v in variations
    ]
"""
)

# Шаг 7: Документировать решения
write_memory("variation_refactoring_decisions", """
# Variation Parser Refactoring

## Decisions
1. Renamed parse_variations → extract_product_variations (clearer intent)
2. Added auto CMS detection (reduces manual configuration)
3. Separated CMS-specific extractors (better maintainability)

## Architecture
- Main method: extract_product_variations()
- CMS detection: _detect_cms()
- CMS extractors: _get_cms_extractor() → strategy pattern

## Supported CMS
- WooCommerce, Shopify, OpenCart, Magento, PrestaShop

## Testing
- Run: /variation-test
- Expected: 95%+ accuracy on all supported CMS
""")
```

---

## 📊 Сравнение эффективности

### Сценарий 1: Изучение нового модуля

| Подход | Операции | Токены | Время |
|--------|----------|--------|-------|
| **Без Serena** | Read entire file | ~2500 | 15s |
| **С Serena** | get_symbols_overview + find_symbol × 2 | ~350 | 3s |
| **Экономия** | — | **86%** | **80%** |

### Сценарий 2: Рефакторинг функции

| Подход | Операции | Токены | Время |
|--------|----------|--------|-------|
| **Без Serena** | Read file + Grep + Edit × 5 | ~4000 | 25s |
| **С Serena** | find_symbol + find_referencing + rename_symbol | ~500 | 5s |
| **Экономия** | — | **87%** | **80%** |

### Сценарий 3: Добавление нового класса

| Подход | Операции | Токены | Время |
|--------|----------|--------|-------|
| **Без Serena** | Read + Find location + Edit | ~2200 | 12s |
| **С Serena** | get_symbols_overview + insert_after_symbol | ~300 | 3s |
| **Экономия** | — | **86%** | **75%** |

---

## 🚨 Troubleshooting

### Проблема: "Symbol not found"
**Решение:**
```python
# 1. Проверить правильность пути
get_symbols_overview("src/file.py")  # Увидеть доступные символы

# 2. Использовать substring matching
find_symbol("partial_name", substring_matching=True)

# 3. Использовать search_for_pattern как fallback
search_for_pattern(r"class TargetClass", paths_include_glob="src/**/*.py")
```

### Проблема: "First call is very slow"
**Решение:**
```bash
# Индексировать проект перед использованием
serena project index
```

### Проблема: "Too many results"
**Решение:**
```python
# 1. Уточнить relative_path
find_symbol("method", relative_path="src/specific_dir")

# 2. Использовать фильтры по типам
find_symbol("name", include_kinds=[5])  # Только классы

# 3. Использовать абсолютный путь
find_symbol("/TopLevelClass/method")  # Только топ-уровень
```

---

## 📖 Дополнительные ресурсы

### Официальная документация
- GitHub: https://github.com/oraios/serena
- MCP Servers Hub: https://lobehub.com/mcp/oraios-serena

### Типы символов LSP (для include_kinds/exclude_kinds)
```
1=File, 2=Module, 3=Namespace, 4=Package
5=Class, 6=Method, 7=Property, 8=Field
9=Constructor, 10=Enum, 11=Interface
12=Function, 13=Variable, 14=Constant
15=String, 16=Number, 17=Boolean, 18=Array
```

### Индексация проекта
```bash
# Из терминала
serena project index

# Проверить статус
serena project status
```

---

## ✅ Checklist для работы с Serena

**Перед началом работы:**
- [ ] `check_onboarding_performed()` - проект инициализирован?
- [ ] `list_memories()` - какие знания уже есть?
- [ ] `get_current_config()` - правильная конфигурация?

**При изучении кода:**
- [ ] `get_symbols_overview()` - структура файла
- [ ] `find_symbol()` - конкретные символы
- [ ] `find_referencing_symbols()` - зависимости
- [ ] `think_about_collected_information` - достаточно данных?

**При изменении кода:**
- [ ] `find_referencing_symbols()` - кто использует?
- [ ] `think_about_task_adherence` - правильное направление?
- [ ] `replace_symbol_body()` / `insert_*()` - изменения
- [ ] Тесты пройдены?
- [ ] `think_about_whether_you_are_done` - всё готово?

**После завершения:**
- [ ] `write_memory()` - сохранить знания
- [ ] Код закоммичен
- [ ] Документация обновлена

---

**Последнее обновление:** 2025-01-30
**Версия:** 1.0
**Проект:** CompetitorMonitor RU
