"""Hand placement fixes applied on top of tools/pcbgen.py's output (edits *-placed.kicad_pcb in place; safe to re-run).

  python3 tools/place_tweaks.py

1. C52 (32.768 kHz load cap on RTC_XTALO): no room on the bottom within 3.8 mm of ball U13, because every via site
   around it is taken. It goes on the top side beside Y2's RTC_XTALO pad instead. Y2 moves 0.1 mm left to make room.
2. C33, C35 (SNVS LDO output caps) sat 4.5 mm from the finger edge on the bottom. The M.2 spec keeps bottom-side
   parts at least 5.2 mm back (the socket housing is under there), and the bottom has no free spot within 4 mm of
   their balls. They join C52 in a top-side column beside the BGA's left edge, 1.3 to 2.5 mm from balls U14 / T14.
   Y1 moves 0.2 mm left for room. Their nets (VDD_SNVS_ANA, VDD_SNVS_DIG) are routed by nroute.
3. R1 value 4.7k (BOOT# pull-up), to match the schematic.
"""
import os, sys
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pcbgen import P, OUT, card
PLACED = OUT.replace('.kicad_pcb', '-placed.kicad_pcb')

def top_column(fps, ref, y, up=True, x=3.825):
    """stand a 0402 upright in the top-side column between the crystals and the BGA's left edge, signal pad up or down"""
    c = fps[ref]
    if c.GetLayer() != pcbnew.F_Cu: c.Flip(c.GetPosition(), False)
    c.SetPosition(P(x, y))
    sig = [p for p in c.Pads() if p.GetNetname() != 'GND'][0]
    for deg in (90, 270):
        c.SetOrientationDegrees(deg)
        if (card(sig.GetPosition())[1] > y) == up: break
    return card(sig.GetPosition())

def main():
    b = pcbnew.LoadBoard(PLACED)
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    fps['Y2'].SetPosition(P(2.15, 10.6)); fps['Y1'].SetPosition(P(2.05, 6.45))
    for ref, y, up in (('C35', 6.11, True), ('C33', 7.97, True), ('C52', 9.83, False)):     # C52's pad is level with Y2's
        print(ref, 'on top, signal pad at', top_column(fps, ref, y, up))
    fps['R1'].SetValue('4.7k')
    pcbnew.SaveBoard(PLACED, b)

if __name__ == '__main__':
    main()
