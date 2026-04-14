#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/lib/assert.sh"

SCRIPT="$DIR/../skill/lib/birth-planet.sh"

echo "test_birth_planet"

# Test 1: creates planet directory with planet.md
UNIVERSE_ROOT="$(make_test_universe)"
export UNIVERSE_ROOT
"$SCRIPT" "react" "React & frontend patterns" "react,hooks,jsx" "Verdant-Hook" "A world of dense canopies" "re-renders" "reconciliation-at-speed"
assert_dir_exists "$UNIVERSE_ROOT/planets/planet-react"
assert_file_exists "$UNIVERSE_ROOT/planets/planet-react/planet.md"
assert_dir_exists "$UNIVERSE_ROOT/planets/planet-react/creatures"
assert_dir_exists "$UNIVERSE_ROOT/planets/planet-react/generations"
pass "creates planet dir and skeleton"

# Test 2: planet.md has correct frontmatter
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/planet.md" "name: planet-react"
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/planet.md" "domain: React & frontend patterns"
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/planet.md" "keywords: [react, hooks, jsx]"
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/planet.md" "generation: gen-0"
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/planet.md" "# Planet Verdant-Hook"
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/planet.md" "re-renders"
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/planet.md" "reconciliation-at-speed"
pass "planet.md has correct frontmatter and lore"

# Test 3: opens gen-0.md automatically
assert_file_exists "$UNIVERSE_ROOT/planets/planet-react/generations/gen-0.md"
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/generations/gen-0.md" "generation: gen-0"
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/generations/gen-0.md" "status: active"
pass "opens gen-0"

# Test 4: refuses to overwrite an existing planet
set +e
"$SCRIPT" "react" "dup" "x" "Y" "z" "q" "r" 2>/dev/null
RC=$?
set -e
assert_eq "$RC" "1" "should refuse duplicate"
pass "refuses duplicate planet"

rm -rf "$UNIVERSE_ROOT"
echo "PASS: test_birth_planet"
