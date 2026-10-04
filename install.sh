#!/usr/bin/env bash
# Link every style in skills/ into ~/.claude/skills and check the tools the engine needs.
# Safe to re-run after `git pull` (new styles get linked; existing links are left alone).
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd -P)"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
mkdir -p "$DEST"

for dir in "$REPO"/skills/*/; do
  name="$(basename "$dir")"
  [ -f "$dir/SKILL.md" ] || continue            # skips _template
  link="$DEST/$name"
  if [ -L "$link" ]; then
    [ "$(readlink "$link")" = "${dir%/}" ] && { echo "ok      $name"; continue; }
    rm "$link"
  elif [ -e "$link" ]; then
    echo "skip    $name (a real folder already exists at $link — move it away to link this one)"; continue
  fi
  ln -s "${dir%/}" "$link" && echo "linked  $name"
done

echo
fail=0
check() { if eval "$2" >/dev/null 2>&1; then echo "ok      $1"; else echo "MISSING $1 — $3"; fail=1; fi; }
check "python3"            "command -v python3"                         "install Python 3"
check "playwright (python)" "python3 -c 'import playwright'"            "pip3 install playwright"
check "ffmpeg + prores_ks" "ffmpeg -hide_banner -encoders | grep -q prores_ks" "brew install ffmpeg"
check "chromium"           "python3 -c 'import sys; sys.path.insert(0,\"$REPO/engine\"); import common; assert common.chromium_path()'" \
                           "python3 -m playwright install chromium"
[ $fail = 0 ] && echo -e "\nready. try: python3 $REPO/engine/render.py <job.json> --stills 1.0"
