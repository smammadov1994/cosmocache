#!/bin/sh
set -eu

# Compile the universe from the /data bind mount (read-only) into the
# static directory nginx serves. We do an initial compile at start, then
# a lightweight rebuild loop in the background so that subagent activity
# (planet content edits + rows in enigma/evolutions.db) surfaces to the
# dashboard within ~2s without needing a real backend. Each rebuild
# emits both universe.json and evolutions.json side-by-side.
DATA_DIR="${UNIVERSE_ROOT:-/data}"
OUT_FILE="/usr/share/nginx/html/universe.json"
REBUILD_INTERVAL="${REBUILD_INTERVAL:-2}"

rebuild() {
  python3 /opt/build_universe.py "$DATA_DIR" "$OUT_FILE" >/dev/null 2>&1 || true
}

if [ -d "$DATA_DIR" ]; then
  echo "[entrypoint] compiling universe from $DATA_DIR -> $OUT_FILE"
  python3 /opt/build_universe.py "$DATA_DIR" "$OUT_FILE"
  echo "[entrypoint] starting rebuild loop every ${REBUILD_INTERVAL}s"
  (
    while :; do
      sleep "$REBUILD_INTERVAL"
      rebuild
    done
  ) &
else
  echo "[entrypoint] warning: $DATA_DIR not mounted; writing empty universe"
  printf '{"planets":[],"enigma":{"name":"Enigma the One","glossary_md":""}}' > "$OUT_FILE"
fi

exec "$@"
