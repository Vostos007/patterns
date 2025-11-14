# UI Service (FastAPI)

This service exposes upload + status endpoints around the KPS pipeline. It watches
`to_translate/` for incoming files and writes artifacts to `translations/`.

## Quick start

```bash
cd dev/ui_service
python3 -m venv .venv && source .venv/bin/activate
pip install -r ../PDF_PARSER_2.0/requirements.txt  # reuse pipeline deps
pip install fastapi uvicorn
cp .env.example .env
source .env
PYTHONPATH="$PYTHONPATH:../PDF_PARSER_2.0" uvicorn app.main:app --reload --port 9000
```

### Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `UPLOADS_DIR` | `<repo>/to_translate` | Directory used to persist incoming files |
| `OUTPUT_DIR` | `<repo>/translations` | Destination for pipeline artifacts |
| `AUTO_START_JOBS` | `true` | Run pipeline automatically once upload finishes |
| `KPS_PIPELINE_IMPLEMENTATION` | `real` | Set to `stub` for the lightweight dev pipeline |

With `KPS_PIPELINE_IMPLEMENTATION=stub` the job runner simply copies the source
file into each target-language folder, which is perfect for verifying the UI
without running the full ML toolchain.

## API surface

- `GET /health` — simple readiness check
- `POST /jobs` — multipart upload with `file` and comma-delimited `target_languages`
- `GET /jobs` — list every job
- `GET /jobs/{job_id}` — full status with download/log URLs
- `GET /jobs/{job_id}/artifacts/{language}` — download first artifact for a language
- `GET /jobs/{job_id}/logs` — JSON list of pipeline log lines

## Tests

```
cd dev/ui_service
python3 -m pytest -q
```
