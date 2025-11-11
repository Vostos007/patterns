from fastapi.testclient import TestClient

from app.main import create_app


def test_create_job_and_list(tmp_path):
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    app = create_app(
        uploads_dir=uploads,
        output_dir=outputs,
        auto_start_jobs=False,
        pipeline_factory=lambda: None,
    )
    client = TestClient(app)

    resp = client.post(
        "/jobs",
        files={"file": ("demo.pdf", b"%PDF-1.4", "application/pdf")},
        data={"target_languages": "en,fr"},
    )
    assert resp.status_code == 201
    job_id = resp.json()["job_id"]

    detail = client.get(f"/jobs/{job_id}").json()
    assert detail["status"] == "queued"
    assert detail["target_languages"] == ["en", "fr"]

    listing = client.get("/jobs").json()
    assert any(job["job_id"] == job_id for job in listing)
