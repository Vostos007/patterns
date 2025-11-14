# Translation Control Room UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship a localhost web UI where operators drop a PDF/DOCX, trigger the KPS pipeline, watch progress, and download translated artifacts.

**Architecture:** Wrap the existing Python pipeline with a FastAPI job service that marshals uploads into the root-level `to_translate/` folder and writes finished artifacts to `translations/`, exposes status/download endpoints, and emits structured events. A Next.js + shadcn/ui dashboard talks to this backend via REST, offering drag-and-drop upload, live status, and download cards for each target language.

**Tech Stack:** FastAPI + Uvicorn, Pydantic models, pytest, Next.js 14 (App Router) + shadcn/ui + Tailwind, axios/fetch, WebSockets (optional SSE) for live updates.

---

### Task 1: Bootstrap API service skeleton

**Files:**
- Create: `dev/ui_service/app/main.py`
- Create: `dev/ui_service/app/schemas.py`
- Create: `dev/ui_service/app/jobs.py`
- Test: `dev/ui_service/tests/test_health.py`

**Step 1: Write the failing test**
```python
# dev/ui_service/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import create_app

def test_health_endpoint():
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

**Step 2: Run test to verify it fails**
Run: `cd dev/ui_service && pytest tests/test_health.py -vv`
Expected: Module import error.

**Step 3: Write minimal implementation**
```python
# dev/ui_service/app/main.py
from fastapi import FastAPI

def create_app():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

app = create_app()
```
Add `schemas.py` placeholders (JobCreate, JobStatus) and `jobs.py` with `JobStore` class skeleton.

**Step 4: Run test to verify it passes**
Run: `cd dev/ui_service && pytest tests/test_health.py -vv`
Expected: PASS.

**Step 5: Commit**
```bash
git add dev/ui_service/app dev/ui_service/tests/test_health.py
git commit -m "feat: bootstrap ui service skeleton"
```

---

### Task 2: Implement job submission + storage pipeline

**Files:**
- Modify: `dev/ui_service/app/jobs.py`
- Modify: `dev/ui_service/app/schemas.py`
- Modify: `dev/ui_service/app/main.py`
- Test: `dev/ui_service/tests/test_jobs.py`
- Config: `dev/ui_service/.env.example`

**Step 1: Write the failing test**
```python
# dev/ui_service/tests/test_jobs.py
from fastapi.testclient import TestClient
from pathlib import Path
from app.main import create_app

UPLOADS = Path("/tmp/kps_tests/uploads")
OUTPUTS = Path("/tmp/kps_tests/output")

CLIENT = TestClient(create_app(uploads_dir=str(UPLOADS), output_dir=str(OUTPUTS)))

def test_create_job_and_list():
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
```

**Step 2: Run test to verify it fails**
Run: `cd dev/ui_service && pytest tests/test_jobs.py -vv`
Expected: FAIL (endpoint missing).

**Step 3: Write minimal implementation**
- `schemas.JobCreate`, `schemas.JobStatus`, `schemas.Artifact` with pydantic fields.
- `jobs.JobStore` manages an in-memory dict, persists uploads to `uploads_dir`, creates output staging folder, enqueues background task placeholder.
- `main.py` adds endpoints:
  - `POST /jobs` (multipart) -> store file, create job record, schedule pipeline runner via `BackgroundTasks` or `asyncio.create_task` calling helper (stub for now).
  - `GET /jobs` list (paginated) and `GET /jobs/{job_id}` detail.

**Step 4: Run test to verify it passes**
Run: `cd dev/ui_service && pytest tests/test_jobs.py -vv`
Expected: PASS.

**Step 5: Commit**
```bash
git add dev/ui_service/app/*.py dev/ui_service/tests/test_jobs.py dev/ui_service/.env.example
git commit -m "feat: add job submission endpoints"
```

---

### Task 3: Wire backend to actual KPS pipeline execution

**Files:**
- Modify: `dev/ui_service/app/jobs.py`
- Modify: `dev/ui_service/app/main.py`
- Add: `dev/ui_service/app/pipeline_runner.py`
- Test: `dev/ui_service/tests/test_pipeline_runner.py`

**Step 1: Write the failing test**
```python
# dev/ui_service/tests/test_pipeline_runner.py
from pathlib import Path
from app.pipeline_runner import run_pipeline_job

class FakePipeline:
    def __init__(self):
        self.called = False
    def run(self, input_file, target_languages, output_dir):
        self.called = True
        Path(output_dir).mkdir(parents=True, exist_ok=True)


def test_pipeline_runner_invokes_document_pipeline(tmp_path):
    pipeline = FakePipeline()
    run_pipeline_job(
        pipeline=pipeline,
        job_id="job-1",
        source_path=tmp_path / "doc.pdf",
        target_languages=["en"],
        output_root=tmp_path / "outputs",
    )
    assert pipeline.called
```

**Step 2: Run test to verify it fails**
Run: `cd dev/ui_service && pytest tests/test_pipeline_runner.py -vv`
Expected: FAIL.

**Step 3: Write minimal implementation**
- `pipeline_runner.py` exposes `run_pipeline_job(...)` that instantiates `UnifiedPipeline` (reuse config) once, runs `.process()` placing outputs under `output_root/<job_id>/<lang>`.
- Update `JobStore` to launch background thread/process (e.g., `asyncio.to_thread`) calling `run_pipeline_job`; update status transitions (queued → processing → succeeded/failed) and capture artifact metadata paths.
- Extend `schemas.JobStatus` to include `artifacts: List[Artifact]` with download URLs.

**Step 4: Run tests**
`cd dev/ui_service && pytest tests/test_pipeline_runner.py tests/test_jobs.py -vv`
Expected: PASS (mock pipeline is called, job status transitions still pass).

**Step 5: Commit**
```bash
git add dev/ui_service/app/jobs.py dev/ui_service/app/pipeline_runner.py dev/ui_service/tests/test_pipeline_runner.py
git commit -m "feat: connect job queue to KPS pipeline"
```

---

### Task 4: Provide download + progress endpoints

**Files:**
- Modify: `dev/ui_service/app/main.py`
- Modify: `dev/ui_service/app/jobs.py`
- Modify: `dev/ui_service/app/schemas.py`
- Test: `dev/ui_service/tests/test_downloads.py`

**Step 1: Write the failing test**
```python
# dev/ui_service/tests/test_downloads.py
from fastapi.testclient import TestClient
from app.main import create_app

def test_download_endpoint_serves_artifact(tmp_path):
    app = create_app(uploads_dir=str(tmp_path / "u"), output_dir=str(tmp_path / "o"))
    client = TestClient(app)
    # seed fake job
    store = app.state.jobs
    job = store.create_job(name="demo.pdf", source_path=tmp_path / "demo.pdf", target_languages=["en"])
    artifact_path = tmp_path / "o" / job.job_id / "en" / "demo_en.pdf"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("PDF", encoding="utf-8")
    store.mark_completed(job.job_id, [artifact_path])

    resp = client.get(f"/jobs/{job.job_id}/artifacts/en")
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].startswith("attachment;")
```

**Step 2: Run test to verify it fails**
Run: `cd dev/ui_service && pytest tests/test_downloads.py -vv`
Expected: FAIL.

**Step 3: Implementation**
- `JobStore.mark_completed` accepts list of `Path` objects, builds artifact records with MIME guesses.
- Add `GET /jobs/{job_id}/artifacts/{language}` returning `FileResponse` for stored artifact.
- Add `GET /jobs/{job_id}/logs` stream placeholder (JSON lines) to surface pipeline messages (even if stub).
- Ensure `JobStatus` includes `logs_url` and `download_urls` per language.

**Step 4: Run tests**
`cd dev/ui_service && pytest tests/test_downloads.py tests/test_jobs.py -vv`

**Step 5: Commit**
```bash
git add dev/ui_service/app/*.py dev/ui_service/tests/test_downloads.py
git commit -m "feat: add artifact downloads and status metadata"
```

---

### Task 5: Build shadcn/ui dashboard (Next.js App Router)

**Files:**
- Create: `dev/ui_dashboard/package.json`, `tsconfig.json`, `next.config.js`
- Create: `dev/ui_dashboard/app/(dashboard)/layout.tsx`
- Create: `dev/ui_dashboard/app/(dashboard)/page.tsx`
- Add shadcn components via `components/ui/button.tsx`, etc.
- Config: `dev/ui_dashboard/tailwind.config.ts`, `postcss.config.js`
- Test: `dev/ui_dashboard/src/__tests__/upload.test.tsx`

**Step 1: Write failing test (React Testing Library)**
```tsx
// dev/ui_dashboard/src/__tests__/upload.test.tsx
import { render, screen } from "@testing-library/react";
import UploadPanel from "../../components/upload-panel";

test("renders upload button", () => {
  render(<UploadPanel />);
  expect(screen.getByText(/Upload Document/i)).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**
```
cd dev/ui_dashboard
npm install
npm test
```
Expected: FAIL (component missing).

**Step 3: Implementation**
- Scaffold Next.js 14 app with Tailwind + shadcn (use `npx create-next-app@latest dev/ui_dashboard`).
- Add `.env.local` with `NEXT_PUBLIC_API_URL=http://localhost:9000`.
- Implement `components/upload-panel.tsx` using shadcn `Card`, `Input`, `Button`, `Progress`, calling FastAPI using `fetch` with `FormData`; show status list via `useSWR` polling `/jobs`.
- Add downloads table with `Download` buttons linking to `/jobs/{id}/artifacts/{lang}`.
- Provide `app/page.tsx` combining `UploadPanel` and `JobsTable`.

**Step 4: Run tests + lint**
```
cd dev/ui_dashboard
npm run lint
npm test
npm run build
```

**Step 5: Commit**
```bash
git add dev/ui_dashboard
git commit -m "feat: add shadcn dashboard for translation jobs"
```

---

### Task 6: Wire backend & frontend dev workflows + docs

**Files:**
- Add: `dev/ui_service/README.md`
- Add: `dev/ui_dashboard/README.md`
- Update: root `README.md`
- Add script: `dev/ui_service/start.sh`, `dev/ui_dashboard/start.sh`
- Test: N/A (docs)

**Steps:**
1. Document how to create `.env` for FastAPI (`UPLOADS_DIR`, `OUTPUT_DIR`, `PIPELINE_CONFIG`).
2. Document commands to run FastAPI (`uvicorn app.main:app --reload --port 9000`).
3. Document how to run Next.js dev server (`npm run dev`), list environment variables.
4. Update root README with “UI Control Room” section linking to both READMEs and describing end-to-end flow.
5. Commit docs+scripts.

---

Plan complete and saved to `docs/plans/2025-11-11-localization-ui.md`. Two execution options:

1. **Subagent-Driven (this session)** – dispatch fresh subagent per task with reviews between steps.
2. **Parallel Session (separate)** – new session using superpowers:executing-plans.

Which approach?
