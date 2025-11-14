"""Re-embed legacy semantic memory rows using the current embeddings client."""

from __future__ import annotations

import argparse
import sqlite3
from typing import Optional

import numpy as np

from kps.clients.embeddings import EmbeddingsClient
from kps.translation.semantic_memory import SemanticTranslationMemory


def reindex_semantic_memory(
    db_path: str,
    *,
    target_version: int = 1,
    batch_size: int = 128,
    dry_run: bool = False,
    embedding_client: Optional[EmbeddingsClient] = None,
    model: str = "text-embedding-3-small",
    max_batch: int = 16,
    max_retries: int = 2,
    timeout: float = 30.0,
) -> int:
    """Rebuild embeddings for rows that have outdated vectors."""

    memory = SemanticTranslationMemory(db_path, use_embeddings=False)
    client = embedding_client or EmbeddingsClient(
        model=model,
        max_batch=max_batch,
        max_retries=max_retries,
        timeout=timeout,
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    total = 0
    while True:
        cursor.execute(
            """
            SELECT id, source_text
            FROM translations
            WHERE IFNULL(embedding_version, 0) < ?
            LIMIT ?
            """,
            (target_version, batch_size),
        )
        rows = cursor.fetchall()
        if not rows:
            break

        texts = [row[1] for row in rows]
        vectors = client.create_vectors(texts)
        updates = []
        for (row_id, _text), vector in zip(rows, vectors):
            arr = np.asarray(vector, dtype=np.float32)
            fp32 = SemanticTranslationMemory._embedding_to_bytes(arr)
            fp16 = SemanticTranslationMemory._quantize_embedding(arr)
            updates.append((fp32, fp16, target_version, row_id))

        if dry_run:
            total += len(updates)
            continue

        cursor.executemany(
            "UPDATE translations SET embedding=?, embedding_q16=?, embedding_version=? WHERE id=?",
            updates,
        )
        conn.commit()
        total += len(updates)
        print(f"Re-indexed {total} rows...", flush=True)

    conn.close()
    if dry_run:
        print(f"DRY RUN: would update {total} rows", flush=True)
    else:
        print(f"Re-index complete. Updated {total} rows to version {target_version}.", flush=True)
    return total


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", dest="db_path", required=True, help="Path to semantic memory DB")
    parser.add_argument("--target-version", type=int, default=1)
    parser.add_argument("--batch", type=int, default=128)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default="text-embedding-3-small")
    parser.add_argument("--embedding-batch", type=int, default=16)
    parser.add_argument("--embedding-retries", type=int, default=2)
    parser.add_argument("--embedding-timeout", type=float, default=30.0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    reindex_semantic_memory(
        args.db_path,
        target_version=args.target_version,
        batch_size=args.batch,
        dry_run=args.dry_run,
        model=args.model,
        max_batch=args.embedding_batch,
        max_retries=args.embedding_retries,
        timeout=args.embedding_timeout,
    )


if __name__ == "__main__":
    main()
