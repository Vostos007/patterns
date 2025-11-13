"""
Tests for TBX (TermBase eXchange) import/export.
"""

import pytest
from pathlib import Path
import tempfile
from xml.etree import ElementTree as ET

XML_NS = {"xml": "http://www.w3.org/XML/1998/namespace"}


# Sample TBX content for testing
SAMPLE_TBX = """<?xml version="1.0" encoding="UTF-8"?>
<martif type="TBX" xml:lang="ru">
  <martifHeader>
    <fileDesc>
      <sourceDesc>
        <p>Test glossary</p>
      </sourceDesc>
    </fileDesc>
  </martifHeader>
  <text>
    <body>
      <termEntry>
        <langSet xml:lang="ru">
          <tig>
            <term>лицевая петля</term>
          </tig>
        </langSet>
        <langSet xml:lang="en">
          <tig>
            <term>knit stitch</term>
          </tig>
        </langSet>
      </termEntry>
      <termEntry>
        <langSet xml:lang="ru">
          <tig>
            <term>изнаночная петля</term>
          </tig>
        </langSet>
        <langSet xml:lang="en">
          <tig>
            <term>purl stitch</term>
          </tig>
        </langSet>
      </termEntry>
    </body>
  </text>
</martif>
"""


class TestTBXParsing:
    """Tests for TBX file parsing."""

    def test_parse_tbx_structure(self):
        """Test that TBX file can be parsed."""
        root = ET.fromstring(SAMPLE_TBX)
        assert root.tag == "martif"
        assert root.attrib["type"] == "TBX"

    def test_extract_term_entries(self):
        """Test extraction of termEntry elements."""
        root = ET.fromstring(SAMPLE_TBX)
        body = root.find(".//body")
        term_entries = body.findall("termEntry")
        assert len(term_entries) == 2

    def test_extract_terms_by_language(self):
        """Test extraction of terms by language."""
        root = ET.fromstring(SAMPLE_TBX)
        body = root.find(".//body")
        first_entry = body.find("termEntry")

        # Extract RU term
        ru_langset = first_entry.find("langSet[@xml:lang='ru']", namespaces=XML_NS)
        ru_term = ru_langset.find(".//term")
        assert ru_term.text == "лицевая петля"

        # Extract EN term
        en_langset = first_entry.find("langSet[@xml:lang='en']", namespaces=XML_NS)
        en_term = en_langset.find(".//term")
        assert en_term.text == "knit stitch"


class TestTBXImport:
    """Tests for TBX import functionality."""

    @pytest.fixture
    def tbx_file(self, tmp_path):
        """Create temporary TBX file."""
        tbx_path = tmp_path / "test.tbx"
        tbx_path.write_text(SAMPLE_TBX, encoding="utf-8")
        return tbx_path

    def test_import_tbx_file_exists(self, tbx_file):
        """Test that TBX file is created correctly."""
        assert tbx_file.exists()
        content = tbx_file.read_text(encoding="utf-8")
        assert "лицевая петля" in content
        assert "knit stitch" in content

    @pytest.mark.skipif(True, reason="Requires database connection")
    def test_import_tbx_to_db(self, tbx_file):
        """Test importing TBX to database."""
        from kps.interop.tbx import import_tbx_to_db

        # This would require a test database
        # n = import_tbx_to_db(
        #     str(tbx_file),
        #     "postgresql://test",
        #     "ru", "en",
        #     domain="knitting"
        # )
        # assert n >= 2


class TestTBXExport:
    """Tests for TBX export functionality."""

    def test_create_tbx_structure(self):
        """Test creating TBX XML structure."""
        root = ET.Element("martif", attrib={"type": "TBX", "xml:lang": "ru"})
        header = ET.SubElement(root, "martifHeader")
        text = ET.SubElement(root, "text")
        body = ET.SubElement(text, "body")

        # Add a term entry
        term_entry = ET.SubElement(body, "termEntry")

        # RU term
        ru_langset = ET.SubElement(
            term_entry, "langSet", attrib={"{http://www.w3.org/XML/1998/namespace}lang": "ru"}
        )
        ru_tig = ET.SubElement(ru_langset, "tig")
        ET.SubElement(ru_tig, "term").text = "тестовый термин"

        # EN term
        en_langset = ET.SubElement(
            term_entry, "langSet", attrib={"{http://www.w3.org/XML/1998/namespace}lang": "en"}
        )
        en_tig = ET.SubElement(en_langset, "tig")
        ET.SubElement(en_tig, "term").text = "test term"

        # Verify structure
        tree = ET.ElementTree(root)
        assert root.tag == "martif"
        assert len(body.findall("termEntry")) == 1

    @pytest.mark.skipif(True, reason="Requires database connection")
    def test_export_glossary_to_tbx(self, tmp_path):
        """Test exporting glossary to TBX."""
        from kps.interop.tbx import export_glossary_to_tbx

        output_path = tmp_path / "export.tbx"

        # This would require a test database
        # n = export_glossary_to_tbx(
        #     "postgresql://test",
        #     str(output_path),
        #     "ru", "en",
        #     domain="knitting"
        # )
        # assert n >= 0
        # assert output_path.exists()


class TestTBXRoundTrip:
    """Tests for TBX round-trip (import then export)."""

    @pytest.mark.skipif(True, reason="Requires database connection")
    def test_tbx_round_trip(self, tmp_path):
        """Test importing TBX and exporting it back."""
        # Would test: import → DB → export → verify equality
        pass


class TestTBXEdgeCases:
    """Tests for edge cases in TBX processing."""

    def test_empty_tbx(self):
        """Test handling of empty TBX file."""
        empty_tbx = """<?xml version="1.0" encoding="UTF-8"?>
<martif type="TBX" xml:lang="ru">
  <martifHeader>
    <fileDesc><sourceDesc><p>Empty</p></sourceDesc></fileDesc>
  </martifHeader>
  <text><body></body></text>
</martif>"""

        root = ET.fromstring(empty_tbx)
        body = root.find(".//body")
        term_entries = body.findall("termEntry")
        assert len(term_entries) == 0

    def test_tbx_with_multiple_terms_per_language(self):
        """Test TBX with multiple term variants per language."""
        multi_term_tbx = """<?xml version="1.0" encoding="UTF-8"?>
<martif type="TBX" xml:lang="ru">
  <martifHeader>
    <fileDesc><sourceDesc><p>Test</p></sourceDesc></fileDesc>
  </martifHeader>
  <text>
    <body>
      <termEntry>
        <langSet xml:lang="ru">
          <tig><term>вариант1</term></tig>
          <tig><term>вариант2</term></tig>
        </langSet>
        <langSet xml:lang="en">
          <tig><term>variant1</term></tig>
          <tig><term>variant2</term></tig>
        </langSet>
      </termEntry>
    </body>
  </text>
</martif>"""

        root = ET.fromstring(multi_term_tbx)
        body = root.find(".//body")
        first_entry = body.find("termEntry")
        ru_langset = first_entry.find("langSet[@xml:lang='ru']", namespaces=XML_NS)
        ru_terms = ru_langset.findall(".//term")
        assert len(ru_terms) == 2
        assert ru_terms[0].text == "вариант1"
        assert ru_terms[1].text == "вариант2"

    def test_tbx_without_namespace(self):
        """Test TBX file without explicit namespace."""
        no_ns_tbx = """<?xml version="1.0" encoding="UTF-8"?>
<martif type="TBX">
  <martifHeader></martifHeader>
  <text>
    <body>
      <termEntry>
        <langSet xml:lang="ru">
          <tig><term>термин</term></tig>
        </langSet>
        <langSet xml:lang="en">
          <tig><term>term</term></tig>
        </langSet>
      </termEntry>
    </body>
  </text>
</martif>"""

        root = ET.fromstring(no_ns_tbx)
        body = root.find(".//body")
        term_entries = body.findall("termEntry")
        assert len(term_entries) == 1
