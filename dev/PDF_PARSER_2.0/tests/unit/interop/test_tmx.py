"""
Tests for TMX (Translation Memory eXchange) import/export.
"""

import pytest
from pathlib import Path
from xml.etree import ElementTree as ET

XML_NS = {"xml": "http://www.w3.org/XML/1998/namespace"}


# Sample TMX content for testing (TMX 1.4b format)
SAMPLE_TMX = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header
    creationtool="KPS"
    creationtoolversion="2.0"
    datatype="plaintext"
    segtype="sentence"
    adminlang="ru"
    srclang="ru"
    o-tmf="UTF-8"
  />
  <body>
    <tu creationdate="20250111T120000Z">
      <tuv xml:lang="ru">
        <seg>Провязать лицевую петлю</seg>
      </tuv>
      <tuv xml:lang="en">
        <seg>Work a knit stitch</seg>
      </tuv>
    </tu>
    <tu creationdate="20250111T120001Z">
      <tuv xml:lang="ru">
        <seg>Повторить до конца ряда</seg>
      </tuv>
      <tuv xml:lang="en">
        <seg>Repeat to end of row</seg>
      </tuv>
    </tu>
  </body>
</tmx>
"""


class TestTMXParsing:
    """Tests for TMX file parsing."""

    def test_parse_tmx_structure(self):
        """Test that TMX file can be parsed."""
        root = ET.fromstring(SAMPLE_TMX)
        assert root.tag == "tmx"
        assert root.attrib["version"] == "1.4"

    def test_extract_translation_units(self):
        """Test extraction of TU (translation unit) elements."""
        root = ET.fromstring(SAMPLE_TMX)
        body = root.find("body")
        tus = body.findall("tu")
        assert len(tus) == 2

    def test_extract_segments_by_language(self):
        """Test extraction of segments by language."""
        root = ET.fromstring(SAMPLE_TMX)
        body = root.find("body")
        first_tu = body.find("tu")

        # Extract RU segment
        ru_tuv = first_tu.find("tuv[@xml:lang='ru']", namespaces=XML_NS)
        ru_seg = ru_tuv.find("seg")
        assert ru_seg.text == "Провязать лицевую петлю"

        # Extract EN segment
        en_tuv = first_tu.find("tuv[@xml:lang='en']", namespaces=XML_NS)
        en_seg = en_tuv.find("seg")
        assert en_seg.text == "Work a knit stitch"


class TestTMXImport:
    """Tests for TMX import functionality."""

    @pytest.fixture
    def tmx_file(self, tmp_path):
        """Create temporary TMX file."""
        tmx_path = tmp_path / "test.tmx"
        tmx_path.write_text(SAMPLE_TMX, encoding="utf-8")
        return tmx_path

    def test_import_tmx_file_exists(self, tmx_file):
        """Test that TMX file is created correctly."""
        assert tmx_file.exists()
        content = tmx_file.read_text(encoding="utf-8")
        assert "Провязать лицевую петлю" in content
        assert "Work a knit stitch" in content

    @pytest.mark.skipif(True, reason="Requires database connection")
    def test_import_tmx_to_db(self, tmx_file):
        """Test importing TMX to database."""
        from kps.interop.tmx import import_tmx_to_db

        # This would require a test database
        # n = import_tmx_to_db(
        #     str(tmx_file),
        #     "postgresql://test",
        #     "ru", "en"
        # )
        # assert n >= 2


class TestTMXExport:
    """Tests for TMX export functionality."""

    def test_create_tmx_structure(self):
        """Test creating TMX XML structure."""
        root = ET.Element("tmx", attrib={"version": "1.4"})

        header = ET.SubElement(root, "header", attrib={
            "creationtool": "KPS",
            "creationtoolversion": "2.0",
            "datatype": "plaintext",
            "segtype": "sentence",
            "adminlang": "ru",
            "srclang": "ru",
            "o-tmf": "UTF-8",
        })

        body = ET.SubElement(root, "body")

        # Add a translation unit
        tu = ET.SubElement(body, "tu", attrib={
            "creationdate": "20250111T120000Z"
        })

        # RU segment
        tuv_ru = ET.SubElement(tu, "tuv", attrib={
            "{http://www.w3.org/XML/1998/namespace}lang": "ru"
        })
        ET.SubElement(tuv_ru, "seg").text = "тестовый сегмент"

        # EN segment
        tuv_en = ET.SubElement(tu, "tuv", attrib={
            "{http://www.w3.org/XML/1998/namespace}lang": "en"
        })
        ET.SubElement(tuv_en, "seg").text = "test segment"

        # Verify structure
        assert root.tag == "tmx"
        assert len(body.findall("tu")) == 1

    @pytest.mark.skipif(True, reason="Requires database connection")
    def test_export_translations_to_tmx(self, tmp_path):
        """Test exporting translations to TMX."""
        from kps.interop.tmx import export_translations_to_tmx

        output_path = tmp_path / "export.tmx"

        # This would require a test database
        # n = export_translations_to_tmx(
        #     "postgresql://test",
        #     str(output_path),
        #     "ru", "en",
        #     limit=100
        # )
        # assert n >= 0
        # assert output_path.exists()


class TestTMXEdgeCases:
    """Tests for edge cases in TMX processing."""

    def test_empty_tmx(self):
        """Test handling of empty TMX file."""
        empty_tmx = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header creationtool="KPS" datatype="plaintext" segtype="sentence" adminlang="ru" srclang="ru"/>
  <body></body>
</tmx>"""

        root = ET.fromstring(empty_tmx)
        body = root.find("body")
        tus = body.findall("tu")
        assert len(tus) == 0

    def test_tmx_with_multiple_target_languages(self):
        """Test TMX with multiple target languages in one TU."""
        multi_lang_tmx = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header creationtool="KPS" datatype="plaintext" segtype="sentence" adminlang="ru" srclang="ru"/>
  <body>
    <tu>
      <tuv xml:lang="ru">
        <seg>источник</seg>
      </tuv>
      <tuv xml:lang="en">
        <seg>source</seg>
      </tuv>
      <tuv xml:lang="fr">
        <seg>source</seg>
      </tuv>
    </tu>
  </body>
</tmx>"""

        root = ET.fromstring(multi_lang_tmx)
        body = root.find("body")
        first_tu = body.find("tu")
        tuvs = first_tu.findall("tuv")
        assert len(tuvs) == 3

    def test_tmx_without_namespace(self):
        """Test TMX file without explicit namespace."""
        no_ns_tmx = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header creationtool="KPS" datatype="plaintext"/>
  <body>
    <tu>
      <tuv xml:lang="ru">
        <seg>текст</seg>
      </tuv>
      <tuv xml:lang="en">
        <seg>text</seg>
      </tuv>
    </tu>
  </body>
</tmx>"""

        root = ET.fromstring(no_ns_tmx)
        body = root.find("body")
        tus = body.findall("tu")
        assert len(tus) == 1

    def test_tmx_with_metadata(self):
        """Test TMX with additional metadata in TU."""
        meta_tmx = """<?xml version="1.0" encoding="UTF-8"?>
<tmx version="1.4">
  <header creationtool="KPS" datatype="plaintext"/>
  <body>
    <tu creationdate="20250111T120000Z" creationid="user123" changedate="20250111T130000Z">
      <tuv xml:lang="ru">
        <seg>текст с метаданными</seg>
      </tuv>
      <tuv xml:lang="en">
        <seg>text with metadata</seg>
      </tuv>
    </tu>
  </body>
</tmx>"""

        root = ET.fromstring(meta_tmx)
        body = root.find("body")
        first_tu = body.find("tu")
        assert first_tu.attrib["creationdate"] == "20250111T120000Z"
        assert first_tu.attrib["creationid"] == "user123"


class TestTMXRoundTrip:
    """Tests for TMX round-trip (import then export)."""

    @pytest.mark.skipif(True, reason="Requires database connection")
    def test_tmx_round_trip(self, tmp_path):
        """Test importing TMX and exporting it back."""
        # Would test: import → DB → export → verify equality
        pass


class TestTMXPerformance:
    """Tests for TMX performance with large files."""

    def test_parse_large_tmx_structure(self):
        """Test parsing a TMX with many TUs."""
        # Build TMX with 100 TUs
        root = ET.Element("tmx", attrib={"version": "1.4"})
        header = ET.SubElement(root, "header", attrib={
            "creationtool": "KPS",
            "datatype": "plaintext"
        })
        body = ET.SubElement(root, "body")

        for i in range(100):
            tu = ET.SubElement(body, "tu")
            tuv_ru = ET.SubElement(tu, "tuv", attrib={"xml:lang": "ru"})
            ET.SubElement(tuv_ru, "seg").text = f"сегмент {i}"
            tuv_en = ET.SubElement(tu, "tuv", attrib={"xml:lang": "en"})
            ET.SubElement(tuv_en, "seg").text = f"segment {i}"

        # Verify all TUs are present
        tus = body.findall("tu")
        assert len(tus) == 100
