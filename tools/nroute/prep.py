"""Prepare the input of the negotiated-congestion router (tools/nroute/nroute.cpp).

  python3 tools/nroute/prep.py [routed-board-for-power-nets]

Base board = the placed board (parts, fan-out) + the plane zones + the power-rail routing copied from an earlier
Freerouting result (those nets are few, wide, and were always routed completely). Every other net is routed from
scratch by nroute. This script rasterises the fixed copper onto a 0.05 mm grid:

  hardT[layer]  where a 0.09 mm track centre may not go   (-1 free, -2 blocked, k = blocked except for net k)
  hardV         where a via centre may not go
  fixedvia      net index of an existing via at that cell (layer changes there are free for that net)
  holeblock     closer than 0.4 mm to an existing via (hole-to-hole rule, applies to every net)
and writes each net's terminals (pads, existing vias, existing tracks) as cell lists.
Output: build/nroute/{base.kicad_pcb, header.txt, hardT.i16, hardV.i16, fixedvia.i16, holeblock.u8, nets.txt}
"""
import pcbnew
import json, math, os, subprocess, sys
import numpy as np
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); TOOLS = os.path.dirname(HERE); ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from pcbgen import OUT, MM, VIA_D, VIA_DRILL, TRACK, CLEAR, PLANE_NETS
from route import POWER_CLASS, add_planes
from finish_route import poly_cells, item_poly, capsule, G, X0, Y0, NX, NY, SIG
WORK = os.environ.get('NROUTE_DIR') or os.path.join(ROOT, 'build', 'nroute'); os.makedirs(WORK, exist_ok=True)
ROUTE_HERE = {'VDD_SNVS_ANA', 'VDD_SNVS_DIG'}     # power-class nets routed by nroute (their caps moved after the old route; 1 mA LDO outputs)
PROTECT = (set(POWER_CLASS) | set(PLANE_NETS)) - ROUTE_HERE
M = 0.010                    # rasterisation margin (mm)
HOLE_CLR = float(os.environ.get('HOLE_CLR', 0.17))   # copper to hole wall
HOLE_HOLE = 0.25             # hole wall to hole wall
EDGE = 0.25                  # copper to board edge

DUMP = """
import json, sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); out = []
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        p = t.GetPosition(); out.append(['via', t.GetNetname(), '', p.x, p.y, 0, 0, t.GetWidth(), t.GetDrill()])
    else:
        a, c = t.GetStart(), t.GetEnd(); out.append(['track', t.GetNetname(), b.GetLayerName(t.GetLayer()), a.x, a.y, c.x, c.y, t.GetWidth(), 0])
print(json.dumps(out))
"""

_KEEP = []
STUB_NETS = ('GND', '+3V3')  # plane nets: a pad with no via yet gets a 'stub' net = route from the pad to any legal new via
BAND_Y = 5.25                # card y below which the old route's GND/+3V3 copper is dropped (the finger escape band)
ISLAND = [(9.1, 9.7), (13.9, 9.7), (13.9, 11.3), (19.3, 11.3), (19.3, 4.6), (23.3, 4.6), (23.3, 15.4), (19.3, 15.4),
          (19.3, 13.0), (13.9, 13.0), (13.9, 13.7), (9.1, 13.7)]      # DCDC_DIG island on In4 (same as route.py)

def mm(v): return pcbnew.ToMM(v)

def stamp(arr, cells, owner):
    """arr: int16 [NX, NY]; -1 free, -2 blocked for all, k blocked for all but net k"""
    if not len(cells): return
    x, y = cells[:, 0], cells[:, 1]
    cur = arr[x, y]
    new = np.where(cur == -1, owner, np.where(cur == owner, owner, -2))
    arr[x, y] = new

def main():
    power_src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'docs', 'layout', 'power-rails.kicad_pcb')
    placed = OUT.replace('.kicad_pcb', '-placed.kicad_pcb')
    b = pcbnew.LoadBoard(placed)
    ds = b.GetDesignSettings()
    ds.m_MinResolvedSpokes = 1                              # via-in-pad GND pads may keep a single spoke to the pour
    ds.m_SolderMaskExpansion = MM(0.05)                    # JLC: mask opening 0.05 mm larger than the pad, each side
    ds.m_HoleClearance = MM(HOLE_CLR); ds.m_ViasMinSize = MM(0.25); ds.m_MinThroughDrill = MM(0.15)
    ds.m_ViasMinAnnularWidth = MM(0.075); ds.m_TrackMinWidth = MM(0.09); ds.m_MinClearance = MM(0.09)
    # power rails: take their tracks and vias from the earlier route
    for t in list(b.GetTracks()):
        if t.GetNetname() in PROTECT: b.Remove(t); _KEEP.append(t)   # (destroying a removed item from Python breaks pcbnew 7's SWIG types)
    # (pcbnew can only hold one board per process, so the source board is read in a child process)
    dump = subprocess.run([sys.executable, '-c', DUMP, power_src], capture_output=True, text=True, check=True).stdout
    n_pw = 0
    for kind, name, layer, x1, y1, x2, y2, w, drill in json.loads(dump):
        if name not in PROTECT: continue
        if name in STUB_NETS and max(y1, y2 if kind == 'track' else y1) > MM(122 - BAND_Y): continue   # re-done here as plane stubs
        net = b.FindNet(name)
        if kind == 'via':
            v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(x1, y1)); v.SetDrill(drill); v.SetWidth(w)
            v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net); b.Add(v)
        else:
            k = pcbnew.PCB_TRACK(b); k.SetStart(pcbnew.VECTOR2I(x1, y1)); k.SetEnd(pcbnew.VECTOR2I(x2, y2)); k.SetWidth(w)
            k.SetLayer(b.GetLayerID(layer)); k.SetNet(net); b.Add(k)
        n_pw += 1
    add_planes(b)
    pcbnew.SaveBoard(os.path.join(WORK, 'base.kicad_pcb'), b)
    print('base board: copied', n_pw, 'power tracks/vias')

    lid = {n: b.GetLayerID(n) for n in SIG}
    # routable nets
    pads_of = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            n = p.GetNetname()
            if n and n not in PROTECT: pads_of.setdefault(n, []).append(p)
    nets = sorted(n for n, v in pads_of.items() if len(v) >= 2)
    kind = {n: 0 for n in nets}
    # plane nets: group each net's copper into connected lumps; a lump with no via needs a stub
    stub_of_pad = {}; stub_terms = {}
    for pn in STUB_NETS:
        items = []
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.GetNetname() != pn: continue
                for li, ln in enumerate(SIG):
                    if p.IsOnLayer(lid[ln]): items.append(('pad', (fp.GetReference(), p.GetNumber()), [(li, int(x), int(y)) for x, y in poly_cells(item_poly(p, lid[ln], 0))]))
        for t in b.GetTracks():
            if t.GetNetname() != pn: continue
            if t.GetClass() == 'PCB_VIA':
                c = poly_cells(item_poly(t, lid['F.Cu'], 0)); items.append(('via', t, [(li, int(x), int(y)) for li in range(4) for x, y in c]))
            elif b.GetLayerName(t.GetLayer()) in SIG:
                li = SIG.index(b.GetLayerName(t.GetLayer()))
                items.append(('track', t, [(li, int(x), int(y)) for x, y in poly_cells(item_poly(t, t.GetLayer(), 0))]))
        par = list(range(len(items)))
        def find(a):
            while par[a] != a: par[a] = par[par[a]]; a = par[a]
            return a
        seen = {}
        for i, (_, _, cells) in enumerate(items):
            for c in cells:
                if c in seen: par[find(i)] = find(seen[c])
                else: seen[c] = i
        lumps = {}
        for i in range(len(items)): lumps.setdefault(find(i), []).append(i)
        for root, members in lumps.items():
            if any(items[i][0] == 'via' for i in members): continue
            pads = [items[i][1] for i in members if items[i][0] == 'pad']
            if not pads: continue
            p0 = pads[0]; name = f'{pn}@{p0[0]}.{p0[1]}'
            nets.append(name); kind[name] = 1 if pn == 'GND' else 2
            for p in pads: stub_of_pad[p] = name
            stub_terms[name] = [i for i in members]
            stub_terms[name] = [items[i] for i in members]
    idx = {n: i for i, n in enumerate(nets)}
    def owner(netname, pad=None):
        if pad is not None and pad in stub_of_pad: return idx[stub_of_pad[pad]]
        return idx.get(netname, -2)
    print(sum(1 for n in nets if kind[n]), 'plane stubs:', ' '.join(n for n in nets if kind[n]))

    hardT = np.full((4, NX, NY), -1, np.int16); hardV = np.full((NX, NY), -1, np.int16)
    fixedvia = np.full((NX, NY), -1, np.int16); holeblock = np.zeros((NX, NY), np.uint8)
    terms = {n: [] for n in nets}
    stub_track_ids = {id(it[1]): n for n, its in stub_terms.items() for it in its if it[0] == 'track'}

    # board edge
    ps = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(ps)
    for arr, d in ((hardT, EDGE + TRACK / 2 + M), (hardV, EDGE + VIA_D / 2 + M)):
        q = pcbnew.SHAPE_POLY_SET(ps); q.Deflate(MM(d), 16)
        ok = np.zeros((NX, NY), bool); c = poly_cells(q); ok[c[:, 0], c[:, 1]] = True
        if arr is hardT: arr[:, ~ok] = -2
        else: arr[~ok] = -2

    # inner layers stay 1.3 mm back from the finger edge (it is bevelled)
    iy_lim = int(round((122 - 1.3 - Y0) / G))
    hardT[1:3, :, iy_lim:] = -2

    # pads
    for fp in b.GetFootprints():
        for p in fp.Pads():
            own = owner(p.GetNetname(), (fp.GetReference(), p.GetNumber()))
            tname = nets[own] if own >= 0 else None
            for li, ln in enumerate(SIG):
                if not p.IsOnLayer(lid[ln]): continue
                stamp(hardT[li], poly_cells(item_poly(p, lid[ln], CLEAR + TRACK / 2 + M)), own)
                stamp(hardV, poly_cells(item_poly(p, lid[ln], CLEAR + VIA_D / 2 + M)), -2)      # no new via-in-pad
                if own >= 0:
                    q = item_poly(p, lid[ln], 0); q.Deflate(MM(0.02), 16)
                    c = poly_cells(q)
                    if len(c): terms[tname].append([(li, int(x), int(y)) for x, y in c])
    # fixed tracks and vias
    gx, gy = np.meshgrid(np.arange(NX), np.arange(NY), indexing='ij')
    nfix = 0
    for t in b.GetTracks():
        name = t.GetNetname(); own = owner(name); nfix += 1
        if id(t) in stub_track_ids: name = stub_track_ids[id(t)]; own = idx[name]
        if t.GetClass() == 'PCB_VIA':
            r_hole = t.GetDrill() / 2e6; r_cu = t.GetWidth() / 2e6
            # track centre must clear the via copper and the via hole
            infl = max(CLEAR, r_hole + HOLE_CLR - r_cu) + TRACK / 2 + M
            c = poly_cells(item_poly(t, lid['F.Cu'], infl))
            for li in range(4): stamp(hardT[li], c, own)
            px, py = mm(t.GetPosition().x), mm(t.GetPosition().y)
            d2 = (X0 + gx * G - px) ** 2 + (Y0 + gy * G - py) ** 2
            holeblock[d2 < (r_hole + HOLE_HOLE + VIA_DRILL / 2 + 0.005) ** 2] = 1
            ix, iy = round((px - X0) / G), round((py - Y0) / G)
            on_grid = abs(X0 + ix * G - px) < 1e-4 and abs(Y0 + iy * G - py) < 1e-4
            if own >= 0:
                assert on_grid, f'fan-out via of {name} is off the routing grid: {px} {py}'
                fixedvia[ix, iy] = own
                terms[name].append([(li, ix, iy) for li in range(4)])
        else:
            ln = b.GetLayerName(t.GetLayer())
            # a new via must clear this track: copper and hole
            c = poly_cells(item_poly(t, t.GetLayer(), max(CLEAR + VIA_D / 2, HOLE_CLR + VIA_DRILL / 2) + M))
            stamp(hardV, c, own)
            if ln not in SIG: continue
            li = SIG.index(ln)
            stamp(hardT[li], poly_cells(item_poly(t, t.GetLayer(), CLEAR + TRACK / 2 + M)), own)
            if own >= 0:
                c = poly_cells(item_poly(t, t.GetLayer(), -min(0.02, t.GetWidth() / 2e6 - 0.02)))
                if len(c): terms[name].append([(li, int(x), int(y)) for x, y in c])
    print(len(nets), 'nets to route;', nfix, 'fixed tracks/vias')
    from matplotlib.path import Path
    gxx, gyy = np.meshgrid(np.arange(NX), np.arange(NY), indexing='ij')
    cx = X0 + gxx * G - 100; cy = 122 - (Y0 + gyy * G)
    isl = Path(ISLAND).contains_points(np.stack([cx.ravel(), cy.ravel()], 1), radius=0.0).reshape(NX, NY)
    near = np.zeros_like(isl)
    for dx in range(-8, 9):
        for dy in range(-8, 9): near |= np.roll(np.roll(isl, dx, 0), dy, 1)
    (~near).astype(np.uint8).tofile(os.path.join(WORK, 'mask3v3.u8'))
    open(os.path.join(WORK, 'header.txt'), 'w').write(f'{NX} {NY} 4 {len(nets)}\n')
    hardT.tofile(os.path.join(WORK, 'hardT.i16')); hardV.tofile(os.path.join(WORK, 'hardV.i16'))
    fixedvia.tofile(os.path.join(WORK, 'fixedvia.i16')); holeblock.tofile(os.path.join(WORK, 'holeblock.u8'))
    with open(os.path.join(WORK, 'nets.txt'), 'w') as f:
        for n in nets:
            if kind[n]: terms[n] = [sorted(set(c for t in terms[n] for c in t))]          # a stub: one terminal
            f.write(f'{n} {len(terms[n])} {kind[n]}\n')
            for t in terms[n]: f.write(str(len(t)) + ' ' + ' '.join(f'{l} {x} {y}' for l, x, y in t) + '\n')
    print('terminals per net: max', max(len(terms[n]) for n in nets))

if __name__ == '__main__':
    main()
