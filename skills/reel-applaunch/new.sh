#!/usr/bin/env bash
# New app-feature film from the template: the 16 s «الطلب التفاعلي» sample (text bar) and its voice-mode
# variant, the audio builder, and Tajawal as the stand-in brand font.
#   bash new.sh <project-dir> [sfx-pack-dir]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd -P)"
REPO="$HERE/../.."
DIR="${1:?usage: new.sh <project-dir> [sfx-pack-dir]}"
[ -e "$DIR/index.html" ] && { echo "$DIR already has a project — not overwriting"; exit 1; }
mkdir -p "$DIR/assets/fonts" "$DIR/variants" "$DIR/out"
cp -R "$HERE/template/tools" "$DIR/"
cp "$HERE/template/index.html" "$DIR/"
sed 's#"assets/#"../assets/#g' "$HERE/template/voice-mode.html" > "$DIR/variants/voice-mode.html"
cp "$REPO"/engine/fonts/Tajawal-{Regular,Medium,Bold}.ttf "$REPO/engine/fonts/OFL.txt" "$DIR/assets/fonts/"
if [ -n "${2:-}" ]; then mkdir -p "$DIR/assets/sfx-src" && cp "$2"/*.wav "$DIR/assets/sfx-src/"; fi
missing=""
for f in orb.png logo-white.png p1.png p2.png p3.png p4.png p5.png p6.png; do
  [ -f "$DIR/assets/$f" ] || missing="$missing $f"
done
echo "ready: $DIR"
[ -n "$missing" ] && echo "put these in $DIR/assets/:$missing   (see SKILL.md → الأصول)"
exit 0
