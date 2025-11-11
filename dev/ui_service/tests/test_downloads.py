from fastapi.testclient import TestClient

from app.main import create_app


def test_download_endpoint_serves_artifact(tmp_path):
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    app = create_app(uploads_dir=uploads, output_dir=outputs)
    client = TestClient(app)

    resp = client.post(
        "/jobs",
        files={"file": ("sample.pdf", b"pdf", "application/pdf")},
        data={"target_languages": "en"},
    )
    job_id = resp.json()["job_id"]

    store = app.state.jobs
    artifact = outputs / job_id / "en"
    artifact.mkdir(parents=True, exist_ok=True)
    out_file = artifact / "sample_en.pdf"
    out_file.write_text("translated", encoding="utf-8")
    store.mark_completed(job_id, [out_file])

    download = client.get(f"/jobs/{job_id}/artifacts/en")
    assert download.status_code == 200
    assert download.content == b"translated"
