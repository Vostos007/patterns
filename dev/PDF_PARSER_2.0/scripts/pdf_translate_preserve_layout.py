"""CLI wrapper for kps.layout_preserver."""
from __future__ import annotations

import argparse
from pathlib import Path

from kps.layout_preserver import process_pdf


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate PDF while preserving layout")
    parser.add_argument("--in", dest="input_path", required=True, type=Path)
    parser.add_argument("--out", dest="output_dir", required=True, type=Path)
    parser.add_argument(
        "--langs",
        dest="langs",
        default=None,
        help="Comma-separated ISO codes (ru,en,fr). Defaults to remaining languages",
    )
    args = parser.parse_args()

    if not args.input_path.exists():
        raise FileNotFoundError(args.input_path)

    targets = None
    if args.langs:
        targets = [code.strip() for code in args.langs.split(",") if code.strip()]

    produced = process_pdf(args.input_path, args.output_dir, target_langs=targets)
    for path in produced:
        print(f"[OK] {path}")


if __name__ == "__main__":
    main()
