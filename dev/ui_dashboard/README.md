# UI Dashboard (Next.js 16)

Web dashboard for the Hollywool Translation Control Room. It uploads PDF/DOCX files
to the FastAPI service, polls `/jobs`, and renders download buttons pointing at
`translations/` artifacts.

## Setup

```bash
cd dev/ui_dashboard
cp .env.local.example .env.local
npm install
npm run dev
```

`NEXT_PUBLIC_API_BASE` must point at the FastAPI server (default `http://localhost:9000`).

## Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Start Next.js dev server on port 3050 |
| `npm run lint` | Run eslint using Next config |
| `npm run test` | Jest + React Testing Library suite |
| `npm run build` | Production build (Turbopack) |

## Tests

The test suite lives in `src/__tests__`. Run `npm run test` and add more RTL cases
as the dashboard grows.
