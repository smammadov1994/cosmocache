#!/bin/bash
# Install a launchd plist per planet so each planet runs evolution_tick.py
# on its own schedule. Idempotent — safe to re-run after birthing new planets.
#
# Override cadence:  EVOLUTION_INTERVAL=21600 ./install_evolution_cron.sh
# Override universe: UNIVERSE_ROOT=/path/to/universe ./install_evolution_cron.sh

set -eu

UNIVERSE="${UNIVERSE_ROOT:-/Users/bot/universe}"
AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PREFIX="ai.cosmocache.evolution"
TICK_SCRIPT="$UNIVERSE/scripts/evolution_tick.py"
INTERVAL_SECONDS="${EVOLUTION_INTERVAL:-21600}"  # 6h default

if [ ! -f "$TICK_SCRIPT" ]; then
  echo "error: tick script not found at $TICK_SCRIPT" >&2
  exit 2
fi

mkdir -p "$AGENTS_DIR"
mkdir -p "$UNIVERSE/.system/logs"

if [ ! -d "$UNIVERSE/planets" ]; then
  echo "no planets/ dir at $UNIVERSE; nothing to install"
  exit 0
fi

installed=0
skipped=0
for planet_dir in "$UNIVERSE/planets"/*/; do
  [ -d "$planet_dir" ] || { skipped=$((skipped+1)); continue; }
  slug="$(basename "$planet_dir")"
  label="${PLIST_PREFIX}.${slug}"
  plist="$AGENTS_DIR/${label}.plist"
  log_file="$UNIVERSE/.system/logs/launchd-${slug}.log"

  cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>python3</string>
    <string>${TICK_SCRIPT}</string>
    <string>${slug}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>UNIVERSE_ROOT</key><string>${UNIVERSE}</string>
    <key>HOME</key><string>${HOME}</string>
    <key>PATH</key><string>/usr/local/bin:/usr/bin:/bin:${HOME}/.local/bin</string>
  </dict>
  <key>StartInterval</key><integer>${INTERVAL_SECONDS}</integer>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>${log_file}</string>
  <key>StandardErrorPath</key><string>${log_file}</string>
</dict>
</plist>
EOF

  launchctl unload "$plist" 2>/dev/null || true
  launchctl load "$plist"
  echo "installed: ${label} (every ${INTERVAL_SECONDS}s)"
  installed=$((installed+1))
done

# -------- Enigma plist: daily glossary -> index.md regen --------
ENIGMA_SCRIPT="$UNIVERSE/scripts/enigma_tick.py"
ENIGMA_INTERVAL="${ENIGMA_INTERVAL:-86400}"  # daily default
if [ -f "$ENIGMA_SCRIPT" ] && [ -f "$UNIVERSE/enigma/glossary.md" ]; then
  label="ai.cosmocache.enigma"
  plist="$AGENTS_DIR/${label}.plist"
  log_file="$UNIVERSE/.system/logs/launchd-enigma.log"

  cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>python3</string>
    <string>${ENIGMA_SCRIPT}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>UNIVERSE_ROOT</key><string>${UNIVERSE}</string>
    <key>HOME</key><string>${HOME}</string>
    <key>PATH</key><string>/usr/local/bin:/usr/bin:/bin:${HOME}/.local/bin</string>
  </dict>
  <key>StartInterval</key><integer>${ENIGMA_INTERVAL}</integer>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>${log_file}</string>
  <key>StandardErrorPath</key><string>${log_file}</string>
</dict>
</plist>
EOF
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load "$plist"
  echo "installed: ${label} (every ${ENIGMA_INTERVAL}s)"
fi

echo ""
echo "summary: installed=${installed} planets + enigma"
echo "logs:       ${UNIVERSE}/.system/logs/"
echo "inspect:    launchctl list | grep ai.cosmocache"
echo "smoke:      UNIVERSE_ROOT=${UNIVERSE} python3 ${TICK_SCRIPT} <slug>"
echo "            UNIVERSE_ROOT=${UNIVERSE} python3 ${ENIGMA_SCRIPT}"
echo "uninstall:  ${UNIVERSE}/scripts/uninstall_evolution_cron.sh"
