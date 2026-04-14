#!/usr/bin/env bash
# Run every test_*.sh in this directory. Fail fast on first failing test.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

FAILED=0
for t in "$DIR"/test_*.sh; do
  echo "▶ running $(basename "$t")"
  if "$t"; then
    echo "  OK"
  else
    echo "  FAILED"
    FAILED=1
  fi
  echo
done

if [[ "$FAILED" -eq 1 ]]; then
  echo "✗ at least one test failed"
  exit 1
fi
echo "✓ all tests passed"
