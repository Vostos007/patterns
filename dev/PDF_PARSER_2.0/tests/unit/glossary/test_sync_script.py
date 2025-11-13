from pathlib import Path

import yaml

from kps.translation.glossary.manager import GlossaryManager

import subprocess
import sys


def run_sync(tmp_path: Path):
    src = tmp_path / "glossary.json"
    src.write_text(
        """
        {
          "meta": {"title": "Test"},
          "entries": [
            {"ru": "лиц", "en": "knit", "fr": "maille", "category": "terms", "protected_tokens": ["knit"]},
            {"ru": "2ВмЛЛ", "en": "ssk", "fr": "surjet", "category": "decrease"}
          ]
        }
        """,
        encoding="utf-8",
    )
    dest = tmp_path / "glossaries/knitting_custom.yaml"
    venv_python = Path(sys.executable)
    cmd = [
        str(venv_python),
        str(Path(__file__).resolve().parents[3] / "scripts/sync_glossary.py"),
        "--source",
        str(src),
        "--dest",
        str(dest),
    ]
    subprocess.check_call(cmd)
    return dest


def test_sync_script_generates_yaml(tmp_path: Path):
    dest = run_sync(tmp_path)
    data = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert data["terms"]["лиц"]["en"] == "knit"
    assert data["decrease"]["2ВмЛЛ"]["en"] == "ssk"


def test_glossary_manager_reads_synced_yaml(tmp_path: Path):
    dest = run_sync(tmp_path)
    manager = GlossaryManager(glossary_paths=[dest])
    entries = manager.get_all_entries()
    assert any(entry.en == "knit" for entry in entries)
