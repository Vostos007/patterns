#!/usr/bin/env python3
"""Utility to reset dev/PDF_PARSER_2.0/runtime between translation runs."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Iterable, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
INPUT_DIR = RUNTIME_DIR / "input"
INTER_DIR = RUNTIME_DIR / "inter"
TMP_DIR = RUNTIME_DIR / "tmp"
OUTPUT_DIR = RUNTIME_DIR / "output"


def ensure_gitkeep(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    keeper = directory / ".gitkeep"
    if not keeper.exists():
        keeper.touch()


def wipe_children(directory: Path, *, dry_run: bool) -> List[Path]:
    removed: List[Path] = []
    if not directory.exists():
        return removed

    for child in directory.iterdir():
        if child.name == ".gitkeep":
            continue
        removed.append(child)
        action = "[dry-run] would remove" if dry_run else "removed"
        print(f"{action} {child}")
        if dry_run:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    if not dry_run:
        ensure_gitkeep(directory)
    return removed


def version_key(path: Path) -> Tuple[int, object]:
    digits = "".join(ch for ch in path.name if ch.isdigit())
    if digits:
        return (0, int(digits))
    return (1, path.name)


def trim_output(doc_dir: Path, *, keep_latest: int, dry_run: bool) -> None:
    ensure_gitkeep(doc_dir)
    if keep_latest < 0:
        raise ValueError("keep_latest must be >= 0")

    for stray in [p for p in doc_dir.iterdir() if p.is_file() and p.name != ".gitkeep"]:
        action = "[dry-run] would remove" if dry_run else "removed"
        print(f"{action} {stray}")
        if not dry_run:
            stray.unlink()

    version_dirs = [d for d in doc_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"]
    version_dirs.sort(key=version_key)
    if keep_latest == 0:
        to_delete = version_dirs
    else:
        to_delete = version_dirs[:-keep_latest]

    if not to_delete:
        print(f"no versions removed under {doc_dir} (keeping {keep_latest})")
        return

    for path in to_delete:
        action = "[dry-run] would remove" if dry_run else "removed"
        print(f"{action} {path}")
        if dry_run:
            continue
        shutil.rmtree(path)

    remaining = len(version_dirs) - len(to_delete)
    print(f"{doc_dir}: trimmed to {remaining} versions (keep_latest={keep_latest})")


def cleanup_runtime(*, keep_latest: int, dry_run: bool) -> None:
    if not RUNTIME_DIR.exists():
        raise SystemExit(f"runtime directory not found: {RUNTIME_DIR}")

    ensure_gitkeep(RUNTIME_DIR)

    sections: Iterable[Tuple[str, Path]] = [
        ("input", INPUT_DIR),
        ("inter/baselines", INTER_DIR / "baselines"),
        ("inter/json", INTER_DIR / "json"),
        ("inter/markdown", INTER_DIR / "markdown"),
        ("tmp", TMP_DIR),
    ]

    for label, directory in sections:
        print(f"-- wiping {label} --")
        ensure_gitkeep(directory)
        wipe_children(directory, dry_run=dry_run)

    if OUTPUT_DIR.exists():
        for doc_dir in sorted(p for p in OUTPUT_DIR.iterdir() if p.is_dir() and p.name != ".gitkeep"):
            print(f"-- trimming output for {doc_dir.name} --")
            trim_output(doc_dir, keep_latest=keep_latest, dry_run=dry_run)
    else:
        print("runtime/output does not exist; skipping")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup runtime artifacts")
    parser.add_argument(
        "--keep-latest",
        type=int,
        default=1,
        help="how many latest iterations (per document) to keep inside runtime/output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be deleted without removing anything",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.keep_latest < 0:
        raise SystemExit("--keep-latest must be >= 0")
    cleanup_runtime(keep_latest=args.keep_latest, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
