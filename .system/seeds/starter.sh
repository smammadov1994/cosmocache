#!/usr/bin/env bash
# Seed 5 general-purpose "starter" planets that fit almost any Claude user:
# writing, career, health, travel, learning. Use this for a fresh clone
# that isn't tech-focused.
#
# Run directly:
#     .system/seeds/starter.sh
#
# Or via the CLI:
#     cosmo seed starter
#
# Idempotent-ish: if a planet already exists, birth-planet.sh errors on that
# one and the loop continues with the rest.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
UNIVERSE_ROOT="${UNIVERSE_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
BIRTH="$UNIVERSE_ROOT/.system/skill/lib/birth-planet.sh"

if [[ ! -x "$BIRTH" ]]; then
  echo "error: birth-planet.sh not found or not executable at $BIRTH" >&2
  exit 2
fi

PLANETS=(
  "writing:Writing, tone, and everyday communication:writing,email,draft,tone,grammar,editing:Quill-Marrow:ink-soaked marshes where every sentence is fished up whole:comma splices:tone-shaping,draft-weaving"
  "career:Career, job hunting, resumes, interviews:career,resume,interview,job,linkedin:Ambitia Prime:a staircase-planet where every step is a role you outgrew:rejection letters:resume-forging,interview-foresight"
  "health:Health, fitness, sleep, nutrition notes:health,fitness,sleep,nutrition,habit:Vitalis:a breathing biome whose rivers are hydration and whose hills are REM cycles:skipped meals:sleep-charting,habit-tending"
  "travel:Travel, trips, places, packing, logistics:travel,trip,packing,itinerary,flight,hotel:Wayfare:a patchwork atlas that folds itself into a carry-on:expired itineraries:packing-sight,jetlag-foresight"
  "learning:Learning, books, courses, notes-to-self:learning,book,course,notes,study,concept:Mnemos:a library-moon whose shelves rearrange themselves at dawn:unread chapters:concept-linking,spaced-repetition"
)

echo "seeding 5 starter planets into $UNIVERSE_ROOT/planets/"
echo

for p in "${PLANETS[@]}"; do
  IFS=':' read -r slug domain kw name tag food abil <<< "$p"
  UNIVERSE_ROOT="$UNIVERSE_ROOT" "$BIRTH" "$slug" "$domain" "$kw" "$name" "$tag" "$food" "$abil" \
    || echo "  (skipped planet-$slug — see error above)" >&2
done

echo
echo "done. run: cosmo planets"
