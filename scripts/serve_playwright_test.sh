#!/usr/bin/env bash
set -euo pipefail

# Start uvicorn with test environment variables, wait for it to be ready,
# run Playwright tests, then shut down the server.

PRESENCE_ONLINE_SECONDS="${PRESENCE_ONLINE_SECONDS:-3}"
export PRESENCE_ONLINE_SECONDS
export TEST_MODE=1

LOG="/tmp/uvicorn_playwright.log"
PIDFILE="/tmp/uvicorn_playwright.pid"

echo "Starting uvicorn with PRESENCE_ONLINE_SECONDS=$PRESENCE_ONLINE_SECONDS (logs -> $LOG)"
# Start uvicorn in background
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --log-level info >"$LOG" 2>&1 &
echo $! > "$PIDFILE"

# Wait for the server to accept connections (timeout ~30s)
for i in $(seq 1 30); do
  if curl -sSf http://127.0.0.1:8000/ >/dev/null 2>&1; then
    echo "Server is up (after ${i}s)"
    break
  fi
  sleep 1
done

if ! kill -0 $(cat "$PIDFILE") >/dev/null 2>&1; then
  echo "uvicorn process died unexpectedly. Dumping log:" >&2
  sed -n '1,200p' "$LOG" || true
  exit 1
fi

# Run Playwright tests
npx playwright test
RC=$?

echo "Playwright finished with exit code $RC. Stopping server..."
kill $(cat "$PIDFILE") >/dev/null 2>&1 || true
wait $(cat "$PIDFILE") 2>/dev/null || true

exit $RC
