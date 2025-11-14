from pathlib import Path

from app.pipeline_runner import run_pipeline_job


class FakePipeline:
    def __init__(self):
        self.called = False

    def process(self, input_file, target_languages, output_dir):
        self.called = True
        Path(output_dir).mkdir(parents=True, exist_ok=True)


def test_pipeline_runner_invokes_document_pipeline(tmp_path):
    pipeline = FakePipeline()
    source = tmp_path / "doc.pdf"
    source.write_text("PDF")

    run_pipeline_job(
        pipeline=pipeline,
        job_id="job-1",
        source_path=source,
        target_languages=["en"],
        output_root=tmp_path / "outputs",
    )
    assert pipeline.called
