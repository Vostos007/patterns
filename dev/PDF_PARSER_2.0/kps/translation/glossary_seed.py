"""Utilities for seeding glossary terms into semantic memory."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Iterable, Optional

from .glossary.manager import GlossaryManager

logger = logging.getLogger(__name__)


def compute_glossary_checksum(paths: Iterable[Path]) -> Optional[str]:
    hasher = hashlib.sha256()
    found = False
    for raw_path in sorted(str(Path(p)) for p in paths):
        path = Path(raw_path)
        if path.exists():
            hasher.update(path.read_bytes())
            found = True
    if not found:
        return None
    return hasher.hexdigest()


def seed_memory_with_entries(
    memory,
    glossary: GlossaryManager,
    *,
    source_lang: str,
    target_lang: str,
    checksum: str,
    min_quality: float = 0.5,
    limit: Optional[int] = None,
    context: str = "glossary-seed",
) -> int:
    version_int = int(checksum[:12], 16)
    seeded = 0

    for entry in glossary.get_all_entries():
        source = getattr(entry, source_lang, "").strip()
        target = getattr(entry, target_lang, "").strip()
        if not source or not target:
            continue

        try:
            memory.add_translation(
                source_text=source,
                translated_text=target,
                source_lang=source_lang,
                target_lang=target_lang,
                glossary_terms=[entry.key],
                quality_score=min_quality,
                context=context,
                glossary_version=version_int,
            )
            seeded += 1
        except Exception as exc:  # pragma: no cover - log and continue
            logger.warning("Failed to seed glossary entry %s: %s", entry.key, exc)
            continue

        if limit and seeded >= limit:
            break

    return seeded
