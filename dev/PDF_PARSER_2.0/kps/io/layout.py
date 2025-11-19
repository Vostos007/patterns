"""I/O layout helpers for standardized input/intermediate/output structure."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from docling_core.types.doc.document import DoclingDocument


_SLUG_PATTERN = re.compile(r"[^\w-]+", re.UNICODE)


def _slugify(value: str) -> str:
    value = value.replace(os.sep, "-").replace("/", "-")
    slug = _SLUG_PATTERN.sub("-", value.strip())
    slug = slug.strip("-_")
    return slug.lower() or "document"


@dataclass
class RunContext:
    slug: str
    version: str
    staged_input: Path
    output_dir: Path
    inter_json_path: Path
    inter_markdown_path: Path
    input_hash: str

    def dump_docling(self, docling_doc: Optional[DoclingDocument]) -> None:
        if docling_doc is None:
            return
        self.inter_json_path.parent.mkdir(parents=True, exist_ok=True)
        self.inter_markdown_path.parent.mkdir(parents=True, exist_ok=True)
        docling_doc.save_as_json(self.inter_json_path)
        self.inter_markdown_path.write_text(docling_doc.export_to_markdown(), encoding="utf-8")


class IOLayout:
    """Managed directory layout for input/intermediate/output/tmp."""

    def __init__(
        self,
        base_root: Path,
        use_tmp: bool = False,
        publish_root: Optional[Path] = None,
    ) -> None:
        base_root = base_root.expanduser()
        if use_tmp:
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            self.root = (base_root / "tmp" / timestamp).resolve()
            self.tmp_dir = self.root
        else:
            self.root = base_root.resolve()
            self.tmp_dir = self.root / "tmp"
        self.input_dir = self.root / "input"
        self.inter_dir = self.root / "inter"
        self.inter_json_dir = self.inter_dir / "json"
        self.inter_markdown_dir = self.inter_dir / "markdown"
        self.output_dir = self.root / "output"
        self.publish_root = publish_root.expanduser().resolve() if publish_root else None
        self._ensure_base_dirs()

    def _ensure_base_dirs(self) -> None:
        base_dirs = [
            self.input_dir,
            self.inter_json_dir,
            self.inter_markdown_dir,
            self.output_dir,
        ]
        if self.tmp_dir != self.root:
            base_dirs.append(self.tmp_dir)
        for path in base_dirs:
            path.mkdir(parents=True, exist_ok=True)

    def stage_input(self, source: Path) -> Path:
        source = source.expanduser().resolve()
        self.input_dir.mkdir(parents=True, exist_ok=True)
        destination = self.input_dir / source.name
        if source != destination:
            shutil.copy2(source, destination)
        return destination

    def prepare_run(self, source: Path) -> RunContext:
        staged_input = self.stage_input(source)
        slug = _slugify(staged_input.stem)
        version = self._next_version(slug)
        input_hash = self._hash_file(staged_input)
        output_dir = (self.output_dir / slug / version)
        output_dir.mkdir(parents=True, exist_ok=False)
        inter_json_path = self.inter_json_dir / f"{slug}_{version}.json"
        inter_markdown_path = self.inter_markdown_dir / f"{slug}_{version}.md"
        return RunContext(
            slug=slug,
            version=version,
            staged_input=staged_input,
            output_dir=output_dir,
            inter_json_path=inter_json_path,
            inter_markdown_path=inter_markdown_path,
            input_hash=input_hash,
        )

    def _next_version(self, slug: str) -> str:
        slug_dir = self.output_dir / slug
        slug_dir.mkdir(parents=True, exist_ok=True)
        existing = [p.name for p in slug_dir.iterdir() if p.is_dir() and p.name.startswith("v")]
        if self.publish_root:
            published_slug_dir = self.publish_root / slug
            if published_slug_dir.exists():
                published_versions = [
                    p.name
                    for p in published_slug_dir.iterdir()
                    if p.is_dir() and p.name.startswith("v")
                ]
                existing.extend(published_versions)
        numbers = []
        for name in existing:
            try:
                numbers.append(int(name[1:]))
            except ValueError:
                continue
        next_number = max(numbers) + 1 if numbers else 1
        return f"v{next_number:03d}"

    def _hash_file(self, path: Path) -> str:
        sha = hashlib.sha256()
        with open(path, "rb") as handle:
            while chunk := handle.read(8192):
                sha.update(chunk)
        return sha.hexdigest()


__all__ = ["IOLayout", "RunContext"]
