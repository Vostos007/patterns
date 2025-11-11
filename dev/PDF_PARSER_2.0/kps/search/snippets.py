"""
Context compression for LLM prompts.

Extracts relevant snippets from search results to fit within token limits
while preserving the most important information.
"""

from typing import List, Dict


def compress_segments(results: List[Dict], max_chars: int = 2000) -> str:
    """
    Compress search results into concise context for LLM.

    Takes top-N results by score and extracts key paragraphs,
    preserving document/segment references for citations.

    Args:
        results: Search results from hybrid_search()
        max_chars: Maximum character count for compressed output

    Returns:
        Compressed context string with citations

    Example:
        >>> from kps.search import hybrid_search, compress_segments
        >>> results = hybrid_search(db_url, "cable stitch", k=10)
        >>> context = compress_segments(results, max_chars=2000)
        >>> print(context)
        Ряд 1: провязать 6 петель лицевыми...
        [doc:123/seg:5]
        ---
        Перекрестить 3 на 3 петли влево...
        [doc:124/seg:12]
    """
    out = []
    total = 0

    for r in results:
        # Get text (prefer translated, fallback to source)
        txt = (r.get("translated_text") or r.get("src_text") or "").strip()
        if not txt:
            continue

        # Extract first 1-2 paragraphs (simple heuristic)
        paras = [p.strip() for p in txt.split("\n\n") if p.strip()]
        snippet = paras[0] if paras else txt

        # Add metadata for citation
        meta = f"[doc:{r.get('document_id', 'unknown')}/seg:{r.get('segment_id', 'unknown')}]"
        block = f"{snippet}\n{meta}\n"

        # Check if we exceed limit
        if total + len(block) > max_chars:
            break

        out.append(block)
        total += len(block)

    return "\n---\n".join(out)


def compress_with_summary(
    results: List[Dict],
    max_chars: int = 2000,
    summary_ratio: float = 0.3,
) -> str:
    """
    Compress with extractive summarization.

    Takes key sentences from each result rather than full paragraphs.

    Args:
        results: Search results
        max_chars: Maximum character count
        summary_ratio: Ratio of text to extract from each result (0.0-1.0)

    Returns:
        Compressed context with summaries
    """
    out = []
    total = 0

    for r in results:
        txt = (r.get("translated_text") or r.get("src_text") or "").strip()
        if not txt:
            continue

        # Simple sentence extraction (take first N% of text)
        target_len = int(len(txt) * summary_ratio)
        sentences = txt.split(". ")

        summary = ""
        for sent in sentences:
            if len(summary) + len(sent) > target_len:
                break
            summary += sent + ". "

        summary = summary.strip()
        if not summary:
            continue

        meta = f"[doc:{r.get('document_id')}/seg:{r.get('segment_id')}]"
        block = f"{summary}\n{meta}\n"

        if total + len(block) > max_chars:
            break

        out.append(block)
        total += len(block)

    return "\n---\n".join(out)


__all__ = [
    "compress_segments",
    "compress_with_summary",
]
