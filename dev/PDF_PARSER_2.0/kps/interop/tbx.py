"""
TBX (TermBase eXchange, ISO 30042) import/export.

Supports bidirectional conversion between TBX format and internal glossary_terms table.
"""

from xml.etree import ElementTree as ET
from typing import Dict, List, Optional
import logging

from .tbx_validator import validate_tbx_file

logger = logging.getLogger(__name__)

NS = {"tbx": "urn:iso:std:iso:30042:ed-2"}


def _text(node) -> str:
    return (node.text or "").strip()


def import_tbx_to_db(
    path_tbx: str,
    db_url: str,
    src_lang: str,
    tgt_lang: str,
    domain: str = "general",
    default_flags: Optional[Dict] = None,
) -> int:
    """
    Import TBX file into glossary_terms table.

    Maps termEntry elements to glossary pairs (src_term → tgt_term).
    For each termEntry, extracts terms from langSet[src] and langSet[tgt].

    Args:
        path_tbx: Path to TBX file
        db_url: PostgreSQL connection string
        src_lang: Source language code (e.g., 'ru')
        tgt_lang: Target language code (e.g., 'en')
        domain: Domain/category for terms (default: 'general')
        default_flags: Default flags dict for terms (e.g., {'protected': False})

    Returns:
        Number of term pairs inserted

    Example:
        >>> n = import_tbx_to_db(
        ...     "glossary.tbx",
        ...     "postgresql://user:pass@localhost/kps",
        ...     "ru", "en",
        ...     domain="knitting"
        ... )
        >>> print(f"Imported {n} terms")
    """
    validation = validate_tbx_file(path_tbx)
    if not validation.is_valid:
        summary = "; ".join(issue.message for issue in validation.issues if issue.level == "error")
        raise RuntimeError(f"TBX validation failed: {summary or 'see issues'}")

    try:
        import psycopg2
        import psycopg2.extras
    except ImportError as exc:
        raise RuntimeError("psycopg2 not installed. Install with: pip install psycopg2-binary") from exc

    default_flags = default_flags or {}
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    inserted = 0

    tree = ET.parse(path_tbx)
    root = tree.getroot()

    term_entries = root.findall(".//tbx:termEntry", NS) or root.findall(".//termEntry")

    for te in term_entries:
        lang_terms: Dict[str, List[str]] = {}

        langsets = te.findall("tbx:langSet", NS) or te.findall("langSet")

        for ls in langsets:
            lcode = ls.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", "").lower()
            if not lcode:
                continue

            terms: List[str] = []
            tigs = ls.findall(".//tbx:tig", NS) or ls.findall(".//tig")
            for tig in tigs:
                term = tig.find("tbx:term", NS) or tig.find("term")
                if term is not None:
                    txt = _text(term)
                    if txt:
                        terms.append(txt)

            if terms:
                lang_terms[lcode] = terms

        src_list = lang_terms.get(src_lang.lower(), [])
        tgt_list = lang_terms.get(tgt_lang.lower(), [])

        for s in src_list:
            for t in tgt_list:
                try:
                    cur.execute(
                        """
                        insert into glossary_terms(domain, src_lang, tgt_lang, src_term, tgt_term, flags)
                        values (%s,%s,%s,%s,%s,%s)
                        on conflict do nothing
                        """,
                        (domain, src_lang, tgt_lang, s, t, psycopg2.extras.Json(default_flags)),
                    )
                    inserted += 1
                except Exception as e:
                    logger.warning(f"Failed to insert term '{s}' → '{t}': {e}")
                    continue

    cur.close()
    conn.close()

    logger.info(f"Imported {inserted} term pairs from TBX ({src_lang} → {tgt_lang})")
    return inserted


def export_glossary_to_tbx(
    db_url: str,
    output_path: str,
    src_lang: str,
    tgt_lang: str,
    domain: Optional[str] = None,
) -> int:
    """
    Export glossary_terms to TBX format.

    Args:
        db_url: PostgreSQL connection string
        output_path: Output TBX file path
        src_lang: Source language code
        tgt_lang: Target language code
        domain: Optional domain filter

    Returns:
        Number of term pairs exported

    Example:
        >>> n = export_glossary_to_tbx(
        ...     "postgresql://user:pass@localhost/kps",
        ...     "export.tbx",
        ...     "ru", "en",
        ...     domain="knitting"
        ... )
    """
    try:
        import psycopg2
    except ImportError:
        raise RuntimeError("psycopg2 not installed")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Query glossary terms
    query = """
        select src_term, tgt_term, domain
        from glossary_terms
        where src_lang = %s and tgt_lang = %s
    """
    params = [src_lang, tgt_lang]

    if domain:
        query += " and domain = %s"
        params.append(domain)

    query += " order by src_term"

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Build TBX XML
    root = ET.Element("martif", attrib={
        "type": "TBX",
        "xml:lang": src_lang,
    })

    # Header
    header = ET.SubElement(root, "martifHeader")
    file_desc = ET.SubElement(header, "fileDesc")
    source_desc = ET.SubElement(file_desc, "sourceDesc")
    ET.SubElement(source_desc, "p").text = "Exported from KPS glossary"

    # Body
    text = ET.SubElement(root, "text")
    body = ET.SubElement(text, "body")

    for src_term, tgt_term, term_domain in rows:
        # Create termEntry
        term_entry = ET.SubElement(body, "termEntry")

        # Source language
        src_lang_set = ET.SubElement(term_entry, "langSet", attrib={"{http://www.w3.org/XML/1998/namespace}lang": src_lang})
        src_tig = ET.SubElement(src_lang_set, "tig")
        ET.SubElement(src_tig, "term").text = src_term

        # Target language
        tgt_lang_set = ET.SubElement(term_entry, "langSet", attrib={"{http://www.w3.org/XML/1998/namespace}lang": tgt_lang})
        tgt_tig = ET.SubElement(tgt_lang_set, "tig")
        ET.SubElement(tgt_tig, "term").text = tgt_term

    # Write to file
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="UTF-8", xml_declaration=True)

    logger.info(f"Exported {len(rows)} term pairs to TBX: {output_path}")
    return len(rows)


__all__ = [
    "import_tbx_to_db",
    "export_glossary_to_tbx",
]
