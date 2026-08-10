#!/usr/bin/env bash
# Installs claude-speak into every Claude Code config directory found.
#
#   ./install.sh                 # auto-detect ~/.claude, $CLAUDE_CONFIG_DIR, ...
#   ./install.sh ~/.claude-work  # or name the config dirs explicitly
#
# Safe to re-run: existing settings are merged, never replaced.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="${CLAUDE_SPEAK_HOME:-$HOME/.claude-speak}"
PYTHON="$(command -v python3)"

if [ -z "$PYTHON" ]; then
  echo "python3 not found on PATH" >&2
  exit 1
fi

# Shared config + runtime state, so every config dir speaks with one voice.
mkdir -p "$HOME_DIR"
# Stable path to the scripts, so skills don't hardcode wherever you cloned this.
ln -sfn "$SRC" "$HOME_DIR/bin"
if [ ! -f "$HOME_DIR/config.json" ]; then
  cp "$SRC/config.default.json" "$HOME_DIR/config.json"
  echo "seeded $HOME_DIR/config.json"
fi

# Which config dirs to wire up.
if [ "$#" -gt 0 ]; then
  TARGETS=("$@")
else
  TARGETS=("$HOME/.claude")
  [ -n "${CLAUDE_CONFIG_DIR:-}" ] && TARGETS+=("$CLAUDE_CONFIG_DIR")
  for d in "$HOME"/.claude-*; do
    case "$d" in
      *"/.claude-speak") continue ;;
    esac
    [ -d "$d" ] && [ -f "$d/settings.json" ] && TARGETS+=("$d")
  done
fi

# De-duplicate while preserving order.
SEEN=""
for CFG in "${TARGETS[@]}"; do
  CFG="${CFG%/}"
  case " $SEEN " in *" $CFG "*) continue ;; esac
  SEEN="$SEEN $CFG"

  [ -d "$CFG" ] || { echo "skip $CFG (not a directory)"; continue; }

  mkdir -p "$CFG/skills"
  for SKILL in "$SRC"/skills/*/; do
    NAME="$(basename "$SKILL")"
    rm -rf "$CFG/skills/$NAME"
    ln -s "${SKILL%/}" "$CFG/skills/$NAME"
  done

  SRC="$SRC" PYTHON="$PYTHON" "$PYTHON" - "$CFG/settings.json" <<'PY'
import json, os, sys

path = sys.argv[1]
command = '"%s" "%s/stop-hook.py"' % (os.environ["PYTHON"], os.environ["SRC"])

try:
    with open(path) as f:
        settings = json.load(f)
except FileNotFoundError:
    settings = {}
except ValueError:
    sys.exit("%s is not valid JSON -- fix it and re-run" % path)

hooks = settings.setdefault("hooks", {})
stop = hooks.setdefault("Stop", [])

# Drop any previous claude-speak entry, keeping every other Stop hook intact.
for group in stop:
    group["hooks"] = [h for h in group.get("hooks", [])
                      if "stop-hook.py" not in str(h.get("command", ""))]
stop[:] = [g for g in stop if g.get("hooks")]

stop.append({"hooks": [{
    "type": "command",
    "command": command,
    "timeout": 60,
    "async": True,
    "statusMessage": "Speaking...",
}]})

with open(path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
print("wired %s" % path)
PY
done

echo
echo "installed. shared config: $HOME_DIR/config.json"
echo "try:  $PYTHON $HOME_DIR/bin/speakctl.py test"
echo "note: open /hooks once (or restart) in any running session to load the hook."
