"""
Pattern Generator - генерация описаний изделий на основе базы знаний.

Использует накопленные знания для создания правильных и детальных
описаний вязаных изделий.

Функции:
- Генерация описания изделия по параметрам
- Подбор подходящей пряжи
- Рекомендации по инструментам
- Выбор техник и узоров
- Проверка совместимости компонентов
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from .base import KnowledgeBase, KnowledgeCategory, KnowledgeEntry

logger = logging.getLogger(__name__)


@dataclass
class ProjectRequirements:
    """Требования к изделию."""

    project_type: str  # "шарф", "свитер", "шапка"
    yarn_type: Optional[str] = None  # "мохер", "шерсть"
    technique: Optional[str] = None  # "ажурное вязание", "косы"
    size: Optional[str] = None  # "S", "M", "L"
    skill_level: Optional[str] = None  # "beginner", "intermediate", "advanced"
    language: str = "ru"


@dataclass
class ProjectDescription:
    """Сгенерированное описание изделия."""

    title: str
    description: str
    materials: Dict[str, str]  # yarn, needles, etc.
    techniques: List[str]
    patterns: List[str]
    instructions: str
    estimated_time: str
    skill_level: str
    sources: List[str]  # Источники из базы знаний


class PatternGenerator:
    """
    Генератор описаний изделий на основе базы знаний.

    Использует RAG для поиска релевантной информации и составления
    корректных описаний.

    Example:
        >>> kb = KnowledgeBase("data/knowledge.db")
        >>> generator = PatternGenerator(kb)
        >>>
        >>> # Требования
        >>> req = ProjectRequirements(
        ...     project_type="шарф",
        ...     yarn_type="мохер",
        ...     technique="ажурное вязание"
        ... )
        >>>
        >>> # Сгенерировать описание
        >>> description = generator.generate(req)
        >>> print(description.title)
        >>> print(description.instructions)
    """

    def __init__(self, knowledge_base: KnowledgeBase):
        """
        Инициализация генератора.

        Args:
            knowledge_base: База знаний о вязании
        """
        self.kb = knowledge_base

    def generate(self, requirements: ProjectRequirements) -> ProjectDescription:
        """
        Сгенерировать описание изделия.

        Args:
            requirements: Требования к изделию

        Returns:
            Полное описание изделия с инструкциями
        """
        logger.info(f"Generating pattern for: {requirements.project_type}")

        # 1. Найти похожие изделия
        similar_projects = self._find_similar_projects(requirements)

        # 2. Подобрать материалы
        materials = self._select_materials(requirements, similar_projects)

        # 3. Выбрать техники
        techniques = self._select_techniques(requirements, similar_projects)

        # 4. Выбрать узоры
        patterns = self._select_patterns(requirements, similar_projects)

        # 5. Сгенерировать инструкции
        instructions = self._generate_instructions(
            requirements, materials, techniques, patterns, similar_projects
        )

        # 6. Оценить время и уровень
        estimated_time = self._estimate_time(requirements, techniques)
        skill_level = self._determine_skill_level(techniques, patterns)

        # 7. Создать заголовок и описание
        title = self._create_title(requirements)
        description = self._create_description(requirements, materials, techniques)

        # Источники
        sources = [p.source_file for p in similar_projects if p.source_file]

        return ProjectDescription(
            title=title,
            description=description,
            materials=materials,
            techniques=[t.title for t in techniques],
            patterns=[p.title for p in patterns],
            instructions=instructions,
            estimated_time=estimated_time,
            skill_level=skill_level,
            sources=list(set(sources)),
        )

    def _find_similar_projects(
        self, req: ProjectRequirements
    ) -> List[KnowledgeEntry]:
        """Найти похожие изделия в базе знаний."""
        query = f"{req.project_type}"
        if req.yarn_type:
            query += f" {req.yarn_type}"
        if req.technique:
            query += f" {req.technique}"

        return self.kb.search(
            query,
            category=KnowledgeCategory.PROJECT,
            language=req.language,
            limit=5,
        )

    def _select_materials(
        self, req: ProjectRequirements, similar: List[KnowledgeEntry]
    ) -> Dict[str, str]:
        """Подобрать материалы."""
        materials = {}

        # Пряжа
        if req.yarn_type:
            yarn_query = req.yarn_type
        else:
            # Взять из похожих проектов
            yarn_query = req.project_type

        yarn_results = self.kb.search(
            yarn_query, category=KnowledgeCategory.YARN, language=req.language, limit=1
        )

        if yarn_results:
            materials["yarn"] = yarn_results[0].title
            materials["yarn_details"] = yarn_results[0].content[:200]

        # Инструменты
        tool_query = req.project_type
        tool_results = self.kb.search(
            tool_query, category=KnowledgeCategory.TOOL, language=req.language, limit=1
        )

        if tool_results:
            materials["needles"] = tool_results[0].title

        return materials

    def _select_techniques(
        self, req: ProjectRequirements, similar: List[KnowledgeEntry]
    ) -> List[KnowledgeEntry]:
        """Выбрать техники."""
        if req.technique:
            query = req.technique
        else:
            query = req.project_type

        return self.kb.search(
            query,
            category=KnowledgeCategory.TECHNIQUE,
            language=req.language,
            limit=3,
        )

    def _select_patterns(
        self, req: ProjectRequirements, similar: List[KnowledgeEntry]
    ) -> List[KnowledgeEntry]:
        """Выбрать узоры."""
        query = req.project_type
        if req.yarn_type:
            query += f" {req.yarn_type}"

        return self.kb.search(
            query,
            category=KnowledgeCategory.PATTERN,
            language=req.language,
            limit=2,
        )

    def _generate_instructions(
        self,
        req: ProjectRequirements,
        materials: Dict,
        techniques: List[KnowledgeEntry],
        patterns: List[KnowledgeEntry],
        similar: List[KnowledgeEntry],
    ) -> str:
        """Сгенерировать инструкции."""

        instructions = []

        # Вступление
        instructions.append(f"ОПИСАНИЕ ИЗДЕЛИЯ: {req.project_type.upper()}\n")

        # Материалы
        instructions.append("МАТЕРИАЛЫ:")
        for key, value in materials.items():
            instructions.append(f"- {key}: {value}")
        instructions.append("")

        # Техники
        if techniques:
            instructions.append("ИСПОЛЬЗУЕМЫЕ ТЕХНИКИ:")
            for tech in techniques:
                instructions.append(f"- {tech.title}")
                # Краткое описание
                desc = tech.content[:150].replace("\n", " ").strip()
                instructions.append(f"  {desc}...\n")

        # Узоры
        if patterns:
            instructions.append("УЗОРЫ:")
            for pattern in patterns:
                instructions.append(f"- {pattern.title}")
                desc = pattern.content[:150].replace("\n", " ").strip()
                instructions.append(f"  {desc}...\n")

        # Общие инструкции (из похожих проектов)
        if similar:
            instructions.append("ИНСТРУКЦИИ:")
            # Взять фрагменты из похожих проектов
            for project in similar[:2]:
                # Извлечь инструкции
                content_lines = project.content.split("\n")
                for line in content_lines[:10]:  # Первые 10 строк
                    if line.strip():
                        instructions.append(f"  {line.strip()}")
                instructions.append("")

        return "\n".join(instructions)

    def _estimate_time(
        self, req: ProjectRequirements, techniques: List[KnowledgeEntry]
    ) -> str:
        """Оценить время вязания."""
        # Простая эвристика
        project_times = {
            "шарф": "10-20 часов",
            "scarf": "10-20 hours",
            "шапка": "5-10 часов",
            "hat": "5-10 hours",
            "свитер": "40-60 часов",
            "sweater": "40-60 hours",
            "носки": "8-12 часов",
            "socks": "8-12 hours",
        }

        return project_times.get(req.project_type.lower(), "15-30 часов")

    def _determine_skill_level(
        self, techniques: List[KnowledgeEntry], patterns: List[KnowledgeEntry]
    ) -> str:
        """Определить уровень сложности."""
        # По количеству техник и сложности узоров
        total = len(techniques) + len(patterns)

        if total <= 2:
            return "beginner"
        elif total <= 4:
            return "intermediate"
        else:
            return "advanced"

    def _create_title(self, req: ProjectRequirements) -> str:
        """Создать заголовок."""
        title_parts = [req.project_type.capitalize()]

        if req.yarn_type:
            title_parts.append(f"из {req.yarn_type}")

        if req.technique:
            title_parts.append(f"({req.technique})")

        return " ".join(title_parts)

    def _create_description(
        self,
        req: ProjectRequirements,
        materials: Dict,
        techniques: List[KnowledgeEntry],
    ) -> str:
        """Создать описание."""
        desc = f"{req.project_type.capitalize()} "

        if req.yarn_type:
            desc += f"из {req.yarn_type}, "

        if techniques:
            tech_names = ", ".join([t.title for t in techniques[:2]])
            desc += f"выполненный в технике {tech_names}. "

        desc += "Подходит для "
        if req.skill_level:
            desc += f"{req.skill_level}. "
        else:
            desc += "вязальщиц с базовыми навыками."

        return desc


__all__ = ["PatternGenerator", "ProjectRequirements", "ProjectDescription"]
