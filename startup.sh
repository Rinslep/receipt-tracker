#!/usr/bin/env bash
# startup.sh – Development startup script for receipt-tracker
# Activates the virtual environment and launches the FastAPI dev server.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtual environment
source "$PROJECT_ROOT/.venv/bin/activate"

# Load environment variables from .env if present
if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

echo "Starting Receipt Tracker API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
