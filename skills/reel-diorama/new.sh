#!/usr/bin/env bash
# New paper-diorama film from the template: the 27 s sample, the diorama engine, and reel-charity's
# shared pieces (content.js, logo build, icons, closing card, fonts, demo logo).
#   bash new.sh <project-dir> [logo.png] [focus-x,focus-y]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd -P)"
CHARITY="$HERE/../reel-charity"
REPO="$HERE/../.."
DIR="${1:?usage: new.sh <project-dir> [logo.png] [focus-x,focus-y]}"
[ -e "$DIR/index.html" ] && { echo "$DIR already has a project — not overwriting"; exit 1; }
mkdir -p "$DIR/lib" "$DIR/assets/fonts" "$DIR/out"
cp "$CHARITY/template/content.js" "$DIR/"
cp "$CHARITY"/template/lib/*.{js,css} "$DIR/lib/"
cp -R "$CHARITY/template/logo" "$DIR/"
cp -R "$HERE/template/." "$DIR/"
cp "$REPO"/engine/fonts/Tajawal-{Regular,Medium,Bold,ExtraBold}.ttf "$REPO/engine/fonts/OFL.txt" "$DIR/assets/fonts/"
if [ -n "${2:-}" ]; then
  python3 "$CHARITY/tools/split_logo.py" "$2" --out "$DIR/logo" ${3:+--focus "$3"}
fi
echo "ready: $DIR — edit content.js and index.html, then snapshot/render (see SKILL.md)"
