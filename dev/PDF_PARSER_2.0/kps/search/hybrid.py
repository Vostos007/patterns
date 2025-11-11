"""
Hybrid search combining BM25 (full-text) and vector similarity.

Provides better recall than either method alone by combining:
- BM25 (ts_rank) for keyword matching
- Vector similarity for semantic matching

Alpha parameter controls the weight between BM25 and vector scores.
"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

EMB_MODEL = "text-embedding-3-small"


def _embedding(client, text: str) -> List[float]:
    """
    Generate embedding for text using OpenAI.

    Args:
        client: OpenAI client
        text: Text to embed

    Returns:
        384-dimensional embedding vector
    """
    response = client.embeddings.create(model=EMB_MODEL, input=text)
    return response.data[0].embedding


def hybrid_search(
    db_url: str,
    query: str,
    k: int = 12,
    alpha: float = 0.5,
) -> List[Dict]:
    """
    Hybrid search combining BM25 and vector similarity.

    Args:
        db_url: PostgreSQL connection string
        query: Search query
        k: Number of results to return
        alpha: Weight for BM25 (0.0 = pure vector, 1.0 = pure BM25, 0.5 = balanced)

    Returns:
        List of search results with scores

    Example:
        >>> results = hybrid_search(
        ...     "postgresql://user:pass@localhost/kps",
        ...     "cable stitch pattern",
        ...     k=10,
        ...     alpha=0.5
        ... )
        >>> for r in results:
        ...     print(f"{r['score']:.3f}: {r['src_text'][:50]}...")
    """
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        raise RuntimeError("psycopg2 not installed. Install with: pip install psycopg2-binary")

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai not installed. Install with: pip install openai")

    # Generate query embedding
    client = OpenAI()
    qvec = _embedding(client, query)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # 1) BM25 search (ts_rank) - top 200
    logger.debug(f"Running BM25 search for: {query}")
    cur.execute(
        """
        with q as (select plainto_tsquery('simple', %s) as qq)
        select s.id as segment_id, ts_rank(sc.text, (select qq from q)) as bm25
        from search_corpus sc
        join segments s on s.id = sc.segment_id
        where sc.text @@ (select qq from q)
        order by bm25 desc
        limit 200
        """,
        (query,),
    )
    bm25_rows = cur.fetchall()
    bm25_map = {r["segment_id"]: float(r["bm25"]) for r in bm25_rows}
    bm25_max = max(bm25_map.values()) if bm25_map else 1.0

    # 2) Vector search (cosine similarity = 1 - distance) - top 200
    logger.debug(f"Running vector search for: {query}")
    cur.execute(
        """
        select segment_id, 1 - (vec <=> %s::vector) as sim
        from embeddings
        order by vec <=> %s::vector
        limit 200
        """,
        (qvec, qvec),
    )
    vec_rows = cur.fetchall()
    vec_map = {r["segment_id"]: float(r["sim"]) for r in vec_rows}
    vec_max = max(vec_map.values()) if vec_map else 1.0

    # 3) Combine and normalize scores
    seg_ids = set(bm25_map) | set(vec_map)
    scored = []
    for sid in seg_ids:
        # Normalize to [0, 1]
        bm25_norm = bm25_map.get(sid, 0.0) / bm25_max
        vec_norm = vec_map.get(sid, 0.0) / vec_max

        # Weighted combination
        combined_score = alpha * bm25_norm + (1 - alpha) * vec_norm

        scored.append((sid, combined_score, bm25_norm, vec_norm))

    # Sort by combined score
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:k]

    # 4) Fetch segment data
    ids = [t[0] for t in top]
    if not ids:
        logger.info("No results found")
        cur.close()
        conn.close()
        return []

    cur.execute(
        """
        select s.id as segment_id, s.document_id, s.src_text, t.translated_text
        from segments s
        left join translations t on t.segment_id = s.id
        where s.id = any(%s)
        """,
        (ids,),
    )
    data = {r["segment_id"]: dict(r) for r in cur.fetchall()}
    cur.close()
    conn.close()

    # 5) Build results with scores
    results = []
    for sid, score, bm25, vec in top:
        row = data.get(sid, {})
        row.update({
            "score": score,
            "bm25": bm25,
            "sim": vec,
        })
        results.append(row)

    logger.info(f"Found {len(results)} results for query: {query}")
    return results


__all__ = ["hybrid_search"]
