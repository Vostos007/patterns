# Hollywool Patterns Workspace

This workspace now includes a translation Control Room composed of:

- **dev/ui_service** – FastAPI backend handling uploads, job queueing, and artifact downloads.
- **dev/ui_dashboard** – Next.js + shadcn/ui dashboard (port 3050) for uploading documents and monitoring translation status.
- Existing pipelines remain under `dev/PDF_parser` and `dev/PDF_PARSER_2.0`.

## UI Service

```
cd dev/ui_service
pip install -r requirements.txt
PYTHONPATH="$PYTHONPATH:../PDF_PARSER_2.0" uvicorn app.main:app --reload --port 9000
```

Environment variables:
- `UPLOADS_DIR` (default `/tmp/kps_uploads`)
- `OUTPUT_DIR` (default `/tmp/kps_outputs`)
- `AUTO_START_JOBS=true` to execute pipeline immediately

## Dashboard (port 3050)

```
cd dev/ui_dashboard
npm install
npm run dev  # http://localhost:3050
```

Create `.env.local`:
```
NEXT_PUBLIC_API_BASE=http://localhost:9000
```

Scripts:
- `npm run lint`
- `npm run test`
- `npm run build`

## Tests

Backend:
```
cd dev/ui_service
python3 -m pytest -vv
```

Frontend:
```
cd dev/ui_dashboard
npm run lint
npm run test
```
