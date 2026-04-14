#!/usr/bin/env bash
# Tiny assertion helpers. Each function exits 1 on failure.

assert_eq() {
  local actual="$1"; local expected="$2"; local msg="${3:-}"
  if [[ "$actual" != "$expected" ]]; then
    echo "FAIL: ${msg:-assert_eq}"
    echo "  expected: $expected"
    echo "  actual:   $actual"
    exit 1
  fi
}

assert_file_exists() {
  [[ -f "$1" ]] || { echo "FAIL: expected file $1"; exit 1; }
}

assert_dir_exists() {
  [[ -d "$1" ]] || { echo "FAIL: expected dir $1"; exit 1; }
}

assert_contains() {
  local haystack="$1"; local needle="$2"; local msg="${3:-}"
  if [[ "$haystack" != *"$needle"* ]]; then
    echo "FAIL: ${msg:-assert_contains}"
    echo "  needle:   $needle"
    echo "  haystack: $haystack"
    exit 1
  fi
}

assert_file_contains() {
  local file="$1"; local needle="$2"
  grep -Fq -- "$needle" "$file" || {
    echo "FAIL: file $file missing: $needle"; exit 1;
  }
}

pass() {
  echo "  ✓ $1"
}

# Make a temp universe for a test, echo its path.
make_test_universe() {
  local tmp
  tmp="$(mktemp -d)"
  mkdir -p "$tmp/enigma" "$tmp/planets"
  cat > "$tmp/enigma/glossary.md" <<GLOSS
# Enigma's Glossary

| Planet | Domain | Keywords | Last Visited | Gen | Creatures | Why Last Modified |
|---|---|---|---|---|---|---|
GLOSS
  cat > "$tmp/.universe-meta.json" <<META
{"version":"1.0.0","theatrical_mode":false,"planet_count":0,"created":"2026-04-13"}
META
  echo "$tmp"
}
