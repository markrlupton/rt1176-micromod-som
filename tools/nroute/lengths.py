"""Print routed length and via count of the nets named on the command line (default: the timing-sensitive ones)."""
import os, sys, math
import pcbnew
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
names = sys.argv[1:] or ['USB_DP', 'USB_DN', 'USBHOST_DP', 'USBHOST_DN', 'XTALI', 'XTALO', 'RTC_XTALI', 'RTC_XTALO']
b = pcbnew.LoadBoard(os.path.join(ROOT, 'rt1176-micromod-som.kicad_pcb'))
for n in names:
    ts = [t for t in b.GetTracks() if t.GetNetname() == n]
    L = sum(math.hypot(t.GetEnd().x - t.GetStart().x, t.GetEnd().y - t.GetStart().y) for t in ts if t.GetClass() != 'PCB_VIA') / 1e6
    lay = sorted({b.GetLayerName(t.GetLayer()) for t in ts if t.GetClass() != 'PCB_VIA'})
    print(f'{n:12s} {L:6.2f} mm  {sum(1 for t in ts if t.GetClass() == "PCB_VIA")} vias  {" ".join(lay)}')
