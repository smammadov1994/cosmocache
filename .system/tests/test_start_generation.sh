#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/lib/assert.sh"

BIRTH_PLANET="$DIR/../skill/lib/birth-planet.sh"
START_GEN="$DIR/../skill/lib/start-generation.sh"

echo "test_start_generation"

UNIVERSE_ROOT="$(make_test_universe)"
export UNIVERSE_ROOT

"$BIRTH_PLANET" "react" "React patterns" "react,hooks" "Verdant-Hook" "canopies" "re-renders" "reconciliation"

# add a key addition to gen-0 so there's something to summarize
echo "- Moved to App Router" >> "$UNIVERSE_ROOT/planets/planet-react/generations/gen-0.md"

# Trigger gen-1 with a summary body
"$START_GEN" "react" "App Router migration" "Migrated from Pages Router to App Router"

# Test 1: gen-0 marked archived
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/generations/gen-0.md" "status: archived"
pass "gen-0 archived"

# Test 2: gen-0-summary.md created
assert_file_exists "$UNIVERSE_ROOT/planets/planet-react/generations/gen-0-summary.md"
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/generations/gen-0-summary.md" "Migrated from Pages Router"
pass "gen-0 summary written"

# Test 3: gen-1.md created, active
assert_file_exists "$UNIVERSE_ROOT/planets/planet-react/generations/gen-1.md"
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/generations/gen-1.md" "generation: gen-1"
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/generations/gen-1.md" "status: active"
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/generations/gen-1.md" "App Router migration"
pass "gen-1 opened active"

# Test 4: planet.md frontmatter updated
assert_file_contains "$UNIVERSE_ROOT/planets/planet-react/planet.md" "generation: gen-1"
pass "planet.md points to gen-1"

rm -rf "$UNIVERSE_ROOT"
echo "PASS: test_start_generation"
