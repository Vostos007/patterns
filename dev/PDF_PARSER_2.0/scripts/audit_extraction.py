#!/usr/bin/env python3
"""CLI utility to audit Docling extraction quality for DOCX/PDF inputs."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

from kps.extraction.audit import compare_metrics, compute_metrics, write_metrics
from kps.extraction.docling_extractor import DoclingExtractor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def _load_baseline(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _baseline_path(baseline_dir: Path, input_file: Path) -> Path:
    return baseline_dir / f"{input_file.stem}.metrics.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Docling extraction outputs.")
    parser.add_argument("files", nargs="+", type=Path, help="DOCX/PDF files to audit")
    parser.add_argument("--baseline-dir", type=Path, help="Directory containing metric baseline JSON files", default=None)
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write fresh baselines into --baseline-dir",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=0,
        help="Allowed difference for numeric metrics",
    )
    parser.add_argument(
        "--dump-json-dir",
        type=Path,
        default=None,
        help="Directory to store Docling JSON exports",
    )
    parser.add_argument(
        "--dump-markdown-dir",
        type=Path,
        default=None,
        help="Directory to store Docling Markdown exports",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    files: list[Path] = args.files
    baseline_dir: Optional[Path] = args.baseline_dir
    write_baseline: bool = args.write_baseline
    tolerance: int = args.tolerance
    dump_json_dir: Optional[Path] = args.dump_json_dir
    dump_markdown_dir: Optional[Path] = args.dump_markdown_dir

    if write_baseline and baseline_dir is None:
        raise SystemExit("--write-baseline requires --baseline-dir")

    extractor = DoclingExtractor()

    for input_path in files:
        if not input_path.is_file():
            logging.warning("Skipping %s (not a file)", input_path)
            continue
        logging.info("Auditing %s", input_path)
        document = extractor.extract_document(input_path, slug=input_path.stem)
        docling_doc = extractor.last_docling_document
        metrics = compute_metrics(
            document,
            source_file=input_path,
            block_map=extractor.last_block_map,
        )
        print(json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2))

        if docling_doc is None and (dump_json_dir or dump_markdown_dir):
            logging.warning("Docling document unavailable; skipping dumps for %s", input_path)
        else:
            if dump_markdown_dir and docling_doc is not None:
                dump_markdown_dir.mkdir(parents=True, exist_ok=True)
                md_path = dump_markdown_dir / f"{input_path.stem}.md"
                md_path.write_text(docling_doc.export_to_markdown(), encoding="utf-8")
                logging.info("Markdown export saved: %s", md_path)

            if dump_json_dir and docling_doc is not None:
                dump_json_dir.mkdir(parents=True, exist_ok=True)
                json_path = dump_json_dir / f"{input_path.stem}.docling.json"
                docling_doc.save_as_json(json_path)
                logging.info("JSON export saved: %s", json_path)

        if baseline_dir:
            baseline_path = _baseline_path(baseline_dir, input_path)
            baseline = _load_baseline(baseline_path)
            if baseline is None:
                logging.warning("Baseline missing: %s", baseline_path)
                if write_baseline:
                    write_metrics(metrics, baseline_path)
                    logging.info("Baseline written: %s", baseline_path)
            else:
                diff = compare_metrics(metrics, baseline, tolerance=tolerance)
                if diff:
                    print(
                        json.dumps(
                            {"file": str(input_path), "diff": diff},
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                else:
                    logging.info("Metrics match baseline (tolerance=%s)", tolerance)
        elif write_baseline:
            raise SystemExit("--write-baseline requires --baseline-dir")


if __name__ == "__main__":
    main()
