"""Seed semantic memory with glossary entries to warm up RAG."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from kps.clients.embeddings import EmbeddingsClient
from kps.translation.glossary.manager import GlossaryManager
from kps.translation.glossary_seed import (
    compute_glossary_checksum,
    seed_memory_with_entries,
)
from kps.translation.semantic_memory import SemanticTranslationMemory


def seed_glossary_memory(
    glossary_path: str,
    db_path: str,
    *,
    source_lang: str = "ru",
    target_lang: str = "en",
    limit: Optional[int] = None,
    dry_run: bool = False,
    model: str = "text-embedding-3-small",
    embedding_batch: int = 16,
    embedding_retries: int = 2,
    embedding_timeout: float = 30.0,
    force: bool = False,
    embedding_client: Optional[EmbeddingsClient] = None,
) -> int:
    manager = GlossaryManager([Path(glossary_path)])
    checksum = compute_glossary_checksum(manager.glossary_paths)
    if not checksum:
        raise RuntimeError("Cannot compute glossary checksum; no files found")

    client = embedding_client or EmbeddingsClient(
        model=model,
        max_batch=embedding_batch,
        max_retries=embedding_retries,
        timeout=embedding_timeout,
    )

    memory = SemanticTranslationMemory(
        db_path,
        use_embeddings=True,
        embedding_client=client,
        embedding_dimensions=None,
    )

    metadata_key = f"glossary_seed:{source_lang}:{target_lang}"
    if not force and memory.get_metadata(metadata_key) == checksum:
        print("Glossary already seeded; use --force to reseed", flush=True)
        return 0

    if dry_run:
        total = len(manager.get_all_entries()) if limit is None else min(
            limit, len(manager.get_all_entries())
        )
        print(f"DRY RUN: would seed {total} entries", flush=True)
        return total

    seeded = seed_memory_with_entries(
        memory,
        manager,
        source_lang=source_lang,
        target_lang=target_lang,
        checksum=checksum,
        limit=limit,
    )
    memory.set_metadata(metadata_key, checksum)
    print(
        f"Seeded {seeded} glossary entries for {source_lang}->{target_lang}",
        flush=True,
    )
    return seeded


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glossary", required=True, help="Path to glossary YAML")
    parser.add_argument("--db", required=True, help="Path to semantic memory DB")
    parser.add_argument("--source", default="ru")
    parser.add_argument("--target", default="en")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--model", default="text-embedding-3-small")
    parser.add_argument("--embedding-batch", type=int, default=16)
    parser.add_argument("--embedding-retries", type=int, default=2)
    parser.add_argument("--embedding-timeout", type=float, default=30.0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    seed_glossary_memory(
        args.glossary,
        args.db,
        source_lang=args.source,
        target_lang=args.target,
        limit=args.limit,
        dry_run=args.dry_run,
        model=args.model,
        embedding_batch=args.embedding_batch,
        embedding_retries=args.embedding_retries,
        embedding_timeout=args.embedding_timeout,
        force=args.force,
    )


if __name__ == "__main__":
    main()
