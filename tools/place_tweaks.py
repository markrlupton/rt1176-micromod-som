"""Hand placement fixes applied on top of tools/pcbgen.py's output (edits *-placed.kicad_pcb in place; safe to re-run).

  python3 tools/place_tweaks.py

1. C52 (32.768 kHz load cap on RTC_XTALO): no room on the bottom within 3.8 mm of ball U13, because every via site
   around it is taken. It goes on the top side beside Y2's RTC_XTALO pad instead. Y2 moves 0.1 mm left to make room.
"""
import os, sys
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from pcbgen import P, OUT, card
PLACED = OUT.replace('.kicad_pcb', '-placed.kicad_pcb')

def main():
    b = pcbnew.LoadBoard(PLACED)
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    y2 = fps['Y2']; y2.SetPosition(P(2.15, 10.6))
    xo = [p for p in y2.Pads() if p.GetNetname() == 'RTC_XTALO'][0]; _, yo = card(xo.GetPosition())
    c = fps['C52']
    if c.GetLayer() != pcbnew.F_Cu: c.Flip(c.GetPosition(), False)
    c.SetOrientationDegrees(90); c.SetPosition(P(3.825, yo + 0.48))
    p1 = [p for p in c.Pads() if p.GetNetname() == 'RTC_XTALO'][0]
    if abs(card(p1.GetPosition())[1] - yo) > 0.1:                       # RTC_XTALO pad must be the one level with Y2's pad
        c.SetOrientationDegrees(270)
        p1 = [p for p in c.Pads() if p.GetNetname() == 'RTC_XTALO'][0]
    assert abs(card(p1.GetPosition())[1] - yo) < 0.1
    pcbnew.SaveBoard(PLACED, b)
    print('C52 on top at', card(c.GetPosition()), 'RTC_XTALO pad at', card(p1.GetPosition()), '; Y2 pad at', card(xo.GetPosition()))

if __name__ == '__main__':
    main()
