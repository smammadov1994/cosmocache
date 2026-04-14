#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/lib/assert.sh"

BIRTH_PLANET="$DIR/../skill/lib/birth-planet.sh"
BIRTH_CREATURE="$DIR/../skill/lib/birth-creature.sh"

echo "test_birth_creature"

UNIVERSE_ROOT="$(make_test_universe)"
export UNIVERSE_ROOT

"$BIRTH_PLANET" "react" "React patterns" "react,hooks" "Verdant-Hook" "canopies" "re-renders" "reconciliation"

# Test 1: creates creature file with frontmatter
"$BIRTH_CREATURE" "react" "jimbo-the-reactor" "Jimbo the React-tor" "hooks, state management" "A wiry creature with eight fingers, each a useState."
C="$UNIVERSE_ROOT/planets/planet-react/creatures/jimbo-the-reactor.md"
assert_file_exists "$C"
assert_file_contains "$C" "name: jimbo-the-reactor"
assert_file_contains "$C" "planet: planet-react"
assert_file_contains "$C" "born_in_generation: gen-0"
assert_file_contains "$C" "expertise: hooks, state management"
assert_file_contains "$C" "sessions: 0"
assert_file_contains "$C" "# Jimbo the React-tor"
assert_file_contains "$C" "eight fingers"
assert_file_contains "$C" "## Distilled Wisdom"
assert_file_contains "$C" "## Journal"
pass "creates creature.md with correct frontmatter"

# Test 2: refuses duplicate
set +e
"$BIRTH_CREATURE" "react" "jimbo-the-reactor" "dup" "dup" "dup" 2>/dev/null
RC=$?
set -e
assert_eq "$RC" "1" "should refuse dup"
pass "refuses duplicate creature"

# Test 3: refuses nonexistent planet
set +e
"$BIRTH_CREATURE" "nonexistent" "x" "x" "x" "x" 2>/dev/null
RC=$?
set -e
assert_eq "$RC" "1"
pass "refuses unknown planet"

rm -rf "$UNIVERSE_ROOT"
echo "PASS: test_birth_creature"
