"""
TMX (Translation Memory eXchange) import/export.

Supports TMX 1.4b format for translation memory interchange.
"""

from xml.etree import ElementTree as ET
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def import_tmx_to_db(
    path_tmx: str,
    db_url: str,
    src_lang: str,
    tgt_lang: str,
) -> int:
    """
    Import TMX file into translations_training table.

    Extracts translation units (TU) with source and target segments.

    Args:
        path_tmx: Path to TMX file
        db_url: PostgreSQL connection string
        src_lang: Source language code (e.g., 'ru')
        tgt_lang: Target language code (e.g., 'en')

    Returns:
        Number of translation pairs inserted

    Example:
        >>> n = import_tmx_to_db(
        ...     "memory.tmx",
        ...     "postgresql://user:pass@localhost/kps",
        ...     "ru", "en"
        ... )
        >>> print(f"Imported {n} translation pairs")
    """
    try:
        import psycopg2
    except ImportError:
        raise RuntimeError("psycopg2 not installed. Install with: pip install psycopg2-binary")

    tree = ET.parse(path_tmx)
    root = tree.getroot()

    # Find body element (with or without namespace)
    body = root.find("body")
    if body is None:
        body = root.find("{*}body")

    if body is None:
        raise ValueError("No <body> element found in TMX file")

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    inserted = 0

    # Iterate through translation units
    for tu in body.findall("tu") + body.findall("{*}tu"):
        src_text, tgt_text = None, None

        # Extract source and target segments
        for tuv in tu.findall("tuv") + tu.findall("{*}tuv"):
            # Get language from xml:lang attribute
            lang = (
                tuv.attrib.get("{http://www.w3.org/XML/1998/namespace}lang") or ""
            ).lower()

            # Find segment text
            seg = tuv.find("seg") or tuv.find("{*}seg")
            if seg is None:
                continue

            text = (seg.text or "").strip()
            if not text:
                continue

            # Match language
            if lang.startswith(src_lang.lower()):
                src_text = text
            elif lang.startswith(tgt_lang.lower()):
                tgt_text = text

        # Insert if both source and target found
        if src_text and tgt_text:
            try:
                cur.execute(
                    """
                    insert into translations_training(src_lang, tgt_lang, src_text, tgt_text)
                    values (%s,%s,%s,%s)
                    on conflict do nothing
                    """,
                    (src_lang, tgt_lang, src_text, tgt_text),
                )
                inserted += 1
            except Exception as e:
                logger.warning(f"Failed to insert translation pair: {e}")
                continue

    cur.close()
    conn.close()

    logger.info(f"Imported {inserted} translation pairs from TMX ({src_lang} → {tgt_lang})")
    return inserted


def export_translations_to_tmx(
    db_url: str,
    output_path: str,
    src_lang: str,
    tgt_lang: str,
    limit: Optional[int] = None,
) -> int:
    """
    Export translations_training to TMX 1.4b format.

    Args:
        db_url: PostgreSQL connection string
        output_path: Output TMX file path
        src_lang: Source language code
        tgt_lang: Target language code
        limit: Optional limit on number of translations to export

    Returns:
        Number of translation pairs exported

    Example:
        >>> n = export_translations_to_tmx(
        ...     "postgresql://user:pass@localhost/kps",
        ...     "export.tmx",
        ...     "ru", "en",
        ...     limit=1000
        ... )
    """
    try:
        import psycopg2
    except ImportError:
        raise RuntimeError("psycopg2 not installed")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Query translations
    query = """
        select src_text, tgt_text, created_at
        from translations_training
        where src_lang = %s and tgt_lang = %s
        order by created_at desc
    """
    params = [src_lang, tgt_lang]

    if limit:
        query += f" limit {limit}"

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Build TMX XML
    root = ET.Element("tmx", attrib={"version": "1.4"})

    # Header
    header = ET.SubElement(root, "header", attrib={
        "creationtool": "KPS",
        "creationtoolversion": "2.0",
        "datatype": "plaintext",
        "segtype": "sentence",
        "adminlang": src_lang,
        "srclang": src_lang,
        "o-tmf": "UTF-8",
    })

    # Body
    body = ET.SubElement(root, "body")

    for src_text, tgt_text, created_at in rows:
        # Create translation unit
        tu = ET.SubElement(body, "tu", attrib={
            "creationdate": created_at.strftime("%Y%m%dT%H%M%SZ"),
        })

        # Source segment
        tuv_src = ET.SubElement(tu, "tuv", attrib={
            "{http://www.w3.org/XML/1998/namespace}lang": src_lang
        })
        ET.SubElement(tuv_src, "seg").text = src_text

        # Target segment
        tuv_tgt = ET.SubElement(tu, "tuv", attrib={
            "{http://www.w3.org/XML/1998/namespace}lang": tgt_lang
        })
        ET.SubElement(tuv_tgt, "seg").text = tgt_text

    # Write to file
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="UTF-8", xml_declaration=True)

    logger.info(f"Exported {len(rows)} translation pairs to TMX: {output_path}")
    return len(rows)


__all__ = [
    "import_tmx_to_db",
    "export_translations_to_tmx",
]
