#!/bin/sh
# Render each copper layer of the card (plus outline) to docs/layout/*.png.  Needs kicad-cli and rsvg-convert.
set -e
cd "$(dirname "$0")/.."
OUT=docs/layout; mkdir -p "$OUT"; T=$(mktemp -d)
for L in F.Cu In1.Cu In2.Cu In3.Cu In4.Cu B.Cu; do
  M=""; [ "$L" = B.Cu ] && M="--mirror"
  EXTRA=""; case $L in F.Cu) EXTRA=",F.Fab";; B.Cu) EXTRA=",B.Fab";; esac
  kicad-cli pcb export svg -o "$T/$L.svg" --layers "$L,Edge.Cuts$EXTRA" $M --page-size-mode 2 --exclude-drawing-sheet rt1176-micromod-som.kicad_pcb >/dev/null
  rsvg-convert -b white -w 1000 "$T/$L.svg" -o "$OUT/$(echo $L | tr . _ | tr A-Z a-z).png"
done
echo "rendered to $OUT"
