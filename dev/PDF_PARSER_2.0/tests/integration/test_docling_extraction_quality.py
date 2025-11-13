import json
from pathlib import Path

import pytest

from kps.extraction.audit import compare_metrics, compute_metrics
from kps.extraction.docling_extractor import DoclingExtractor

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "extraction"
BASELINE_DIR = FIXTURE_DIR / "baselines"


@pytest.mark.integration
@pytest.mark.parametrize(
    "filename",
    ["cardigan_peer_gynt.docx", "gloves_bonjour.pdf"],
)
def test_docling_extraction_matches_baseline(filename):
    input_path = FIXTURE_DIR / filename
    extractor = DoclingExtractor()
    document = extractor.extract_document(input_path, slug=input_path.stem)
    metrics = compute_metrics(
        document,
        source_file=input_path,
        block_map=extractor.last_block_map,
    )

    baseline_path = BASELINE_DIR / f"{input_path.stem}.metrics.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    diff = compare_metrics(metrics, baseline)

    assert diff == {}, f"Extraction drift detected for {filename}: {diff}"
