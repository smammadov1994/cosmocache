#!/usr/bin/env bash
# Usage: update-glossary.sh <planet-slug> <why-last-modified>
# Inserts a row for this planet into enigma/glossary.md, or updates the existing row.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

[[ $# -eq 2 ]] || die "usage: update-glossary.sh <planet-slug> <why-last-modified>"

PLANET_SLUG="$(slugify "$1")"
WHY="$2"
PLANET_NAME="planet-$PLANET_SLUG"
require_planet_exists "$PLANET_NAME"

PLANET_MD="$UNIVERSE_ROOT/planets/$PLANET_NAME/planet.md"
GLOSS="$UNIVERSE_ROOT/enigma/glossary.md"
TODAY="$(today_iso)"

# Extract fields from planet.md
DOMAIN="$(awk -F': ' '/^domain:/ {sub(/^domain: /,""); print; exit}' "$PLANET_MD")"
GEN="$(awk '/^generation:/ {print $2; exit}' "$PLANET_MD")"
KEYWORDS="$(awk -F': ' '/^keywords:/ {sub(/^keywords: /,""); print; exit}' "$PLANET_MD")"
KEYWORDS="${KEYWORDS#[}"; KEYWORDS="${KEYWORDS%]}"
CREATURE_COUNT="$(ls -1 "$UNIVERSE_ROOT/planets/$PLANET_NAME/creatures" 2>/dev/null | wc -l | tr -d ' ')"

ROW="| $PLANET_NAME | $DOMAIN | $KEYWORDS | $TODAY | $GEN | $CREATURE_COUNT | $WHY |"

# Remove any existing row for this planet
TMP="$(mktemp)"
grep -v "^| $PLANET_NAME |" "$GLOSS" > "$TMP" || true
mv "$TMP" "$GLOSS"

# Append the fresh row (before the trailing blank line, if any)
# Simple approach: just append at end.
echo "$ROW" >> "$GLOSS"
