# Hollywool Patterns Workspace

This workspace now includes a translation Control Room composed of:

- **dev/ui_service** – FastAPI backend handling uploads, job queueing, and artifact downloads.
- **dev/ui_dashboard** – Next.js + shadcn/ui dashboard (port 3050) for uploading documents and monitoring translation status.
- Existing pipelines remain under `dev/PDF_parser` and `dev/PDF_PARSER_2.0`.

## Workspace Layout

To keep the root tidy, only the following entries stay in view:

- `README.md`, `.git*`, `.github/`
- `docs/` (all handbooks + plans)
- `dev/` (pipelines, UI apps, tooling)
- `to_translate/`, `translations/`
- `глоссарий.json`

Internal automation configs such as the former `.claude/` and `.serena/` directories now live under `dev/tools/claude` and `dev/tools/serena`. Coverage outputs (`.coverage`, `htmlcov/`) are deleted after every test run and ignored by git, so the repo root always highlights just the IO folders and documentation.

## Translation IO (always visible at repo root)

- `to_translate/` – drop incoming PDF/DOCX files here. The daemon, CLI (`kps daemon`) and UI service all watch this folder and automatically create `processed/` and `failed/` inside it. Keep sample sources (e.g., `КАРДИГАН peer gynt.docx`) here rather than under `dev/PDF_PARSER_2.0/runtime/input/`.
- `translations/` – finished artifacts land here, grouped per document/language exactly as the pipeline already does (`pattern_EN/pattern_EN.pdf`, etc.).

Both directories are tracked via `.gitkeep`, while their contents stay ignored so you never accidentally commit customer documents. After each verified run, follow the [Repo Hygiene Runbook](docs/runbooks/repo-hygiene.md) to:

- wipe `dev/PDF_PARSER_2.0/runtime/input/`, `runtime/inter/`, and `runtime/tmp/`
- trim `dev/PDF_PARSER_2.0/runtime/output/<doc>/` down to the latest successful iteration (v044 right now)
- keep `to_translate/` + `translations/` tidy so the FastAPI UI and CLI stay in sync

The runbook also documents `scripts/cleanup_runtime.py`, which automates the reset in one command.

## UI Service

```
cd dev/ui_service
cp .env.example .env
./start.sh
```

Environment variables:
- `UPLOADS_DIR` (default `<repo>/to_translate`)
- `OUTPUT_DIR` (default `<repo>/translations`)
- `AUTO_START_JOBS=true` to execute pipeline immediately
- `KPS_PIPELINE_IMPLEMENTATION=stub` for the lightweight copier pipeline (great for demos)

## Dashboard (port 3050)

```
cd dev/ui_dashboard
cp .env.local.example .env.local
npm install
./start.sh  # http://localhost:3050
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
