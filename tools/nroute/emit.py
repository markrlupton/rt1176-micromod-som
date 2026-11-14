"""Write nroute's result into the board: build/nroute/routes.txt + base.kicad_pcb -> rt1176-micromod-som.kicad_pcb
  python3 tools/nroute/emit.py        (then tools/drc.py)"""
import os, sys
import pcbnew
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); TOOLS = os.path.dirname(HERE); ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from pcbgen import OUT, MM, VIA_D, VIA_DRILL, TRACK, PLANE_NETS
sys.path.insert(0, HERE)
from prep import PROTECT
from finish_route import G, X0, Y0, NX, NY, SIG
WORK = os.environ.get('NROUTE_DIR') or os.path.join(ROOT, 'build', 'nroute')

_KEEP = []       # removed items must outlive the board object (pcbnew 7 SWIG quirk)
PLANES = {'GND': ('In1.Cu',), '+3V3': ('In4.Cu',), 'DCDC_DIG': ('In4.Cu',)}

def cleanup(b):
    """remove vias that join fewer than two layers and tracks with a loose end, until nothing changes"""
    import math
    pads = {}
    for fp in b.GetFootprints():
        for p in fp.Pads(): pads.setdefault(p.GetNetname(), []).append(p)
    removed = 0
    while True:
        tracks = {}; vias = {}
        for t in b.GetTracks():
            (vias if t.GetClass() == 'PCB_VIA' else tracks).setdefault(t.GetNetname(), []).append(t)
        kill = []
        def near_seg(p, t):
            a, c = t.GetStart(), t.GetEnd(); dx, dy = c.x - a.x, c.y - a.y; L2 = dx * dx + dy * dy
            u = 0 if L2 == 0 else max(0, min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / L2))
            return math.hypot(p.x - (a.x + u * dx), p.y - (a.y + u * dy)) <= t.GetWidth() / 2
        for net, vs in vias.items():
            for v in vs:
                pos = v.GetPosition(); layers = set(PLANES.get(net, ()))
                for t in tracks.get(net, []):
                    if near_seg(pos, t): layers.add(b.GetLayerName(t.GetLayer()))
                for p in pads.get(net, []):
                    if p.HitTest(pos):
                        layers.add('F.Cu' if p.IsOnLayer(pcbnew.F_Cu) else 'B.Cu')
                if len(layers) < 2: kill.append(v)
        for net, ts in tracks.items():
            if net in PROTECT and net not in ('GND', '+3V3'): continue    # other power-rail tracks come from the earlier route: leave them alone
            for t in ts:
                lay = t.GetLayer()
                for e in (t.GetStart(), t.GetEnd()):
                    ok = any(p.IsOnLayer(lay) and p.HitTest(e) for p in pads.get(net, []))
                    ok = ok or any(math.hypot(v.GetPosition().x - e.x, v.GetPosition().y - e.y) <= v.GetWidth() / 2 for v in vias.get(net, []))
                    ok = ok or any(o is not t and o.GetLayer() == lay and near_seg(e, o) for o in ts)
                    if not ok: kill.append(t); break
        if not kill: return removed
        for k in kill: b.Remove(k); _KEEP.append(k)
        removed += len(kill)

def drc_errors(b):
    """number of copper-spacing errors KiCad's DRC finds"""
    import re, tempfile
    rpt = os.path.join(tempfile.mkdtemp(), 'drc.txt')
    pcbnew.WriteDRCReport(b, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    return len(re.findall(r'^\[(clearance|hole_clearance|copper_edge_clearance|shorting_items|tracks_crossing)\]', open(rpt).read(), re.M))

def widen_stubs(b, stubs):
    """the pad-to-plane stubs are routed at 0.09 mm; make each as wide as DRC allows (power fingers carry the supply)"""
    base = drc_errors(b); out = []
    assert base == 0, f'{base} copper-spacing errors before widening: fix those first (tools/drc.py --show clearance,hole_clearance)'
    for name in sorted(stubs):
        got = TRACK
        for w in (0.3, 0.25, 0.2, 0.15):
            for t in stubs[name]: t.SetWidth(MM(w))
            if drc_errors(b) <= base: got = w; break
        for t in stubs[name]: t.SetWidth(MM(got))
        out.append(f'{name} {got:g}')
    print('plane stub widths (mm):', ', '.join(out))

def add_pours(b):
    """GND fill on the four signal layers (lowest priority, loose islands removed). Kept off the gold fingers."""
    from pcbgen import P as CP, WIDTH
    for ln, y0, clr, conn in (('F.Cu', 2.95, 0.2, pcbnew.ZONE_CONNECTION_THERMAL), ('B.Cu', 2.95, 0.2, pcbnew.ZONE_CONNECTION_THERMAL),
                              ('In2.Cu', 1.3, 0.15, pcbnew.ZONE_CONNECTION_FULL), ('In3.Cu', 1.3, 0.15, pcbnew.ZONE_CONNECTION_FULL)):
        z = pcbnew.ZONE(b); z.SetLayer(b.GetLayerID(ln)); z.SetNet(b.FindNet('GND'))
        o = z.Outline(); o.NewOutline()
        for x, y in ((-0.5, y0), (WIDTH + 0.5, y0), (WIDTH + 0.5, 22.5), (-0.5, 22.5)): o.Append(CP(x, y))
        z.SetAssignedPriority(0); z.SetLocalClearance(MM(clr)); z.SetMinThickness(MM(0.15))
        z.SetPadConnection(conn); z.SetThermalReliefGap(MM(0.15)); z.SetThermalReliefSpokeWidth(MM(0.2))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS); b.Add(z)

def main():
    b = pcbnew.LoadBoard(os.path.join(WORK, 'base.kicad_pcb'))
    fixedvia = np.fromfile(os.path.join(WORK, 'fixedvia.i16'), np.int16).reshape(NX, NY)
    lid = [b.GetLayerID(n) for n in SIG]
    def P(x, y): return pcbnew.VECTOR2I(MM(float(X0 + x * G)), MM(float(Y0 + y * G)))
    lines = open(os.path.join(WORK, 'routes.txt')).read().split('\n')
    assert lines[0] == 'CONFLICTS 0', 'the route has conflicts: ' + lines[0]
    nt = nv = 0; net = None; vias_done = set(); segs_done = set(); stubs = {}; cur = None
    def via(x, y):
        nonlocal nv
        if fixedvia[x, y] >= 0 or (x, y) in vias_done: return
        vias_done.add((x, y))
        v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetDrill(MM(VIA_DRILL)); v.SetWidth(MM(VIA_D))
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net); b.Add(v); nv += 1
    def seg(l, a, c):
        nonlocal nt
        if a == c: return
        key = (l, min(a, c), max(a, c))
        if key in segs_done: return
        segs_done.add(key)
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(MM(TRACK)); t.SetLayer(lid[l]); t.SetNet(net); b.Add(t); nt += 1
        if '@' in cur: stubs.setdefault(cur, []).append(t)
    for ln in lines[1:]:
        f = ln.split()
        if not f: continue
        if f[0] == 'NET':
            assert f[3] == '0', f'{f[1]} failed to route'
            net = b.FindNet(f[1].split('@')[0]); assert net, f[1]; cur = f[1]; continue
        v = list(map(int, f[2:])); cells = [tuple(v[i:i + 3]) for i in range(0, len(v), 3)]
        start = cells[0]; lastdir = None
        for a, c in zip(cells, cells[1:]):
            if c[0] == 9:                                   # a plane stub ends in a via
                seg(a[0], start[1:], a[1:]); via(c[1], c[2]); start = None; break
            if a[0] != c[0]:
                seg(a[0], start[1:], a[1:]); via(a[1], a[2]); start = c; lastdir = None; continue
            d = (c[1] - a[1], c[2] - a[2])
            if lastdir is not None and d != lastdir: seg(a[0], start[1:], a[1:]); start = a
            lastdir = d
        if start is not None: seg(cells[-1][0], start[1:], cells[-1][1:])
    print('cleanup removed', cleanup(b), 'unused fan-out vias / stub tracks')
    widen_stubs(b, stubs)
    add_pours(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(OUT, b)
    print(f'added {nt} track segments and {nv} vias; saved {OUT}')

if __name__ == '__main__':
    main()
