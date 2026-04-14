#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/lib/assert.sh"

LOAD="$DIR/../hooks/universe-load.sh"
COMMIT="$DIR/../hooks/universe-commit.sh"
BIRTH_PLANET="$DIR/../skill/lib/birth-planet.sh"

echo "test_hooks"

UNIVERSE_ROOT="$(make_test_universe)"
export UNIVERSE_ROOT

# -------- universe-load.sh --------

# Test 1: outputs glossary content when given no cwd match
OUTPUT="$("$LOAD" 2>&1)"
assert_contains "$OUTPUT" "# Enigma's Glossary" "should include glossary header"
assert_contains "$OUTPUT" "Enigma consulted" "should include status line"
pass "load outputs glossary + status"

# Test 2: detects anchor_paths match
"$BIRTH_PLANET" "react" "React" "react" "Verdant" "x" "y" "z"
# add an anchor path matching a known test dir
TEST_ANCHOR="/tmp/universe-anchor-test"
mkdir -p "$TEST_ANCHOR"
# inject anchor_paths by rewriting planet.md
sed -i '' "s|anchor_paths: \[\]|anchor_paths: [$TEST_ANCHOR]|" "$UNIVERSE_ROOT/planets/planet-react/planet.md"

OUTPUT="$(cd "$TEST_ANCHOR" && "$LOAD" 2>&1)"
assert_contains "$OUTPUT" "Anchored to: planet-react" "should detect anchor"
assert_contains "$OUTPUT" "# Planet Verdant" "should include planet.md body"
pass "load detects anchor + injects planet.md"

rm -rf "$TEST_ANCHOR"

# Test 2b: reject false-positive prefix match (/foo should NOT match /foobar)
mkdir -p /tmp/universe-anchor-foobar
sed -i '' "s|anchor_paths: \[[^]]*\]|anchor_paths: [/tmp/universe-anchor]|" "$UNIVERSE_ROOT/planets/planet-react/planet.md"
OUTPUT="$(cd /tmp/universe-anchor-foobar && "$LOAD" 2>&1)"
assert_contains "$OUTPUT" "Anchored to: none" "should not match /foobar to /foo anchor"
pass "load rejects false-positive prefix match"
rm -rf /tmp/universe-anchor-foobar

# -------- universe-commit.sh --------

# Test 3: commit hook prints the persistence prompt
OUTPUT="$("$COMMIT" 2>&1)"
assert_contains "$OUTPUT" "/universe remember" "should prompt remember action"
pass "commit hook prompts /universe remember"

rm -rf "$UNIVERSE_ROOT"
echo "PASS: test_hooks"
