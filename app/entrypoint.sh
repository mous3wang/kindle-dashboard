#!/bin/sh
# Start the HTTP server, then regenerate the dashboard image every
# GENERATE_INTERVAL seconds (default 1800). A failed generation never
# kills the loop: the previous image keeps being served.
set -u
python3 /app/serve.py &
while true; do
    python3 /app/generate.py || echo "generate failed, keeping previous image" >&2
    sleep "${GENERATE_INTERVAL:-1800}"
done
