#!/usr/bin/env bash
# SessionStart hook. Injects Enigma's glossary and any anchored planet.md into context.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../skill/lib/common.sh"

GLOSS="$UNIVERSE_ROOT/enigma/glossary.md"
[[ -f "$GLOSS" ]] || { echo "universe: glossary missing — system not initialized."; exit 0; }

# Emit glossary
cat "$GLOSS"
echo

# Anchor detection: walk planets, check anchor_paths for $PWD match
CWD="${PWD}"
ANCHORED=""
if [[ -d "$UNIVERSE_ROOT/planets" ]]; then
  for p in "$UNIVERSE_ROOT/planets"/*/; do
    [[ -d "$p" ]] || continue
    PMD="$p/planet.md"
    [[ -f "$PMD" ]] || continue
    # Read anchor_paths line: "anchor_paths: [a, b, c]"
    LINE="$(grep -E '^anchor_paths:' "$PMD" || true)"
    [[ -n "$LINE" ]] || continue
    # Extract content between brackets
    INNER="${LINE#*[}"; INNER="${INNER%]*}"
    [[ -n "$INNER" ]] || continue
    IFS=',' read -ra PATHS <<< "$INNER"
    for raw in "${PATHS[@]}"; do
      path="$(echo "$raw" | xargs)"  # trim
      [[ -z "$path" ]] && continue
      if [[ "$CWD" == "$path"* ]]; then
        ANCHORED="$(basename "$p")"
        echo "---"
        echo "# Anchored Planet ($ANCHORED)"
        echo
        cat "$PMD"
        echo
        break 2
      fi
    done
  done
fi

PLANET_COUNT=$(find "$UNIVERSE_ROOT/planets" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
echo "---"
echo "Enigma consulted. $PLANET_COUNT planets known. Anchored to: ${ANCHORED:-none}."
