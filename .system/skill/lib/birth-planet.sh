#!/usr/bin/env bash
# Usage: birth-planet.sh <slug> <domain> <keywords-csv> <lore-name> <lore-tagline> <food-metaphor> <ability-list-csv>
# Example: birth-planet.sh react "React & frontend patterns" "react,hooks,jsx" "Verdant-Hook" "dense canopies" "re-renders" "reconciliation,prop-sight"

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

[[ $# -eq 7 ]] || die "usage: birth-planet.sh <slug> <domain> <keywords-csv> <lore-name> <lore-tagline> <food-metaphor> <ability-list-csv>"

SLUG="$(slugify "$1")"
DOMAIN="$2"
KEYWORDS_CSV="$3"
LORE_NAME="$4"
LORE_TAGLINE="$5"
FOOD="$6"
ABILITIES_CSV="$7"

PLANET_NAME="planet-$SLUG"
PLANET_PATH="$UNIVERSE_ROOT/planets/$PLANET_NAME"

[[ ! -e "$PLANET_PATH" ]] || die "planet '$PLANET_NAME' already exists at $PLANET_PATH"

mkdir -p "$PLANET_PATH/creatures" "$PLANET_PATH/generations"

# Format keywords list: "a,b,c" -> "[a, b, c]"
KEYWORDS_FMT="[$(echo "$KEYWORDS_CSV" | sed 's/,/, /g')]"

# Format abilities as markdown bullets
ABILITIES_MD=""
IFS=',' read -ra ABIL <<< "$ABILITIES_CSV"
for a in "${ABIL[@]}"; do
  ABILITIES_MD+="- ${a# }"$'\n'
done

TODAY="$(today_iso)"

cat > "$PLANET_PATH/planet.md" <<PLANET
---
name: $PLANET_NAME
born: $TODAY
domain: $DOMAIN
keywords: $KEYWORDS_FMT
generation: gen-0
anchor_paths: []
---

# Planet $LORE_NAME
*$LORE_TAGLINE*

## Food
The creatures here feed on **$FOOD**.
Birth cycle: new creatures spawn when a distinct sub-expertise first appears.

## Unique Abilities
$ABILITIES_MD

## Creatures
Dynamically populated — see \`creatures/\` directory.
PLANET

cat > "$PLANET_PATH/generations/gen-0.md" <<GEN
---
generation: gen-0
started: $TODAY
trigger: "planet birth"
status: active
---

# Generation 0 — The First Era
*Seeded at the birth of $PLANET_NAME.*

## New Creatures

## Key Additions
GEN

echo "$PLANET_PATH"

# Install / refresh the launchd cron so this new planet gets a tick.
# Silent on success — log any failure to stderr but don't abort birth.
CRON_INSTALL="$UNIVERSE_ROOT/scripts/install_evolution_cron.sh"
if [[ -x "$CRON_INSTALL" ]]; then
  if ! UNIVERSE_ROOT="$UNIVERSE_ROOT" "$CRON_INSTALL" >/dev/null 2>&1; then
    echo "warning: install_evolution_cron.sh failed; run it manually" >&2
  fi
fi
