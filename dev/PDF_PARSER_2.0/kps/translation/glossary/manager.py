"""
Glossary manager for multi-language translation in KPS v2.0.

Provides term lookups, protected token management, and glossary context building.
Enhanced from PDF_parser with YAML support and multi-domain glossaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml


@dataclass
class GlossaryEntry:
    """Single glossary entry with translations."""

    key: str
    ru: str
    en: str
    fr: str
    category: str  # "abbreviation", "term", "unit"
    description: Optional[str] = None
    protected_tokens: List[str] = None

    def __post_init__(self):
        if self.protected_tokens is None:
            self.protected_tokens = []


@dataclass
class GlossaryMatch:
    """Result of a glossary lookup."""

    key: str
    source_text: str
    target_text: str
    category: str
    description: Optional[str] = None


class GlossaryManager:
    """
    Manages glossary lookups and protected tokens for translation.

    Supports multiple domains (knitting.yaml, sewing.yaml) and
    multi-language lookups (ru → en, ru → fr).
    """

    def __init__(self, glossary_paths: Optional[List[Path]] = None):
        """
        Initialize glossary manager.

        Args:
            glossary_paths: List of YAML glossary files to load.
                           If None, attempts to load from config/glossaries/
        """
        self.glossary_paths = glossary_paths or self._discover_glossaries()
        self.entries: List[GlossaryEntry] = []
        self.protected_tokens: Set[str] = set()

        # Load all glossaries
        self._load_glossaries()

        # Build lookup indices for fast access
        self._build_indices()

    def _discover_glossaries(self) -> List[Path]:
        """Auto-discover glossary YAML files in config/glossaries/."""
        config_dir = Path(__file__).parents[3] / "config" / "glossaries"
        if config_dir.exists():
            return list(config_dir.glob("*.yaml"))
        return []

    def _load_glossaries(self) -> None:
        """Load all glossary YAML files."""
        for path in self.glossary_paths:
            self._load_glossary_file(path)

    def _load_glossary_file(self, path: Path) -> None:
        if not path.exists():
            return

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self._ingest_entries(data)

    def _ingest_entries(self, data: Dict) -> None:
        for category, entries_dict in data.items():
            if category == "metadata" or not isinstance(entries_dict, dict):
                continue

            normalized_category = (
                category.rstrip("s")
                if category in {"abbreviations", "terms", "units"}
                else category
            )

            for key, values in entries_dict.items():
                entry = GlossaryEntry(
                    key=key,
                    ru=values.get("ru", ""),
                    en=values.get("en", ""),
                    fr=values.get("fr", ""),
                    category=normalized_category,
                    description=values.get("description") or values.get("note"),
                    protected_tokens=values.get("protected_tokens", []),
                )
                self.entries.append(entry)
                self.protected_tokens.update(entry.protected_tokens)

    def load_from_yaml(self, path: str) -> None:
        """Load an additional glossary YAML file at runtime."""
        self._load_glossary_file(Path(path))
        self._build_indices()

    def _build_indices(self) -> None:
        """Build lookup indices for fast access by language and category."""
        self._by_key: Dict[str, GlossaryEntry] = {e.key: e for e in self.entries}
        self._by_category: Dict[str, List[GlossaryEntry]] = {}

        for entry in self.entries:
            if entry.category not in self._by_category:
                self._by_category[entry.category] = []
            self._by_category[entry.category].append(entry)

    def lookup(
        self,
        key: str,
        source_lang: str = "ru",
        target_lang: str = "en",
    ) -> Optional[GlossaryMatch]:
        """
        Look up a glossary entry by key.

        Args:
            key: Entry key (e.g., "k", "pattern", "cm")
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            GlossaryMatch if found, None otherwise
        """
        entry = self._by_key.get(key)
        if not entry:
            return None

        source_text = getattr(entry, source_lang, None)
        target_text = getattr(entry, target_lang, None)

        if source_text is None or target_text is None:
            return None

        return GlossaryMatch(
            key=key,
            source_text=source_text,
            target_text=target_text,
            category=entry.category,
            description=entry.description,
        )

    def get_all_entries(self, category: Optional[str] = None) -> List[GlossaryEntry]:
        """
        Get all glossary entries, optionally filtered by category.

        Args:
            category: Optional category filter ("abbreviation", "term", "unit")

        Returns:
            List of glossary entries
        """
        if category:
            return self._by_category.get(category, [])
        return self.entries

    def is_protected(self, token: str) -> bool:
        """
        Check if a token is protected (should not be translated).

        Args:
            token: Token to check

        Returns:
            True if token is protected
        """
        return token in self.protected_tokens

    def get_protected_tokens(self) -> List[str]:
        """
        Get list of all protected tokens.

        Returns:
            List of protected tokens
        """
        return list(self.protected_tokens)

    def build_context_for_prompt(
        self,
        source_lang: str = "ru",
        target_lang: str = "en",
        selected_entries: Optional[List[GlossaryEntry]] = None,
    ) -> str:
        """
        Build glossary context string for LLM prompt.

        Args:
            source_lang: Source language code
            target_lang: Target language code
            selected_entries: Optional subset of entries. If None, uses all.

        Returns:
            Formatted glossary context string
        """
        entries_to_use = selected_entries if selected_entries else self.entries

        lines = ["Glossary (use these exact translations):"]

        # Group by category
        by_cat: Dict[str, List[GlossaryEntry]] = {}
        for entry in entries_to_use:
            if entry.category not in by_cat:
                by_cat[entry.category] = []
            by_cat[entry.category].append(entry)

        # Format each category
        for category in ["abbreviation", "term", "unit"]:
            entries = by_cat.get(category, [])
            if not entries:
                continue

            lines.append(f"\n{category.title()}s:")
            for entry in sorted(entries, key=lambda e: e.key):
                source_text = getattr(entry, source_lang)
                target_text = getattr(entry, target_lang)
                desc = f" ({entry.description})" if entry.description else ""
                lines.append(f"  {source_text} → {target_text}{desc}")

        return "\n".join(lines)

    def get_statistics(self) -> Dict:
        """
        Get glossary statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "total_entries": len(self.entries),
            "by_category": {
                cat: len(entries) for cat, entries in self._by_category.items()
            },
            "total_protected_tokens": len(self.protected_tokens),
            "loaded_files": [str(p) for p in self.glossary_paths],
        }


__all__ = ["GlossaryManager", "GlossaryEntry", "GlossaryMatch"]
