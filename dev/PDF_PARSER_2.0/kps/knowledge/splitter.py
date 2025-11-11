"""
Document Splitter - умное разбиение документов на секции.

Один документ (книга, инструкция) может содержать разные разделы:
- Узоры (PATTERN)
- Техники (TECHNIQUE)
- Описание пряжи (YARN)
- Инструменты (TOOL)
- Готовые проекты (PROJECT)

Система автоматически:
1. Определяет структуру документа (заголовки, главы)
2. Разбивает на смысловые секции
3. Категоризирует каждую секцию отдельно
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

from .base import KnowledgeCategory


@dataclass
class DocumentSection:
    """Секция документа с метаданными."""

    title: str  # Заголовок секции
    content: str  # Содержимое
    level: int  # Уровень вложенности (1=глава, 2=подглава, 3=секция)
    start_pos: int  # Позиция начала в документе
    end_pos: int  # Позиция конца
    parent_title: Optional[str] = None  # Родительская секция
    metadata: Optional[Dict[str, Any]] = None  # Доп. метаданные

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SplitStrategy(Enum):
    """Стратегия разбиения документа."""

    AUTO = "auto"  # Автоматический выбор
    MARKDOWN = "markdown"  # По markdown заголовкам (# ## ###)
    CHAPTERS = "chapters"  # По главам ("Глава 1", "Chapter 1")
    HEADINGS = "headings"  # По любым заголовкам (жирный текст, заглавные буквы)
    PARAGRAPHS = "paragraphs"  # По абзацам (для коротких документов)
    FIXED_SIZE = "fixed_size"  # По фиксированному размеру (chunk_size символов)


class DocumentSplitter:
    """
    Умное разбиение документов на секции.

    Example:
        >>> splitter = DocumentSplitter()
        >>> sections = splitter.split(text, strategy=SplitStrategy.AUTO)
        >>> for section in sections:
        ...     print(f"{section.title}: {len(section.content)} chars")
    """

    def __init__(
        self,
        min_section_length: int = 100,  # Минимальная длина секции
        max_section_length: int = 10000,  # Максимальная длина секции
        chunk_size: int = 2000,  # Размер для FIXED_SIZE
    ):
        self.min_section_length = min_section_length
        self.max_section_length = max_section_length
        self.chunk_size = chunk_size

    def split(
        self,
        text: str,
        strategy: SplitStrategy = SplitStrategy.AUTO,
        filename: Optional[str] = None,
    ) -> List[DocumentSection]:
        """
        Разбить документ на секции.

        Args:
            text: Текст документа
            strategy: Стратегия разбиения
            filename: Имя файла (для определения формата)

        Returns:
            Список секций документа
        """
        if not text or len(text.strip()) < self.min_section_length:
            # Слишком короткий документ - вернуть как одну секцию
            return [
                DocumentSection(
                    title=filename or "Document",
                    content=text.strip(),
                    level=1,
                    start_pos=0,
                    end_pos=len(text),
                )
            ]

        # Автоматический выбор стратегии
        if strategy == SplitStrategy.AUTO:
            strategy = self._detect_strategy(text, filename)

        # Применить стратегию
        if strategy == SplitStrategy.MARKDOWN:
            sections = self._split_markdown(text)
        elif strategy == SplitStrategy.CHAPTERS:
            sections = self._split_chapters(text)
        elif strategy == SplitStrategy.HEADINGS:
            sections = self._split_headings(text)
        elif strategy == SplitStrategy.PARAGRAPHS:
            sections = self._split_paragraphs(text)
        elif strategy == SplitStrategy.FIXED_SIZE:
            sections = self._split_fixed_size(text)
        else:
            # Fallback - весь документ как одна секция
            sections = [
                DocumentSection(
                    title=filename or "Document",
                    content=text.strip(),
                    level=1,
                    start_pos=0,
                    end_pos=len(text),
                )
            ]

        # Фильтр: удалить слишком короткие секции
        sections = [s for s in sections if len(s.content.strip()) >= self.min_section_length]

        # Разбить слишком длинные секции
        sections = self._split_long_sections(sections)

        # Добавить связи между родительскими и дочерними секциями
        sections = self._link_parent_sections(sections)

        return sections

    def _detect_strategy(self, text: str, filename: Optional[str]) -> SplitStrategy:
        """Автоматически определить стратегию разбиения."""
        # Проверить markdown заголовки
        if re.search(r"^#{1,6}\s+.+$", text, re.MULTILINE):
            return SplitStrategy.MARKDOWN

        # Проверить наличие глав
        chapter_patterns = [
            r"^Глава\s+\d+",
            r"^ГЛАВА\s+\d+",
            r"^Chapter\s+\d+",
            r"^CHAPTER\s+\d+",
            r"^Раздел\s+\d+",
            r"^Section\s+\d+",
        ]
        for pattern in chapter_patterns:
            if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
                return SplitStrategy.CHAPTERS

        # Проверить наличие заголовков (заглавные буквы, отдельная строка)
        if re.search(r"^[А-ЯA-Z][А-ЯA-Z\s]{5,}$", text, re.MULTILINE):
            return SplitStrategy.HEADINGS

        # Для коротких документов - по абзацам
        if len(text) < 3000:
            return SplitStrategy.PARAGRAPHS

        # Для длинных без структуры - фиксированный размер
        return SplitStrategy.FIXED_SIZE

    def _split_markdown(self, text: str) -> List[DocumentSection]:
        """Разбить по markdown заголовкам (# ## ###)."""
        sections = []
        lines = text.split("\n")

        current_section = None
        current_content = []
        current_level = 0
        start_pos = 0

        for i, line in enumerate(lines):
            # Проверить на markdown заголовок
            match = re.match(r"^(#{1,6})\s+(.+)$", line)

            if match:
                # Сохранить предыдущую секцию
                if current_section:
                    content = "\n".join(current_content).strip()
                    sections.append(
                        DocumentSection(
                            title=current_section,
                            content=content,
                            level=current_level,
                            start_pos=start_pos,
                            end_pos=start_pos + len(content),
                        )
                    )

                # Начать новую секцию
                level = len(match.group(1))  # Количество #
                title = match.group(2).strip()

                current_section = title
                current_level = level
                current_content = []
                start_pos = sum(len(l) + 1 for l in lines[:i])
            else:
                # Добавить к текущей секции
                current_content.append(line)

        # Сохранить последнюю секцию
        if current_section:
            content = "\n".join(current_content).strip()
            sections.append(
                DocumentSection(
                    title=current_section,
                    content=content,
                    level=current_level,
                    start_pos=start_pos,
                    end_pos=start_pos + len(content),
                )
            )

        return sections

    def _split_chapters(self, text: str) -> List[DocumentSection]:
        """Разбить по главам."""
        sections = []

        # Паттерны для поиска глав
        chapter_patterns = [
            r"^(Глава\s+\d+[:.]\s*)(.+)$",
            r"^(ГЛАВА\s+\d+[:.]\s*)(.+)$",
            r"^(Chapter\s+\d+[:.]\s*)(.+)$",
            r"^(CHAPTER\s+\d+[:.]\s*)(.+)$",
            r"^(Раздел\s+\d+[:.]\s*)(.+)$",
            r"^(Section\s+\d+[:.]\s*)(.+)$",
        ]

        # Объединить все паттерны
        combined_pattern = "|".join(f"({p})" for p in chapter_patterns)

        # Найти все главы
        lines = text.split("\n")
        chapter_positions = []

        for i, line in enumerate(lines):
            for pattern in chapter_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    title = line.strip()
                    pos = sum(len(l) + 1 for l in lines[:i])
                    chapter_positions.append((i, title, pos))
                    break

        # Разбить текст по главам
        for idx, (line_num, title, start_pos) in enumerate(chapter_positions):
            # Определить конец главы
            if idx + 1 < len(chapter_positions):
                end_line = chapter_positions[idx + 1][0]
            else:
                end_line = len(lines)

            # Извлечь содержимое главы
            content_lines = lines[line_num + 1 : end_line]
            content = "\n".join(content_lines).strip()

            if content:
                sections.append(
                    DocumentSection(
                        title=title,
                        content=content,
                        level=1,
                        start_pos=start_pos,
                        end_pos=start_pos + len(content),
                    )
                )

        return sections

    def _split_headings(self, text: str) -> List[DocumentSection]:
        """Разбить по заголовкам (заглавные буквы, отдельная строка)."""
        sections = []
        lines = text.split("\n")

        current_section = None
        current_content = []
        start_pos = 0

        for i, line in enumerate(lines):
            # Проверить на заголовок (заглавные буквы, минимум 5 символов)
            if re.match(r"^[А-ЯA-Z][А-ЯA-Z\s]{5,}$", line.strip()):
                # Сохранить предыдущую секцию
                if current_section and current_content:
                    content = "\n".join(current_content).strip()
                    sections.append(
                        DocumentSection(
                            title=current_section,
                            content=content,
                            level=1,
                            start_pos=start_pos,
                            end_pos=start_pos + len(content),
                        )
                    )

                # Начать новую секцию
                current_section = line.strip()
                current_content = []
                start_pos = sum(len(l) + 1 for l in lines[:i])
            else:
                current_content.append(line)

        # Сохранить последнюю секцию
        if current_section and current_content:
            content = "\n".join(current_content).strip()
            sections.append(
                DocumentSection(
                    title=current_section,
                    content=content,
                    level=1,
                    start_pos=start_pos,
                    end_pos=start_pos + len(content),
                )
            )

        return sections

    def _split_paragraphs(self, text: str) -> List[DocumentSection]:
        """Разбить по абзацам (для коротких документов)."""
        sections = []
        paragraphs = re.split(r"\n\s*\n", text)

        pos = 0
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if len(para) >= self.min_section_length:
                # Использовать первую строку как заголовок
                lines = para.split("\n")
                title = lines[0][:50] + ("..." if len(lines[0]) > 50 else "")

                sections.append(
                    DocumentSection(
                        title=f"Paragraph {i + 1}: {title}",
                        content=para,
                        level=1,
                        start_pos=pos,
                        end_pos=pos + len(para),
                    )
                )

            pos += len(para) + 2  # +2 for \n\n

        return sections

    def _split_fixed_size(self, text: str) -> List[DocumentSection]:
        """Разбить по фиксированному размеру."""
        sections = []
        chunk_size = self.chunk_size

        # Разбить на предложения для умного разделения
        sentences = re.split(r"([.!?]\s+)", text)

        current_chunk = []
        current_length = 0
        chunk_num = 1
        start_pos = 0

        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            separator = sentences[i + 1] if i + 1 < len(sentences) else ""

            sentence_full = sentence + separator
            sentence_len = len(sentence_full)

            if current_length + sentence_len > chunk_size and current_chunk:
                # Сохранить текущий chunk
                content = "".join(current_chunk).strip()
                title = f"Section {chunk_num}"

                # Попробовать найти первое предложение как заголовок
                first_sentence = current_chunk[0][:50]
                if first_sentence:
                    title = f"Section {chunk_num}: {first_sentence}..."

                sections.append(
                    DocumentSection(
                        title=title,
                        content=content,
                        level=1,
                        start_pos=start_pos,
                        end_pos=start_pos + len(content),
                    )
                )

                # Начать новый chunk
                current_chunk = [sentence_full]
                current_length = sentence_len
                start_pos += len(content)
                chunk_num += 1
            else:
                current_chunk.append(sentence_full)
                current_length += sentence_len

        # Сохранить последний chunk
        if current_chunk:
            content = "".join(current_chunk).strip()
            first_sentence = current_chunk[0][:50]
            title = f"Section {chunk_num}: {first_sentence}..."

            sections.append(
                DocumentSection(
                    title=title,
                    content=content,
                    level=1,
                    start_pos=start_pos,
                    end_pos=start_pos + len(content),
                )
            )

        return sections

    def _split_long_sections(self, sections: List[DocumentSection]) -> List[DocumentSection]:
        """Разбить слишком длинные секции."""
        result = []

        for section in sections:
            if len(section.content) <= self.max_section_length:
                result.append(section)
            else:
                # Разбить длинную секцию на части
                subsections = self._split_fixed_size(section.content)

                for i, subsection in enumerate(subsections):
                    # Сохранить связь с родительской секцией
                    subsection.parent_title = section.title
                    subsection.level = section.level + 1
                    subsection.title = f"{section.title} - Part {i + 1}"
                    result.append(subsection)

        return result

    def _link_parent_sections(self, sections: List[DocumentSection]) -> List[DocumentSection]:
        """Добавить связи между родительскими и дочерними секциями."""
        # Создать карту: level -> последняя секция этого уровня
        level_map = {}

        for section in sections:
            # Найти родителя (секция с меньшим level)
            if section.level > 1 and not section.parent_title:
                for parent_level in range(section.level - 1, 0, -1):
                    if parent_level in level_map:
                        section.parent_title = level_map[parent_level].title
                        break

            # Обновить карту
            level_map[section.level] = section

        return sections


def categorize_section(section: DocumentSection) -> KnowledgeCategory:
    """
    Определить категорию секции на основе заголовка и содержимого.

    Args:
        section: Секция документа

    Returns:
        Категория знаний
    """
    text = (section.title + " " + section.content[:500]).lower()

    # Паттерны для каждой категории
    category_patterns = {
        KnowledgeCategory.PATTERN: [
            "узор",
            "схема",
            "pattern",
            "chart",
            "мотив",
            "косы",
            "коса",
            "ажур",
            "жаккард",
            "араны",
            "cable",
            "lace",
            "colorwork",
        ],
        KnowledgeCategory.TECHNIQUE: [
            "техник",
            "метод",
            "способ",
            "technique",
            "method",
            "вязание",
            "knitting",
            "прибавлен",
            "убавлен",
            "закрыт",
            "набор",
            "casting",
            "bind",
            "increase",
            "decrease",
        ],
        KnowledgeCategory.YARN: [
            "пряж",
            "нит",
            "yarn",
            "thread",
            "мохер",
            "шерст",
            "хлопок",
            "акрил",
            "mohair",
            "wool",
            "cotton",
            "fiber",
            "волокн",
        ],
        KnowledgeCategory.TOOL: [
            "спиц",
            "крючок",
            "инструмент",
            "needle",
            "hook",
            "tool",
            "круговые",
            "чулочные",
            "маркер",
            "circular",
            "dpn",
            "marker",
        ],
        KnowledgeCategory.MATERIAL: [
            "материал",
            "состав",
            "material",
            "composition",
            "натуральн",
            "синтетич",
            "natural",
            "synthetic",
        ],
        KnowledgeCategory.PROJECT: [
            "шарф",
            "свитер",
            "шапк",
            "носк",
            "варежк",
            "изделие",
            "project",
            "scarf",
            "sweater",
            "hat",
            "sock",
            "mitten",
            "описание вязания",
        ],
        KnowledgeCategory.STITCH: [
            "петл",
            "stitch",
            "лицев",
            "изнаночн",
            "knit",
            "purl",
            "k2tog",
            "ssk",
            "вместе",
            "накид",
        ],
    }

    # Подсчитать совпадения для каждой категории
    scores = {}
    for category, patterns in category_patterns.items():
        score = sum(1 for pattern in patterns if pattern in text)
        scores[category] = score

    # Выбрать категорию с максимальным score
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)

    # По умолчанию - GENERAL
    return KnowledgeCategory.GENERAL
