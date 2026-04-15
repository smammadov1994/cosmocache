#!/usr/bin/env bash
# Seed 10 canonical planets so a fresh universe has something to look at.
#
# Run directly:
#     .system/seeds/ten-planets.sh
#
# Or via the CLI:
#     cosmo seed
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
  "react:React & frontend patterns:react,hooks,jsx:Verdant-Hook:dense canopies of reactive foliage:re-renders:reconciliation,prop-sight"
  "python:Python ecosystem:python,pip,venv:Serpentis:coiled libraries:whitespace:duck-typing,gil-whisper"
  "rust:Rust systems:rust,cargo,borrow:Ferro-Crag:iron cliffs:lifetimes:borrow-check,zero-cost"
  "go:Go concurrency:go,goroutines,channels:Gophoria:burrowed meadows:goroutines:channel-weave,gc-pause"
  "typescript:TypeScript types:typescript,tsc,types:Typhlos:crystalline type lattices:inference:generics,narrowing"
  "docker:Containers & Docker:docker,compose,images:Hullform:floating cargo shells:layers:layer-cache,rootless-run"
  "k8s:Kubernetes orchestration:kubernetes,pods,helm:Podspire:terraced server-hives:manifests:pod-scheduling,hpa-sight"
  "postgres:PostgreSQL & SQL:postgres,sql,psql:Aquaform:brackish query-seas:WAL:index-sight,vacuum-rite"
  "aws:AWS cloud:aws,s3,lambda:Nimbaris:billowing cloud-steppes:IAM:iam-sigils,region-hop"
  "llm:LLM engineering:llm,prompts,tokens:Noospheron:whispering prompt-mists:tokens:prompt-weave,context-echo"
)

for p in "${PLANETS[@]}"; do
  IFS=':' read -r slug domain kw name tag food abil <<< "$p"
  UNIVERSE_ROOT="$UNIVERSE_ROOT" "$BIRTH" "$slug" "$domain" "$kw" "$name" "$tag" "$food" "$abil" \
    || echo "  (skipped planet-$slug — see error above)" >&2
done
