from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


UPLOADS = Path("/tmp/kps_tests/uploads")
OUTPUTS = Path("/tmp/kps_tests/output")


CLIENT = TestClient(
    create_app(
        uploads_dir=str(UPLOADS),
        output_dir=str(OUTPUTS),
        auto_start_jobs=False,
    )
)


def test_create_job_and_list(tmp_path):
    response = CLIENT.post(
        "/jobs",
        files={"file": ("demo.pdf", b"%PDF-1.4", "application/pdf")},
        data={"target_languages": "en,fr"},
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    resp = CLIENT.get(f"/jobs/{job_id}")
    data = resp.json()
    assert data["status"] in {"queued", "processing"}
    assert sorted(data["target_languages"]) == ["en", "fr"]
