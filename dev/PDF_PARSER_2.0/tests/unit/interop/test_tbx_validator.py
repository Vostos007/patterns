"""Tests for TBX validation utilities."""

from pathlib import Path

import pytest

from kps.interop.tbx import import_tbx_to_db
from kps.interop.tbx_validator import validate_tbx_file


def write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_validate_tbx_reports_missing_entries(tmp_path):
    tbx = write(tmp_path, "empty.tbx", "<martif></martif>")
    result = validate_tbx_file(str(tbx))
    assert not result.is_valid
    assert any("termEntry" in issue.message for issue in result.issues)


def test_validate_tbx_accepts_basic_structure(tmp_path):
    tbx = write(
        tmp_path,
        "ok.tbx",
        """
<martif>
  <text>
    <body>
      <termEntry>
        <langSet xml:lang="ru">
          <tig><term>петля</term></tig>
        </langSet>
        <langSet xml:lang="en">
          <tig><term>stitch</term></tig>
        </langSet>
      </termEntry>
    </body>
  </text>
</martif>
        """,
    )
    result = validate_tbx_file(str(tbx))
    assert result.is_valid
    assert result.issues == []


def test_import_tbx_to_db_rejects_invalid_file(tmp_path):
    tbx = write(tmp_path, "bad.tbx", "<martif></martif>")
    with pytest.raises(RuntimeError) as exc:
        import_tbx_to_db(str(tbx), db_url="postgresql://test:test@localhost/test_db", src_lang="ru", tgt_lang="en")
    assert "TBX validation failed" in str(exc.value)
