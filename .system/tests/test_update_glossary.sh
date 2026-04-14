#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/lib/assert.sh"

BIRTH_PLANET="$DIR/../skill/lib/birth-planet.sh"
UPDATE_GLOSS="$DIR/../skill/lib/update-glossary.sh"

echo "test_update_glossary"

UNIVERSE_ROOT="$(make_test_universe)"
export UNIVERSE_ROOT

"$BIRTH_PLANET" "react" "React patterns" "react,hooks" "Verdant-Hook" "x" "y" "z"

# Test 1: insert new row
"$UPDATE_GLOSS" "react" "App Router migration"
assert_file_contains "$UNIVERSE_ROOT/enigma/glossary.md" "planet-react"
assert_file_contains "$UNIVERSE_ROOT/enigma/glossary.md" "App Router migration"
pass "inserts row on first call"

# Row count = 1
ROWS=$(grep -c "^| planet-" "$UNIVERSE_ROOT/enigma/glossary.md")
assert_eq "$ROWS" "1" "should have one row"
pass "exactly one row"

# Test 2: update existing row (no duplicate)
"$UPDATE_GLOSS" "react" "Added RSC patterns"
ROWS=$(grep -c "^| planet-" "$UNIVERSE_ROOT/enigma/glossary.md")
assert_eq "$ROWS" "1" "still one row after update"
assert_file_contains "$UNIVERSE_ROOT/enigma/glossary.md" "Added RSC patterns"
# old reason should be gone
if grep -q "App Router migration" "$UNIVERSE_ROOT/enigma/glossary.md"; then
  echo "FAIL: old 'why' should have been replaced"; exit 1
fi
pass "updates without duplicating"

# Test 3: refuses nonexistent planet
set +e
"$UPDATE_GLOSS" "nope" "reason" 2>/dev/null
RC=$?
set -e
assert_eq "$RC" "1"
pass "refuses unknown planet"

rm -rf "$UNIVERSE_ROOT"
echo "PASS: test_update_glossary"
