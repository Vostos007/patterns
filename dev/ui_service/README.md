# KPS UI Service

FastAPI service that coordinates translation jobs for the Control Room UI.

## Prerequisites

- Python 3.9+
- `pip install -r requirements.txt` (FastAPI, uvicorn, python-multipart)

## Configuration

Environment variables (defaults shown):

```
UPLOADS_DIR=/tmp/kps_uploads
OUTPUT_DIR=/tmp/kps_outputs
AUTO_START_JOBS=true
PYTHONPATH=/path/to/repo/dev/PDF_PARSER_2.0  # required so UnifiedPipeline imports
```

## Running locally

```
cd dev/ui_service
PYTHONPATH="$PYTHONPATH:../PDF_PARSER_2.0" uvicorn app.main:app --reload --port 9000
```

### API

- `POST /jobs` – multipart upload, `target_languages="en,fr"`
- `GET /jobs` – list job statuses
- `GET /jobs/{job_id}` – job detail
- `GET /jobs/{job_id}/artifacts/{lang}` – download artifact

## Tests

```
cd dev/ui_service
python3 -m pytest -vv
```
