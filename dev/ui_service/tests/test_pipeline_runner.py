from pathlib import Path

from app.pipeline_runner import run_pipeline_job


class FakePipeline:
    def __init__(self):
        self.called = False

    def process(self, input_file, target_languages, output_dir):
        self.called = True
        artifacts = {}
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for lang in target_languages:
            dest = out_dir / f"{lang}.txt"
            dest.write_text(f"lang={lang}", encoding="utf-8")
            artifacts[lang] = str(dest)
        return type("Result", (), {"output_files": artifacts})


def test_pipeline_runner_invokes_document_pipeline(tmp_path):
    src = tmp_path / "doc.pdf"
    src.write_text("pdf")
    pipeline = FakePipeline()
    dest_root = tmp_path / "outputs"
    artifacts = run_pipeline_job(
        job_id="job-1",
        source_path=src,
        target_languages=["en"],
        output_root=dest_root,
        pipeline=pipeline,
    )
    assert pipeline.called
    assert len(artifacts) == 1
    assert artifacts[0].exists()
    assert artifacts[0].parent == dest_root / "en"
