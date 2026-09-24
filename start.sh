#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

# Start backend API (includes in-process judge worker)
cd "$ROOT/backend"
PYTHONPATH="$ROOT/backend" python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend (exposed preview port, proxies /api to backend)
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait $FRONTEND_PID
