#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f .env ]; then
  # shellcheck disable=SC1091
  source .env
fi

export PYTHONPATH="${PYTHONPATH:-}:../PDF_PARSER_2.0"
exec python3 -m uvicorn app.main:app --reload --port 9000
