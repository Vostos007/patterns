# KPS Control Room Dashboard

Next.js 16 + shadcn/ui dashboard for uploading localization jobs and monitoring progress.

## Getting Started

```
cd dev/ui_dashboard
npm install
npm run dev
```

The dev server runs on http://localhost:3050.

Set the backend URL via `.env.local`:

```
NEXT_PUBLIC_API_BASE=http://localhost:9000
```

## Scripts

- `npm run dev` – start Next.js dev server (port 3050)
- `npm run lint` – ESLint
- `npm run test` – Vitest + Testing Library
- `npm run build` – production build

## Components

UI primitives installed via `shadcn ui` CLI (`button`, `card`, `input`, `table`, `sonner`, etc.). Custom components live in `src/components`.
