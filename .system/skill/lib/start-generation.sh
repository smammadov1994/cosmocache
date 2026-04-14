#!/usr/bin/env bash
# Usage: start-generation.sh <planet-slug> <trigger> <summary-body>
# Archives the active generation, writes gen-N-summary.md, and opens gen-(N+1).md.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

[[ $# -eq 3 ]] || die "usage: start-generation.sh <planet-slug> <trigger> <summary-body>"

PLANET_SLUG="$(slugify "$1")"
TRIGGER="$2"
SUMMARY="$3"

PLANET_NAME="planet-$PLANET_SLUG"
require_planet_exists "$PLANET_NAME"

PLANET_MD="$UNIVERSE_ROOT/planets/$PLANET_NAME/planet.md"
GEN_DIR="$UNIVERSE_ROOT/planets/$PLANET_NAME/generations"

CURRENT="$(grep -E '^generation:' "$PLANET_MD" | awk '{print $2}')"
CURRENT_N="${CURRENT#gen-}"
NEXT_N="$((CURRENT_N + 1))"
NEXT="gen-$NEXT_N"
TODAY="$(today_iso)"

CURRENT_FILE="$GEN_DIR/$CURRENT.md"
[[ -f "$CURRENT_FILE" ]] || die "active gen file missing: $CURRENT_FILE"

# Flip status in current gen file
# macOS sed: use -i '' for in-place
sed -i '' 's/^status: active$/status: archived/' "$CURRENT_FILE"

# Write summary
cat > "$GEN_DIR/$CURRENT-summary.md" <<SUM
---
generation: $CURRENT
summarized_at: $TODAY
trigger: "$TRIGGER"
---

# $CURRENT — Summary

$SUMMARY
SUM

# Open next gen
cat > "$GEN_DIR/$NEXT.md" <<NEXTF
---
generation: $NEXT
started: $TODAY
trigger: "$TRIGGER"
status: active
---

# Generation $NEXT_N — $TRIGGER

## New Creatures

## Key Additions
NEXTF

# Point planet.md at the new gen
sed -i '' "s/^generation: $CURRENT$/generation: $NEXT/" "$PLANET_MD"

echo "$NEXT"
