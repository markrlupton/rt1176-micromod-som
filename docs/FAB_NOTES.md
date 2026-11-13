# Ordering from JLCPCB

All files are made by `python3 tools/fab.py` and live in `fab/`.

## Bare board

Upload `fab/rt1176-micromod-som-gerbers.zip`. Settings:

| Option | Setting | Why |
|---|---|---|
| Layers | 6 | |
| Dimensions | 22.8 × 22 mm (read from the outline) | |
| Thickness | 0.8 mm | MicroMod card thickness |
| Stack-up | JLC's standard 0.8 mm 6-layer stack-up | no controlled impedance needed (USB runs are about 7 mm) |
| Outer / inner copper | 1 oz / 0.5 oz | 0.09 mm trace and space |
| Min via hole / diameter | 0.15 mm / 0.3 mm | BGA fan-out vias (6-layer option) |
| Via covering | **Epoxy filled and capped** | the bottom 0402s sit on vias (via-in-pad); open vias would wick solder away |
| Surface finish | ENIG | flat BGA pads and the gold fingers |
| Gold fingers | Yes, 45° chamfer (bevel) on the finger edge | M.2 edge connector |
| Solder mask | any colour | |
| Silkscreen | outlines and pin-1 marks only, no text | no room for legible designators; use the assembly drawings |
| Mark on PCB / order number | Remove, or specify a location you're happy with | there is no clear spot for it |
| Board count | 5 | |

Things JLC's checker may flag that are expected:
- 0.09 mm trace/space and 0.15 mm via holes: within JLC's 6-layer limits.
- Copper close to the hole wall (0.17 mm minimum on this board). If they want 0.2 mm, tell me and I'll re-route with that rule.

## Stencils

- **Hand build:** order a frameless stencil from `fab/stencil-hand/` (top paste without BGA apertures, bottom paste).
  Order top and bottom as one stencil, or two if you want them separate.
- **JLC assembly:** JLC makes its own stencil from the paste layers in the gerbers zip.

## Assembly (if JLC builds it)

- Standard PCBA, both sides. BOM: `fab/bom-jlc.csv`. Placement: `fab/cpl-jlc.csv`.
- U1 (MIMXRT1176DVMAB) and U4 (GD25Q128EQIGR) are not stocked at LCSC: buy them (DigiKey or Mouser) and consign
  them, or use JLC's global sourcing.
- Check rotations in JLC's placement preview, especially U2, U3 (SOT-23-5/6), D1 (SOT-23), U4 and Y1; KiCad's zero
  rotation doesn't always match JLC's.
- J1 (the gold fingers) and TP1 to TP5 (bare test pads) are left out of the BOM and placement files.

## Notes on parts

- Y1 is YXC X201624MMD4SI (C108160), 10 pF load. C48/C49 are 12 pF, which gives about 9 pF with board stray; close
  enough for USB and audio. Use 15 pF if you want it exactly on frequency.
- The flash needs QE = 1 set once for quad reads (the NXP boot ROM does this when you program it with their tools).
