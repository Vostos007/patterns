"""
Context-Aware Chunker - умное разбиение с сохранением контекста для RAG.

Проблема с простым chunking:
- Фиксированный размер → теряется контекст на границах
- Без overlap → важная информация может оказаться разорванной
- Без учёта структуры → разрыв посередине важной мысли

Решение:
- Overlap между чанками (10-20%) для сохранения контекста
- Динамический размер в зависимости от типа контента
- Разрыв только на границах смысловых единиц
- Сохранение иерархии и связей между чанками
- Метаданные для восстановления полного контекста
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import re
from enum import Enum


class ChunkingStrategy(Enum):
    """Стратегия разбиения на чанки."""

    SEMANTIC = "semantic"  # По смысловым границам (параграфы, предложения)
    FIXED_SIZE = "fixed"  # Фиксированный размер с overlap
    SLIDING_WINDOW = "sliding"  # Скользящее окно
    HIERARCHICAL = "hierarchical"  # Иерархическое (абзац → предложения)


@dataclass
class ChunkMetadata:
    """Метаданные чанка для восстановления контекста."""

    chunk_id: int  # ID чанка
    source_id: str  # ID источника (документ, секция)
    position: int  # Позиция в источнике
    total_chunks: int  # Всего чанков в источнике

    # Контекст
    prev_chunk_id: Optional[int] = None  # Предыдущий чанк
    next_chunk_id: Optional[int] = None  # Следующий чанк
    parent_chunk_id: Optional[int] = None  # Родительский (для hierarchical)
    level: int = 0  # Уровень иерархии (0=top, 1=section, 2=paragraph)

    # Для восстановления контекста
    overlap_with_prev: int = 0  # Символов overlap с предыдущим
    overlap_with_next: int = 0  # Символов overlap со следующим


@dataclass
class Chunk:
    """Чанк текста с метаданными."""

    text: str  # Основной текст чанка
    metadata: ChunkMetadata  # Метаданные

    # Контекстная информация
    prefix_context: str = ""  # Контекст перед чанком (из overlap)
    suffix_context: str = ""  # Контекст после чанка (из overlap)

    def get_full_context(self) -> str:
        """Получить полный текст с контекстом."""
        return f"{self.prefix_context}{self.text}{self.suffix_context}".strip()

    def get_size(self) -> int:
        """Размер чанка в символах."""
        return len(self.text)

    def get_size_with_context(self) -> int:
        """Размер с учётом контекста."""
        return len(self.get_full_context())


class ContextAwareChunker:
    """
    Умное разбиение текста на чанки с сохранением контекста.

    Features:
    - Overlap между чанками для сохранения контекста
    - Разрыв только на границах предложений/абзацев
    - Динамический размер в зависимости от контента
    - Сохранение иерархии (документ → секция → параграф)
    - Метаданные для восстановления контекста

    Example:
        >>> chunker = ContextAwareChunker(
        ...     chunk_size=1000,
        ...     overlap_size=200,
        ...     strategy=ChunkingStrategy.SEMANTIC
        ... )
        >>> chunks = chunker.chunk(text, source_id="doc1")
        >>> # Chunks имеют overlap и связи между собой
    """

    def __init__(
        self,
        chunk_size: int = 1000,  # Базовый размер чанка (символов)
        overlap_size: int = 200,  # Размер overlap (символов)
        min_chunk_size: int = 100,  # Минимальный размер
        max_chunk_size: int = 2000,  # Максимальный размер
        strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC,
        preserve_sentences: bool = True,  # Не разрывать предложения
        preserve_paragraphs: bool = False,  # Не разрывать абзацы (если возможно)
    ):
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.strategy = strategy
        self.preserve_sentences = preserve_sentences
        self.preserve_paragraphs = preserve_paragraphs

        # Валидация
        assert overlap_size < chunk_size, "Overlap должен быть меньше chunk_size"
        assert (
            min_chunk_size <= chunk_size <= max_chunk_size
        ), "Invalid chunk size range"

    def chunk(self, text: str, source_id: str = "unknown") -> List[Chunk]:
        """
        Разбить текст на чанки с учётом контекста.

        Args:
            text: Текст для разбиения
            source_id: ID источника (для метаданных)

        Returns:
            Список чанков с метаданными и контекстом
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            return []

        # Выбрать стратегию
        if self.strategy == ChunkingStrategy.SEMANTIC:
            chunks = self._chunk_semantic(text, source_id)
        elif self.strategy == ChunkingStrategy.FIXED_SIZE:
            chunks = self._chunk_fixed_size(text, source_id)
        elif self.strategy == ChunkingStrategy.SLIDING_WINDOW:
            chunks = self._chunk_sliding_window(text, source_id)
        elif self.strategy == ChunkingStrategy.HIERARCHICAL:
            chunks = self._chunk_hierarchical(text, source_id)
        else:
            chunks = self._chunk_semantic(text, source_id)

        # Добавить overlap контекст
        chunks = self._add_overlap_context(chunks)

        # Связать чанки (prev/next)
        chunks = self._link_chunks(chunks)

        return chunks

    def _chunk_semantic(self, text: str, source_id: str) -> List[Chunk]:
        """
        Семантическое разбиение по смысловым границам.

        Приоритеты:
        1. Абзацы (если preserve_paragraphs)
        2. Предложения (если preserve_sentences)
        3. Слова
        """
        chunks = []

        # Разбить на абзацы
        paragraphs = re.split(r"\n\s*\n", text)

        current_chunk_text = ""
        current_position = 0
        chunk_id = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Проверить, влезает ли абзац целиком
            if (
                self.preserve_paragraphs
                and len(current_chunk_text) + len(para) <= self.max_chunk_size
            ):
                # Добавить к текущему чанку
                if current_chunk_text:
                    current_chunk_text += "\n\n"
                current_chunk_text += para

            elif len(current_chunk_text) + len(para) <= self.chunk_size:
                # Влезает в текущий чанк
                if current_chunk_text:
                    current_chunk_text += "\n\n"
                current_chunk_text += para

            else:
                # Не влезает - сохранить текущий чанк
                if current_chunk_text:
                    chunk = self._create_chunk(
                        current_chunk_text, chunk_id, source_id, current_position
                    )
                    chunks.append(chunk)
                    current_position += len(current_chunk_text)
                    chunk_id += 1

                # Разбить абзац на предложения если нужно
                if len(para) > self.max_chunk_size:
                    para_chunks = self._split_by_sentences(
                        para, chunk_id, source_id, current_position
                    )
                    chunks.extend(para_chunks)
                    chunk_id += len(para_chunks)
                    current_position += len(para)
                    current_chunk_text = ""
                else:
                    current_chunk_text = para

        # Сохранить последний чанк
        if current_chunk_text:
            chunk = self._create_chunk(
                current_chunk_text, chunk_id, source_id, current_position
            )
            chunks.append(chunk)

        return chunks

    def _split_by_sentences(
        self, text: str, start_chunk_id: int, source_id: str, start_position: int
    ) -> List[Chunk]:
        """Разбить длинный текст по предложениям."""
        chunks = []

        # Разбить на предложения
        sentences = re.split(r"([.!?]\s+)", text)

        current_chunk_text = ""
        chunk_id = start_chunk_id
        position = start_position

        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            separator = sentences[i + 1] if i + 1 < len(sentences) else ""
            sentence_full = sentence + separator

            if len(current_chunk_text) + len(sentence_full) <= self.chunk_size:
                current_chunk_text += sentence_full
            else:
                # Сохранить текущий чанк
                if current_chunk_text:
                    chunk = self._create_chunk(
                        current_chunk_text, chunk_id, source_id, position
                    )
                    chunks.append(chunk)
                    position += len(current_chunk_text)
                    chunk_id += 1

                current_chunk_text = sentence_full

        # Сохранить последний чанк
        if current_chunk_text:
            chunk = self._create_chunk(current_chunk_text, chunk_id, source_id, position)
            chunks.append(chunk)

        return chunks

    def _chunk_fixed_size(self, text: str, source_id: str) -> List[Chunk]:
        """Фиксированный размер с overlap."""
        chunks = []
        chunk_id = 0
        position = 0

        # Разбить на предложения для умного разрыва
        sentences = re.split(r"([.!?]\s+)", text)
        sentence_list = []
        for i in range(0, len(sentences), 2):
            s = sentences[i]
            sep = sentences[i + 1] if i + 1 < len(sentences) else ""
            sentence_list.append(s + sep)

        current_text = ""
        i = 0

        while i < len(sentence_list):
            # Набрать chunk_size
            while i < len(sentence_list) and len(current_text) < self.chunk_size:
                current_text += sentence_list[i]
                i += 1

            if current_text:
                chunk = self._create_chunk(current_text, chunk_id, source_id, position)
                chunks.append(chunk)
                position += len(current_text) - self.overlap_size
                chunk_id += 1

                # Откатиться назад на overlap
                overlap_chars = self.overlap_size
                current_text = current_text[-overlap_chars:] if overlap_chars > 0 else ""
                # Откатить индекс предложений
                chars_counted = 0
                sentences_back = 0
                while chars_counted < overlap_chars and i - sentences_back - 1 >= 0:
                    sentences_back += 1
                    chars_counted += len(sentence_list[i - sentences_back])
                i -= sentences_back

        return chunks

    def _chunk_sliding_window(self, text: str, source_id: str) -> List[Chunk]:
        """Скользящее окно фиксированного размера."""
        chunks = []
        chunk_id = 0

        step = self.chunk_size - self.overlap_size
        position = 0

        while position < len(text):
            end = min(position + self.chunk_size, len(text))
            chunk_text = text[position:end]

            # Выровнять по границе предложения если нужно
            if self.preserve_sentences and end < len(text):
                # Найти конец предложения
                match = re.search(r"[.!?]\s", chunk_text[::-1])
                if match:
                    # Обрезать до конца предложения
                    cut_pos = len(chunk_text) - match.start()
                    chunk_text = chunk_text[:cut_pos]

            if len(chunk_text.strip()) >= self.min_chunk_size:
                chunk = self._create_chunk(chunk_text, chunk_id, source_id, position)
                chunks.append(chunk)
                chunk_id += 1

            position += step

        return chunks

    def _chunk_hierarchical(self, text: str, source_id: str) -> List[Chunk]:
        """
        Иерархическое разбиение.

        Level 0: Весь текст (parent chunk)
        Level 1: Абзацы
        Level 2: Предложения (если абзац слишком длинный)
        """
        chunks = []
        chunk_id = 0

        # Level 0: Parent chunk (если текст не слишком длинный)
        if len(text) <= self.max_chunk_size:
            parent_chunk = self._create_chunk(text, chunk_id, source_id, 0, level=0)
            chunks.append(parent_chunk)
            chunk_id += 1
            return chunks

        # Level 1: Абзацы
        paragraphs = re.split(r"\n\s*\n", text)
        parent_id = None

        for para in paragraphs:
            para = para.strip()
            if not para or len(para) < self.min_chunk_size:
                continue

            if len(para) <= self.max_chunk_size:
                # Абзац как один чанк
                chunk = self._create_chunk(
                    para, chunk_id, source_id, 0, level=1, parent_id=parent_id
                )
                chunks.append(chunk)
                chunk_id += 1
            else:
                # Level 2: Разбить абзац на предложения
                para_chunks = self._split_by_sentences(para, chunk_id, source_id, 0)
                for pc in para_chunks:
                    pc.metadata.level = 2
                    pc.metadata.parent_chunk_id = parent_id
                chunks.extend(para_chunks)
                chunk_id += len(para_chunks)

        return chunks

    def _create_chunk(
        self,
        text: str,
        chunk_id: int,
        source_id: str,
        position: int,
        level: int = 0,
        parent_id: Optional[int] = None,
    ) -> Chunk:
        """Создать чанк с метаданными."""
        metadata = ChunkMetadata(
            chunk_id=chunk_id,
            source_id=source_id,
            position=position,
            total_chunks=0,  # Будет обновлено позже
            level=level,
            parent_chunk_id=parent_id,
        )

        return Chunk(text=text.strip(), metadata=metadata)

    def _add_overlap_context(self, chunks: List[Chunk]) -> List[Chunk]:
        """Добавить overlap контекст к чанкам."""
        for i, chunk in enumerate(chunks):
            # Предыдущий контекст
            if i > 0:
                prev_chunk = chunks[i - 1]
                # Взять последние overlap_size символов предыдущего чанка
                overlap_text = prev_chunk.text[-self.overlap_size :]
                # Обрезать до начала предложения для читаемости
                if self.preserve_sentences:
                    match = re.search(r"[.!?]\s+", overlap_text)
                    if match:
                        overlap_text = overlap_text[match.end() :]
                chunk.prefix_context = overlap_text
                chunk.metadata.overlap_with_prev = len(overlap_text)

            # Следующий контекст
            if i < len(chunks) - 1:
                next_chunk = chunks[i + 1]
                # Взять первые overlap_size символов следующего чанка
                overlap_text = next_chunk.text[: self.overlap_size]
                # Обрезать до конца предложения
                if self.preserve_sentences:
                    match = re.search(r"[.!?]\s", overlap_text)
                    if match:
                        overlap_text = overlap_text[: match.end()]
                chunk.suffix_context = overlap_text
                chunk.metadata.overlap_with_next = len(overlap_text)

        return chunks

    def _link_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """Связать чанки (prev/next references)."""
        total = len(chunks)

        for i, chunk in enumerate(chunks):
            chunk.metadata.total_chunks = total

            if i > 0:
                chunk.metadata.prev_chunk_id = chunks[i - 1].metadata.chunk_id

            if i < total - 1:
                chunk.metadata.next_chunk_id = chunks[i + 1].metadata.chunk_id

        return chunks

    def get_chunk_with_neighbors(
        self, chunks: List[Chunk], chunk_id: int, context_window: int = 1
    ) -> str:
        """
        Получить чанк с соседними чанками для расширенного контекста.

        Args:
            chunks: Список всех чанков
            chunk_id: ID целевого чанка
            context_window: Сколько чанков брать слева и справа

        Returns:
            Текст с расширенным контекстом
        """
        # Найти чанк
        target_idx = None
        for i, chunk in enumerate(chunks):
            if chunk.metadata.chunk_id == chunk_id:
                target_idx = i
                break

        if target_idx is None:
            return ""

        # Взять соседние чанки
        start_idx = max(0, target_idx - context_window)
        end_idx = min(len(chunks), target_idx + context_window + 1)

        context_chunks = chunks[start_idx:end_idx]
        texts = [c.text for c in context_chunks]

        return "\n\n".join(texts)


def estimate_optimal_chunk_size(
    model_context_window: int = 4096,  # Размер контекстного окна модели (токенов)
    num_chunks_in_prompt: int = 5,  # Сколько чанков добавляется в промпт
    prompt_overhead: int = 500,  # Токены на системный промпт
    chars_per_token: float = 4.0,  # Примерно символов на токен
) -> int:
    """
    Оценить оптимальный размер чанка для RAG.

    Args:
        model_context_window: Размер контекстного окна модели (токенов)
        num_chunks_in_prompt: Сколько чанков используется в RAG
        prompt_overhead: Токены на промпт, инструкции
        chars_per_token: Соотношение символы/токены (~4 для английского, ~2 для русского)

    Returns:
        Рекомендуемый размер чанка в символах
    """
    # Доступные токены для чанков
    available_tokens = model_context_window - prompt_overhead

    # Токены на один чанк
    tokens_per_chunk = available_tokens // num_chunks_in_prompt

    # Конвертировать в символы
    chunk_size_chars = int(tokens_per_chunk * chars_per_token)

    return chunk_size_chars


# Предустановки для разных моделей
CHUNK_SIZE_PRESETS = {
    "gpt-3.5": {
        "context_window": 4096,
        "recommended_chunk_size": 800,  # символов
        "overlap": 150,
    },
    "gpt-4": {
        "context_window": 8192,
        "recommended_chunk_size": 1200,
        "overlap": 200,
    },
    "claude-2": {
        "context_window": 100000,
        "recommended_chunk_size": 2000,
        "overlap": 300,
    },
    "claude-3": {
        "context_window": 200000,
        "recommended_chunk_size": 3000,
        "overlap": 400,
    },
}
