#!/usr/bin/env bash
# New charity project from the template: the intro and end compositions, shared content, fonts and the demo logo.
#   bash new.sh <project-dir> [logo.png] [focus-x,focus-y]
# With a logo it splits it into parts right away (needs: pip3 install pillow numpy scipy).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd -P)"
REPO="$HERE/../.."
DIR="${1:?usage: new.sh <project-dir> [logo.png] [focus-x,focus-y]}"
[ -e "$DIR/content.js" ] && { echo "$DIR already has a project — not overwriting"; exit 1; }
mkdir -p "$DIR/assets/fonts" "$DIR/out"
cp -R "$HERE/template/." "$DIR/"
rm -f "$DIR/assets/demo-logo.png"
for scene in intro end; do                       # each scene is its own HyperFrames project sharing the files above
  for f in content.js lib logo assets; do ln -s "../$f" "$DIR/$scene/$f"; done
done
cp "$REPO"/engine/fonts/Tajawal-{Regular,Medium,Bold,ExtraBold}.ttf "$REPO/engine/fonts/OFL.txt" "$DIR/assets/fonts/"
if [ -n "${2:-}" ]; then
  python3 "$HERE/tools/split_logo.py" "$2" --out "$DIR/logo" ${3:+--focus "$3"}
fi
echo "ready: $DIR — edit content.js, then render intro/ and end/ (see SKILL.md)"
