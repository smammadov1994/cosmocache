#!/usr/bin/env bash
# cosmocache installer — wires Claude Code hooks, the /universe skill,
# and (optionally) the autonomous evolve loop. Idempotent.
set -euo pipefail

export REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── colors ─────────────────────────────────────────────────────────────
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  B=$'\033[1m'; D=$'\033[2m'; R=$'\033[0m'
  V=$'\033[38;5;141m'; Vb=$'\033[1;38;5;141m'
  G=$'\033[38;5;114m'; Y=$'\033[38;5;222m'
  Rd=$'\033[38;5;203m'; C=$'\033[38;5;110m'
  Coral=$'\033[38;5;209m'
else
  B=''; D=''; R=''; V=''; Vb=''; G=''; Y=''; Rd=''; C=''; Coral=''
fi
OK="${G}✓${R}"; X="${Rd}✗${R}"; Q="${Y}?${R}"; STAR="${Coral}✦${R}"
hr() { printf "${D}  ────────────────────────────────────────────────${R}\n"; }
section() { printf "\n${Vb}  %s${R}\n" "$1"; hr; }
step() { printf "\n  ${B}[%s]${R} %s\n" "$1" "$2"; }
ok() { printf "        %s %s\n" "$OK" "$1"; }
warn() { printf "        %s ${Y}%s${R}\n" "$Q" "$1"; }
bad() { printf "        %s ${Rd}%s${R}\n" "$X" "$1"; }
dim() { printf "        ${D}%s${R}\n" "$1"; }

banner() {
cat <<EOF
${V}
      *       .      ✦     .       *       .
   .        .     ✦   .         *      .    ·
       ${Coral}___ ___  ___ _ __ ___   ___   ___ __ _  ___| |__   ___${V}
      ${Coral}/ __/ _ \\/ __| '_ \` _ \\ / _ \\ / __/ _\` |/ __| '_ \\ / _ \\${V}
     ${Coral}| (_| (_) \\__ \\ | | | | | (_) | (_| (_| | (__| | | |  __/${V}
      ${Coral}\\___\\___/|___/_| |_| |_|\\___/ \\___\\__,_|\\___|_| |_|\\___|${V}
    .         ·   persistent memory for claude code    ·     .
      ·   .     ✦    .      ·     *     ·    .     ✦
${R}
${D}      "I am the keeper of names. Ask, and I will point the way."${R}
${D}                                    — Enigma the One${R}

EOF
}

# ─── prerequisites ──────────────────────────────────────────────────────
banner
section "Prerequisites"

OS="$(uname -s)"
if [[ "$OS" != "Darwin" ]]; then
  bad "macOS required (detected: $OS)"
  dim "the memory system works on Linux but the evolve loop uses launchd."
  dim "skip evolve and wire hooks manually on non-macOS systems."
  exit 1
fi
ok "macOS detected ($(uname -r))"

if ! command -v python3 >/dev/null 2>&1; then
  bad "python3 not found (need ≥ 3.9)"; exit 1
fi
ok "python3 $(python3 --version 2>&1 | awk '{print $2}')"

if command -v claude >/dev/null 2>&1; then
  ok "claude cli: $(command -v claude)"
else
  warn "claude cli not on PATH (install from https://claude.ai/code)"
fi

HAS_KEY=0
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  ok "ANTHROPIC_API_KEY is set"
  HAS_KEY=1
else
  warn "ANTHROPIC_API_KEY not set (evolve ticks will no-op without it)"
fi

# ─── step 1: hooks ──────────────────────────────────────────────────────
section "Installation"

step "1/5" "wiring Claude Code hooks ${D}→ ~/.claude/settings.json${R}"
python3 - <<'PY'
import json, os, pathlib, sys
repo = os.environ["REPO"]
home = pathlib.Path.home()
cfg = home / ".claude" / "settings.json"
cfg.parent.mkdir(parents=True, exist_ok=True)
data = {}
if cfg.exists():
    raw = cfg.read_text().strip()
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"existing settings.json is not valid JSON: {e}", file=sys.stderr)
            sys.exit(1)

hooks = data.setdefault("hooks", {})

def has_cmd(arr, cmd):
    for e in arr:
        for h in e.get("hooks", []) if isinstance(e, dict) else []:
            if h.get("command") == cmd:
                return True
    return False

added = 0
ss = hooks.setdefault("SessionStart", [])
ss_cmd = f"{repo}/.system/hooks/universe-load.sh"
if not has_cmd(ss, ss_cmd):
    ss.append({"matcher": "*", "hooks": [{"type": "command", "command": ss_cmd}]})
    added += 1

st = hooks.setdefault("Stop", [])
st_cmd = f"{repo}/.system/hooks/universe-commit.sh"
if not has_cmd(st, st_cmd):
    st.append({"hooks": [{"type": "command", "command": st_cmd}]})
    added += 1

cfg.write_text(json.dumps(data, indent=2) + "\n")
PY
ok "SessionStart + Stop wired (existing entries preserved)"

# ─── step 2: skill ──────────────────────────────────────────────────────
step "2/5" "registering ${Coral}/universe${R} skill ${D}→ ~/.claude/skills/universe${R}"
SKILL_SRC="$REPO/.system/skill"
SKILL_DST="$HOME/.claude/skills/universe"
mkdir -p "$HOME/.claude/skills"
if [[ -L "$SKILL_DST" || -e "$SKILL_DST" ]]; then
  dim "existing entry at $SKILL_DST — replacing"
  rm -rf "$SKILL_DST"
fi
ln -s "$SKILL_SRC" "$SKILL_DST"
ok "symlinked"

# ─── step 3: seed planets (opt-out prompt, default Y) ──────────────────
step "3/5" "seed the universe with starter planets ${D}(default yes)${R}"
dim "5 general planets for everyday Claude work:"
dim "${Coral}writing${R} · ${Coral}career${R} · ${Coral}health${R} · ${Coral}travel${R} · ${Coral}learning${R}"
dim "each is an empty scaffold — Claude fills them as you work."

PLANETS_EXISTING=$(find "$REPO/planets" -maxdepth 1 -type d -name 'planet-*' 2>/dev/null | wc -l | tr -d ' ')
if [[ "$PLANETS_EXISTING" -gt 0 ]]; then
  dim "${PLANETS_EXISTING} planets already exist — skipping seed"
  SEEDED=0
else
  printf "\n        ${Y}Seed the 5 starter planets now? [Y/n]${R} "
  read -r ANS_SEED || ANS_SEED="Y"
  ANS_SEED="${ANS_SEED:-Y}"
  if [[ "$ANS_SEED" =~ ^[Yy]$ ]]; then
    if UNIVERSE_ROOT="$REPO" bash "$REPO/.system/seeds/starter.sh" >/dev/null 2>&1; then
      ok "seeded 5 planets (writing, career, health, travel, learning)"
      SEEDED=1
    else
      bad "seed failed — run .system/seeds/starter.sh manually for details"
      SEEDED=0
    fi
  else
    dim "skipped — seed later with: ${C}scripts/cosmo seed starter${R}"
    SEEDED=0
  fi
fi

# ─── step 4: PATH (opt-in) ──────────────────────────────────────────────
step "4/5" "add ${Coral}cosmo${R} to your PATH ${D}(opt-in)${R}"
dim "so you can run ${C}cosmo planets${R} from anywhere instead of ${C}scripts/cosmo${R}"

SHELL_RC=""
case "${SHELL:-}" in
  */zsh) SHELL_RC="$HOME/.zshrc" ;;
  */bash) SHELL_RC="$HOME/.bashrc" ;;
esac

PATH_LINE="export PATH=\"$REPO/scripts:\$PATH\"  # cosmocache"

if [[ -z "$SHELL_RC" ]]; then
  dim "couldn't detect zsh/bash — add this to your shell rc manually:"
  dim "  ${C}${PATH_LINE}${R}"
elif [[ -f "$SHELL_RC" ]] && grep -qF "$REPO/scripts" "$SHELL_RC"; then
  ok "already present in $(basename "$SHELL_RC")"
else
  printf "\n        ${Y}Add to $(basename "$SHELL_RC")? [y/N]${R} "
  read -r ANS_PATH || ANS_PATH="N"
  ANS_PATH="${ANS_PATH:-N}"
  if [[ "$ANS_PATH" =~ ^[Yy]$ ]]; then
    printf "\n%s\n" "$PATH_LINE" >> "$SHELL_RC"
    ok "appended to $(basename "$SHELL_RC")"
    dim "reload shell or run: ${C}source $SHELL_RC${R}"
  else
    dim "skipped — add manually later if you want:"
    dim "  ${C}${PATH_LINE}${R}"
  fi
fi

# ─── step 5: evolve loop (opt-in) ───────────────────────────────────────
step "5/5" "autonomous evolve loop ${D}(opt-in)${R}"
dim "runs a Haiku-4.5 judge every 6h per planet. When a planet has"
dim "code/docs/skills, it writes an autoresearch note. Idle planets"
dim "cost ~\$0. Disable anytime with: ${C}cosmo evolve uninstall${R}"
[[ $HAS_KEY -eq 0 ]] && warn "(reminder) ANTHROPIC_API_KEY not set — ticks will no-op"

printf "\n        ${Y}Enable the autonomous evolve loop now? [y/N]${R} "
read -r ANS || ANS="N"
ANS="${ANS:-N}"
EVOLVE_ENABLED=0
if [[ "$ANS" =~ ^[Yy]$ ]]; then
  if UNIVERSE_ROOT="$REPO" bash "$REPO/scripts/install_evolution_cron.sh" >/dev/null 2>&1; then
    ok "launchd plists installed"
    EVOLVE_ENABLED=1
  else
    bad "cron install failed — run scripts/install_evolution_cron.sh manually for details"
  fi
else
  dim "skipped — enable later with: ${C}scripts/cosmo evolve install${R}"
fi

# ─── summary ────────────────────────────────────────────────────────────
section "Summary"
PLANET_COUNT=$(find "$REPO/planets" -maxdepth 1 -type d -name 'planet-*' 2>/dev/null | wc -l | tr -d ' ')
printf "  %s planets known:  ${B}%s${R}\n" "$STAR" "$PLANET_COUNT"
printf "  %s hooks:          ${B}SessionStart, Stop${R}\n" "$STAR"
printf "  %s skill:          ${B}/universe${R}\n" "$STAR"
if [[ $EVOLVE_ENABLED -eq 1 ]]; then
  printf "  %s evolve loop:    ${G}enabled${R} ${D}(6h/planet · daily/Enigma)${R}\n" "$STAR"
else
  printf "  %s evolve loop:    ${D}disabled${R}\n" "$STAR"
fi

section "Next"
cat <<EOF
  start a Claude Code session anywhere — Enigma's glossary will load
  automatically. Use ${C}/universe recall${R} to query; the Stop hook will
  nudge ${C}/universe remember${R} on the way out if new knowledge emerged.

  ${C}cosmo planets${R}             ${D}# roster${R}
  ${C}cosmo search <query>${R}      ${D}# ripgrep across the cosmos${R}
  ${C}cosmo evolve status${R}       ${D}# inspect the loop${R}
  ${C}cosmo seed ten-planets${R}    ${D}# add 10 tech-focused planets${R}

  ${D}optional: the simulation dashboard (docker)${R}
  ${C}cd dashboard && docker compose up --build${R}
  ${D}then open http://localhost:8765${R}

EOF
printf "${Coral}        ✦ may the ancient one guide your seeking ✦${R}\n\n"
