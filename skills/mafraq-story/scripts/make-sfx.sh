#!/usr/bin/env bash
# Copy the episode's sound effects into a HyperFrames project and build the three made-for-mafraq sounds:
# bed.wav (drone_dark looped with crossfades, ~66 s), buzz.wav (phone vibrating twice), heartbeat.wav (3 lub-dubs).
# Usage: bash make-sfx.sh <project>/assets/sfx      (needs reel-sfx: python3 ~/.claude/skills/reel-sfx/synth.py once)
set -euo pipefail
OUT="$1"; X="$HOME/.reel-styles/sfx"
[ -f "$X/index.json" ] || python3 "$HOME/.claude/skills/reel-sfx/synth.py"
mkdir -p "$OUT"; cd "$OUT"
for f in notify message_in tap glitch click reverse_swell slam thud pop_low swipe_ui whoosh_soft stinger; do cp "$X/$f.wav" .; done

args=(); for i in $(seq 0 10); do args+=(-i "$X/drone_dark.wav"); done
fc="[0][1]acrossfade=d=1.5[a1]"; for i in $(seq 2 10); do fc="$fc;[a$((i-1))][$i]acrossfade=d=1.5[a$i]"; done
ffmpeg -loglevel error -y "${args[@]}" -filter_complex "$fc" -map "[a10]" -ac 1 -ar 48000 bed.wav

ffmpeg -loglevel error -y -f lavfi \
  -i "aevalsrc='(0.6*sgn(sin(2*PI*158*t))+0.4*sin(2*PI*316*t))*(between(t,0,0.42)+between(t,0.62,1.04))*0.35':s=48000:d=1.3" \
  -af "lowpass=f=900,highpass=f=90,afade=t=out:st=1.15:d=0.12" buzz.wav

ffmpeg -loglevel error -y -i thud.wav -i thud.wav -i thud.wav -i thud.wav -i thud.wav -i thud.wav -filter_complex \
  "[0]adelay=0|0[a];[1]volume=0.6,adelay=230|230[b];[2]adelay=950|950[c];[3]volume=0.6,adelay=1180|1180[d];[4]adelay=1900|1900[e];[5]volume=0.6,adelay=2130|2130[f];[a][b][c][d][e][f]amix=inputs=6:normalize=0,lowpass=f=220" \
  -ac 1 heartbeat.wav
ls -1
