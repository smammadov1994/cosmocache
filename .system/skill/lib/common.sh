#!/usr/bin/env bash
# Shared helpers for universe skill scripts.
# Source this from every script: `source "$(dirname "$0")/common.sh"`

set -euo pipefail

# Resolve UNIVERSE_ROOT. Honors env override for tests.
resolve_universe_root() {
  if [[ -n "${UNIVERSE_ROOT:-}" ]]; then
    echo "$UNIVERSE_ROOT"
  else
    echo "/Users/bot/universe"
  fi
}

UNIVERSE_ROOT="$(resolve_universe_root)"

# today_iso — returns YYYY-MM-DD
today_iso() {
  date +%Y-%m-%d
}

# slugify <string> — lowercase, spaces → hyphens, strip non-[a-z0-9-]
slugify() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-|-$//g'
}

# die <msg> — exit 1 with message
die() {
  echo "universe: $1" >&2
  exit 1
}

# planet_dir <planet-name> — echoes absolute path
planet_dir() {
  echo "$UNIVERSE_ROOT/planets/$1"
}

# require_planet_exists <planet-name>
require_planet_exists() {
  local p
  p="$(planet_dir "$1")"
  [[ -d "$p" ]] || die "planet '$1' does not exist at $p"
}
