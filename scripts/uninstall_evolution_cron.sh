#!/bin/bash
# Remove all evolution launchd plists. Safe to re-run.
set -eu

AGENTS_DIR="$HOME/Library/LaunchAgents"

removed=0
shopt -s nullglob 2>/dev/null || true
for plist in "$AGENTS_DIR/ai.cosmocache.evolution".*.plist \
             "$AGENTS_DIR/ai.cosmocache.enigma.plist"; do
  [ -f "$plist" ] || continue
  launchctl unload "$plist" 2>/dev/null || true
  rm -f "$plist"
  echo "removed: $(basename "$plist")"
  removed=$((removed+1))
done

echo "removed ${removed} plist(s)"
