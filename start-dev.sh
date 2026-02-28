#!/usr/bin/env bash
# PBAM local development start script (no Docker)
# Usage: ./start-dev.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# ── Cleanup on exit ───────────────────────────────────────────────────────────
BACKEND_PID=""
FRONTEND_PID=""
cleanup() {
  echo ""
  echo "Stopping services..."
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ── PostgreSQL check ──────────────────────────────────────────────────────────
if ! pg_isready -h localhost -q 2>/dev/null; then
  echo "ERROR: PostgreSQL is not running at localhost:5432"
  echo "Start it with: podman-compose up -d db  (or systemctl start postgresql)"
  exit 1
fi
echo "✓ PostgreSQL ready"

# ── Alembic migrations ────────────────────────────────────────────────────────
cd "$BACKEND_DIR"
echo "Running migrations..."
PYTHONPATH="$BACKEND_DIR/src" python3 -m alembic upgrade head
echo "✓ Migrations applied"

# ── Backend ───────────────────────────────────────────────────────────────────
echo "Starting backend on http://localhost:8000 ..."
PYTHONPATH="$BACKEND_DIR/src" python3 -m uvicorn pbam.main:app \
  --host 0.0.0.0 --port 8000 --reload \
  --reload-dir "$BACKEND_DIR/src" &
BACKEND_PID=$!
sleep 2
echo "✓ Backend PID=$BACKEND_PID"

# ── Frontend ──────────────────────────────────────────────────────────────────
cd "$FRONTEND_DIR"
if [[ ! -d node_modules ]]; then
  echo "Installing frontend dependencies..."
  npm install
fi
echo "Starting frontend on http://localhost:5173 ..."
npm run dev &
FRONTEND_PID=$!
echo "✓ Frontend PID=$FRONTEND_PID"

echo ""
echo "==================================="
echo "  PBAM running:"
echo "  Frontend  →  http://localhost:5173"
echo "  API docs  →  http://localhost:8000/docs"
echo "==================================="
echo "  Press Ctrl+C to stop"
echo ""

wait
