#!/usr/bin/env python3
"""Sync glossary JSON into YAML format for GlossaryManager."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict

import yaml


def load_json(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    # Remove // comments if present
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        lines.append(line)
    return json.loads("\n".join(lines))


def normalize_key(entry: Dict[str, Any]) -> str:
    # Prefer explicit key field, else RU text
    return entry.get("key") or entry.get("ru") or entry.get("en")


def build_yaml_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    meta = data.get("meta", {})
    if meta:
        output["metadata"] = meta

    grouped: Dict[str, Dict[str, Any]] = defaultdict(dict)
    for entry in data.get("entries", []):
        category = entry.get("category", "terms")
        key = normalize_key(entry)
        grouped[category][key] = {
            "ru": entry.get("ru", ""),
            "en": entry.get("en", ""),
            "fr": entry.get("fr", ""),
            "note": entry.get("note"),
            "protected_tokens": entry.get("protected_tokens", []),
        }

    output.update(grouped)
    return output


def sync(source: Path, dest: Path) -> None:
    data = load_json(source)
    structure = build_yaml_structure(data)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        yaml.safe_dump(structure, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Synced {source} -> {dest} ({len(data.get('entries', []))} entries)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync glossary JSON into YAML")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/glossary.json",
        help="Path to source glossary.json",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "config/glossaries/knitting_custom.yaml",
        help="Destination YAML path",
    )
    args = parser.parse_args()
    sync(args.source, args.dest)


if __name__ == "__main__":
    main()
