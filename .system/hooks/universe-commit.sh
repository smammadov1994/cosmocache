#!/usr/bin/env bash
# Stop hook. Nudges Claude to persist meaningful knowledge via /universe remember.
set -euo pipefail
cat <<'MSG'
---
Universe persistence check:
If this session produced new, non-obvious knowledge worth keeping across
sessions (a decision, a pattern, a gotcha, a domain fact), call
`/universe remember` before exiting. Otherwise, no action needed.
MSG
