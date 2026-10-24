#!/usr/bin/env bash
# Start the API + both UIs on http://localhost:${PORT:-8000}
cd "$(dirname "$0")/.." && exec python3 -W ignore -m uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port "${PORT:-8000}"
