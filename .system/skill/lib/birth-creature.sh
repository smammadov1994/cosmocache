#!/usr/bin/env bash
# Usage: birth-creature.sh <planet-slug> <creature-slug> <lore-name> <expertise> <lore-tagline>
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

[[ $# -eq 5 ]] || die "usage: birth-creature.sh <planet-slug> <creature-slug> <lore-name> <expertise> <lore-tagline>"

PLANET_SLUG="$(slugify "$1")"
CREATURE_SLUG="$(slugify "$2")"
LORE_NAME="$3"
EXPERTISE="$4"
TAGLINE="$5"

PLANET_NAME="planet-$PLANET_SLUG"
require_planet_exists "$PLANET_NAME"

CREATURE_PATH="$UNIVERSE_ROOT/planets/$PLANET_NAME/creatures/$CREATURE_SLUG.md"
[[ ! -e "$CREATURE_PATH" ]] || die "creature '$CREATURE_SLUG' already exists on $PLANET_NAME"

# Read current generation from planet.md frontmatter
GEN="$(grep -E '^generation:' "$UNIVERSE_ROOT/planets/$PLANET_NAME/planet.md" | awk '{print $2}')"
TODAY="$(today_iso)"

cat > "$CREATURE_PATH" <<CREATURE
---
name: $CREATURE_SLUG
planet: $PLANET_NAME
born: $TODAY
born_in_generation: $GEN
expertise: $EXPERTISE
sessions: 0
last_seen: $TODAY
---

# $LORE_NAME
*$TAGLINE*

## Distilled Wisdom
<!-- Short, high-signal summary rewritten on each session. -->

## Journal
<!-- Append-only session log. -->
CREATURE

echo "$CREATURE_PATH"
