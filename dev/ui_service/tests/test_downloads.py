from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_download_endpoint_serves_artifact(tmp_path):
    uploads = tmp_path / "u"
    outputs = tmp_path / "o"
    app = create_app(uploads_dir=str(uploads), output_dir=str(outputs), auto_start_jobs=False)
    client = TestClient(app)

    store = app.state.jobs
    source = tmp_path / "demo.pdf"
    source.write_text("PDF", encoding="utf-8")
    job = store.create_job(filename="demo.pdf", source_path=source, target_languages=["en"])

    artifact_path = outputs / job.job_id / "en" / "demo_en.pdf"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("PDF", encoding="utf-8")
    store.mark_completed(job.job_id, [artifact_path])

    resp = client.get(f"/jobs/{job.job_id}/artifacts/en")
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].startswith("attachment;")
